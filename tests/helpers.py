import binascii
import socket
import struct

from opple_mt428.protocol import HEADER_SIZE, SEARCH_RESPONSE, build_packet, xor_body


MAC = bytes.fromhex("020000000001")
IP = "192.0.2.42"


def reply_packet(message_type, serial, body, mac=None):
    data = bytearray(build_packet(message_type, 0, body))
    struct.pack_into("!I", data, 0x68, serial)
    data[0x70:0x74] = bytes(4)
    struct.pack_into("!I", data, 0x70, binascii.crc_hqx(data[0x64:], 0))
    if mac is not None:
        data[HEADER_SIZE:] = xor_body(body, mac)
    return bytes(data)


def discovery_reply(serial=42, sku=0x50061, ip=IP, port=55001, name=b"test-lamp@@@@@", size=61):
    body = bytearray(size)
    body[3:7] = sku.to_bytes(4, "big")
    body[9:15] = MAC
    body[0x13:0x17] = (123).to_bytes(4, "big")
    body[0x1B:0x1F] = (0x210).to_bytes(4, "big")
    body[0x1F:0x23] = socket.inet_aton(ip)
    body[0x23:0x25] = port.to_bytes(2, "big")
    body[0x25:0x33] = name[:14].ljust(14, b"\x00")
    return reply_packet(SEARCH_RESPONSE, serial, bytes(body))
