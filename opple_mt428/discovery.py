# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 youli-naixu and contributors

from __future__ import annotations

import ipaddress
import secrets
import socket
import time
from dataclasses import asdict, dataclass

from .protocol import SEARCH, SEARCH_RESPONSE, SUPPORTED_SKU, ProtocolError, build_packet, parse_reply


@dataclass(frozen=True)
class Candidate:
    ip: str
    port: int
    mac: str
    sku: str
    version_raw: str
    name: str
    device_id: int
    mac_tail_hex: str
    control_supported: bool

    def as_dict(self):
        return asdict(self)


def decode_candidate(data: bytes, address: tuple[str, int], serial: int) -> Candidate:
    if address[1] != 55001:
        raise ProtocolError("Unexpected discovery source port")
    reply = parse_reply(data)
    if reply.message_type != SEARCH_RESPONSE or reply.response_serial != serial:
        raise ProtocolError("Discovery response type or serial mismatch")
    body = reply.body
    if len(body) < 0x34:
        raise ProtocolError("Discovery body is shorter than the known identity fields")
    source_ip = ipaddress.IPv4Address(address[0])
    reported_ip = socket.inet_ntoa(body[0x1F:0x23])
    port = int.from_bytes(body[0x23:0x25], "big")
    mac = body[9:15]
    if reported_ip != str(source_ip) or source_ip.is_multicast or source_ip.is_unspecified:
        raise ProtocolError("Discovery source and reported IPv4 address disagree")
    if port != address[1] or not mac or mac[0] & 1 or mac == bytes(6):
        raise ProtocolError("Invalid discovery endpoint or MAC address")
    sku = int.from_bytes(body[3:7], "big")
    name = body[0x25:0x33].split(b"\x00", 1)[0].rstrip(b"@").decode("gbk", errors="replace")
    device_id = int.from_bytes(body[0x13:0x17], "big")
    mac_tail = body[15:17]
    return Candidate(
        ip=str(source_ip), port=port, mac=mac.hex(":"), sku=hex(sku),
        version_raw=hex(int.from_bytes(body[0x1B:0x1F], "big")), name=name,
        device_id=device_id, mac_tail_hex=mac_tail.hex(),
        control_supported=sku == SUPPORTED_SKU and device_id != 0 and not any(mac_tail),
    )


def discover(*, interface: str | None = None, target: str | None = None, bind: str = "0.0.0.0", timeout: float = 3.0) -> list[Candidate]:
    """Send one read-only SEARCH, collect candidates; never send QUERY or a write."""
    if bool(interface) == bool(target):
        raise ValueError("Choose one --interface IPv4/CIDR or one --target IPv4")
    if not 0.1 <= timeout <= 30:
        raise ValueError("Discovery timeout must be 0.1..30 seconds")
    selected = None
    if interface:
        selected = ipaddress.IPv4Interface(interface)
        if selected.network.prefixlen >= 31 or selected.ip in (selected.network.network_address, selected.network.broadcast_address):
            raise ValueError("Broadcast discovery requires a usable local address and prefix <= 30")
        bind_ip = str(selected.ip)
        destination = str(selected.network.broadcast_address)
    else:
        destination = str(ipaddress.IPv4Address(target))
        address = ipaddress.IPv4Address(destination)
        if address.is_multicast or address.is_unspecified or destination == "255.255.255.255":
            raise ValueError("--target requires a unicast IPv4 address")
        bind_ip = str(ipaddress.IPv4Address(bind))
    serial = secrets.randbelow(0xFFFFFFFE) + 1
    found = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        if selected:
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp.bind((bind_ip, 0))
        udp.sendto(build_packet(SEARCH, serial), (destination, 55001))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            udp.settimeout(max(0.01, deadline - time.monotonic()))
            try:
                data, address = udp.recvfrom(65535)
            except socket.timeout:
                break
            source = ipaddress.IPv4Address(address[0])
            if selected and source not in selected.network:
                continue
            if not selected and address[0] != destination:
                continue
            try:
                candidate = decode_candidate(data, address, serial)
            except (ProtocolError, ValueError):
                continue
            found[(candidate.mac, candidate.ip, candidate.port)] = candidate
    candidates = list(found.values())
    conflicted = {item.mac for item in candidates if sum(other.mac == item.mac for other in candidates) > 1}
    if conflicted:
        from dataclasses import replace
        candidates = [replace(item, control_supported=False) if item.mac in conflicted else item for item in candidates]
    return sorted(candidates, key=lambda item: (item.ip, item.mac))
