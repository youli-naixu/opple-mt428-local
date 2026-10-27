import socket
import unittest
from unittest.mock import Mock, patch

from helpers import IP, MAC, reply_packet
from opple_mt428.protocol import (
    HEADER_SIZE, POWER, QUERY_RESPONSE, SEARCH, SEARCH_RESPONSE,
    LampError, OppleLamp, ProtocolError, build_channel_body,
    build_packet, parse_channel_state, parse_reply,
)


class ProtocolTests(unittest.TestCase):
    def test_search_packet_lengths_and_checksum(self):
        data = build_packet(SEARCH, 42)
        self.assertEqual(len(data), HEADER_SIZE)
        self.assertEqual(int.from_bytes(data[0x1C:0x20], "big"), 0x68)
        self.assertEqual(int.from_bytes(data[0x6C:0x70], "big"), 0x18)

    def test_encrypted_reply_preserves_state_and_serial(self):
        body = bytearray(58)
        body[1], body[2] = 1, 102
        body[7:9] = (4000).to_bytes(2, "big")
        reply = parse_reply(reply_packet(QUERY_RESPONSE, 42, bytes(body), MAC), MAC)
        self.assertEqual(reply.response_serial, 42)
        self.assertEqual(reply.body, body)

    def test_corrupt_crc_and_both_length_fields_are_rejected(self):
        source = reply_packet(SEARCH_RESPONSE, 42, bytes(61))
        for offset in (-1, 0x1F, 0x6F):
            data = bytearray(source)
            data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ProtocolError):
                parse_reply(bytes(data))

    def test_truncated_and_oversized_packets_are_rejected(self):
        for size in (0, 123, 4097):
            with self.subTest(size=size), self.assertRaises(ProtocolError):
                parse_reply(bytes(size))

    def test_wrong_xor_mac_fails_crc(self):
        data = reply_packet(QUERY_RESPONSE, 42, bytes(range(58)), MAC)
        with self.assertRaises(ProtocolError):
            parse_reply(data, bytes.fromhex("020000000002"))

    def test_read_only_transport_blocks_before_send(self):
        fake = Mock()
        fake.getsockname.return_value = ("192.0.2.10", 42000)
        with patch("opple_mt428.protocol.socket.socket", return_value=fake):
            lamp = OppleLamp(IP, MAC.hex(":"))
            with self.assertRaises(LampError):
                lamp._send(POWER, b"\x01")
            fake.sendto.assert_not_called()
            lamp.close()

    def test_unicast_and_mac_required(self):
        for ip, mac in (("238.238.238.238", MAC.hex(":")), (IP, "00:00:00:00:00:00"), (IP, "01:00:00:00:00:01")):
            with self.subTest(ip=ip, mac=mac), self.assertRaises(ValueError):
                OppleLamp(ip, mac)

    def test_side_light_body_only_changes_selected_arm_fields(self):
        off = build_channel_body({"power": False})
        dim = build_channel_body({"brightness": 123})
        self.assertEqual(len(off), 10)
        self.assertEqual(int.from_bytes(off[:4], "big"), 0x50061)
        self.assertEqual(off[4], 0)
        self.assertEqual(off[6], 2)
        self.assertEqual(dim[4], 2)
        self.assertEqual(dim[5], 123)
        self.assertEqual(dim[6:], bytes([2, 0, 0, 0]))

    def test_side_light_invalid_values_rejected(self):
        for payload in ({}, {"head_power": True}, {"power": 1}, {"brightness": True}, {"brightness": 9}, {"brightness": 256}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                build_channel_body(payload)

    def test_candidate_channel_offsets_are_labeled_unverified(self):
        self.assertIsNone(parse_channel_state(bytes(57)))
        body = bytearray(58)
        body[52:56] = bytes([1, 123, 0, 100])
        body[56:58] = (4000).to_bytes(2, "big")
        result = parse_channel_state(bytes(body))
        self.assertEqual(result["arm_power_raw"], 1)
        self.assertEqual(result["arm_brightness_raw"], 123)
        self.assertEqual(result["head_color_temp_raw"], 4000)
        self.assertIn("pending", result["evidence"])


if __name__ == "__main__":
    unittest.main()
