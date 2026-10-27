import socket
import unittest
from unittest.mock import patch

from helpers import IP, discovery_reply, reply_packet
from opple_mt428.discovery import decode_candidate, discover
from opple_mt428.protocol import ProtocolError, QUERY_RESPONSE, SEARCH


class FakeSocket:
    def __init__(self, replies):
        self.replies = replies
        self.sent = []
        self.options = []
        self.bound = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def setsockopt(self, *args):
        self.options.append(args)

    def bind(self, endpoint):
        self.bound = endpoint

    def settimeout(self, timeout):
        pass

    def sendto(self, data, endpoint):
        self.sent.append((data, endpoint))

    def recvfrom(self, size):
        if self.replies:
            return self.replies.pop(0)
        raise socket.timeout


class DiscoveryTests(unittest.TestCase):
    def test_known_old_and_unknown_skus_are_returned(self):
        for sku in (0x50061, 0x100010E, 0x123456):
            result = decode_candidate(discovery_reply(sku=sku), (IP, 55001), 42)
            self.assertEqual(result.sku, hex(sku))
            self.assertEqual(result.control_supported, sku == 0x50061)

    def test_type_serial_source_and_reported_ip_checked(self):
        cases = [
            (discovery_reply(serial=43), (IP, 55001)),
            (discovery_reply(), (IP, 80)),
            (discovery_reply(ip="192.0.2.43"), (IP, 55001)),
            (discovery_reply(port=55002), (IP, 55001)),
            (reply_packet(QUERY_RESPONSE, 42, bytes(61)), (IP, 55001)),
        ]
        for data, endpoint in cases:
            with self.subTest(endpoint=endpoint), self.assertRaises(ProtocolError):
                decode_candidate(data, endpoint, 42)

    def test_minimum_body_gbk_padding_and_invalid_text(self):
        name = "台灯".encode("gbk") + b"@@@\x00ignored"
        result = decode_candidate(discovery_reply(size=52, name=name), (IP, 55001), 42)
        self.assertEqual(result.name, "台灯")
        result = decode_candidate(discovery_reply(name=b"\xff\x00"), (IP, 55001), 42)
        self.assertTrue(result.name)

    def test_direct_discovery_sends_one_search_and_never_writes(self):
        fake = FakeSocket([(b"malformed", (IP, 55001)), (discovery_reply(), (IP, 55001))])
        with patch("opple_mt428.discovery.socket.socket", return_value=fake), patch("opple_mt428.discovery.secrets.randbelow", return_value=41):
            result = discover(target=IP)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(fake.sent), 1)
        data, endpoint = fake.sent[0]
        self.assertEqual(endpoint, (IP, 55001))
        self.assertEqual(int.from_bytes(data[0x74:0x78], "big"), SEARCH)

    def test_explicit_interface_broadcast_and_unknown_does_not_break(self):
        fake = FakeSocket([(discovery_reply(sku=0x123456), (IP, 55001)), (discovery_reply(ip="192.0.2.43"), ("192.0.2.43", 55001))])
        with patch("opple_mt428.discovery.socket.socket", return_value=fake), patch("opple_mt428.discovery.secrets.randbelow", return_value=41):
            result = discover(interface="192.0.2.10/24")
        self.assertEqual(fake.bound, ("192.0.2.10", 0))
        self.assertEqual(fake.sent[0][1], ("192.0.2.255", 55001))
        self.assertIn((socket.SOL_SOCKET, socket.SO_BROADCAST, 1), fake.options)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(not item.control_supported for item in result))

    def test_outside_interface_response_is_ignored(self):
        fake = FakeSocket([(discovery_reply(ip="198.51.100.42"), ("198.51.100.42", 55001))])
        with patch("opple_mt428.discovery.socket.socket", return_value=fake):
            self.assertEqual(discover(interface="192.0.2.10/24"), [])

    def test_requires_explicit_target_or_interface(self):
        for args in ({}, {"target": IP, "interface": "192.0.2.10/24"}, {"target": "238.238.238.238"}, {"interface": "192.0.2.10/32"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                discover(**args)


if __name__ == "__main__":
    unittest.main()
