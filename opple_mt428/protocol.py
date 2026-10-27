# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 youli-naixu and contributors

from __future__ import annotations

import binascii
import ipaddress
import secrets
import socket
import struct
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone


SEARCH = 0x02010000
SEARCH_RESPONSE = 0x02020000
QUERY = 0x030F0000
QUERY_RESPONSE = 0x03100000
POWER = 0x03110000
BRIGHTNESS = 0x03130000
COLOR_TEMP = 0x031B0000
EXPERIMENTAL_CHANNELS = 0x03450000
HEADER_SIZE = 0x7C
SUPPORTED_SKU = 0x50061
MODEL = "MT428-D0.5×36+0.2×21-WTT"


class LampError(Exception):
    pass


class ProtocolError(LampError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def xor_body(body: bytes, mac: bytes) -> bytes:
    password = (mac * 4)[:20]
    return bytes(value ^ password[index % 20] for index, value in enumerate(body))


def build_packet(
    message_type: int,
    serial: int,
    body: bytes = b"",
    *,
    local_port: int = 0,
    device_id: int = 0,
    mac: bytes | None = None,
) -> bytes:
    data = bytearray(HEADER_SIZE) + body
    fields = {
        0x0C: local_port,
        0x10: 0x03F2,
        0x14: 0x2775,
        0x1C: len(body) + 0x68,
        0x20: 1,
        0x24: 2,
        0x28: 3,
        0x30: 5,
        0x3C: 0x6A68,
        0x50: 1,
        0x54: device_id,
        0x64: serial,
        0x6C: len(body) + 0x18,
        0x74: message_type,
    }
    for offset, value in fields.items():
        struct.pack_into("!I", data, offset, value)
    struct.pack_into("!I", data, 0x70, binascii.crc_hqx(data[0x64:], 0))
    if mac is not None:
        data[HEADER_SIZE:] = xor_body(body, mac)
    return bytes(data)


@dataclass(frozen=True)
class Reply:
    message_type: int
    response_serial: int
    body: bytes


def parse_reply(data: bytes, mac: bytes | None = None) -> Reply:
    if len(data) < HEADER_SIZE:
        raise ProtocolError("设备报文过短")
    if len(data) > 4096:
        raise ProtocolError("Datagram exceeds this implementation's 4096-byte limit")
    if int.from_bytes(data[0x1C:0x20], "big") != len(data) - 0x14:
        raise ProtocolError("Package length does not match the UDP payload")
    message_type = int.from_bytes(data[0x74:0x78], "big")
    plain = bytearray(data)
    if message_type != SEARCH_RESPONSE:
        if mac is None:
            raise ProtocolError("缺少设备身份，无法解码回复")
        plain[HEADER_SIZE:] = xor_body(data[HEADER_SIZE:], mac)
    expected = int.from_bytes(plain[0x70:0x74], "big")
    plain[0x70:0x74] = bytes(4)
    if binascii.crc_hqx(plain[0x64:], 0) != expected:
        raise ProtocolError("设备回复校验失败")
    message_length = int.from_bytes(plain[0x6C:0x70], "big")
    if message_length != len(data) - 0x64:
        raise ProtocolError("设备回复长度不匹配")
    return Reply(
        message_type=message_type,
        response_serial=int.from_bytes(plain[0x68:0x6C], "big"),
        body=bytes(plain[HEADER_SIZE:]),
    )


def build_channel_body(changes: dict) -> bytes:
    """Experimental wire fields from the 0x50061 vendor-app analysis; not hardware-verified."""
    if not changes or set(changes) - {"power", "brightness"}:
        raise ValueError("Side-light control accepts power and/or brightness")
    body = bytearray(10)
    body[:4] = SUPPORTED_SKU.to_bytes(4, "big")
    body[4] = body[6] = 2
    if "power" in changes:
        if type(changes["power"]) is not bool:
            raise ValueError("Side-light power must be a boolean")
        body[4] = int(changes["power"])
    if "brightness" in changes:
        if type(changes["brightness"]) is not int or not 10 <= changes["brightness"] <= 255:
            raise ValueError("Experimental side-light brightness must be raw 10..255")
        body[5] = changes["brightness"]
    return bytes(body)


def parse_channel_state(body: bytes) -> dict | None:
    if len(body) < 58:
        return None
    return {
        "evidence": "vendor-app-static-analysis; hardware-validation-pending",
        "arm_power_raw": body[52],
        "arm_brightness_raw": body[53],
        "head_power_raw": body[54],
        "head_brightness_raw": body[55],
        "head_color_temp_raw": int.from_bytes(body[56:58], "big"),
    }


class OppleLamp:
    def __init__(self, ip: str, mac: str, timeout: float = 1.2, *, read_only: bool = True, bind: str = "0.0.0.0", experimental_side_light: bool = False):
        self.ip = str(ipaddress.IPv4Address(ip))
        target = ipaddress.IPv4Address(self.ip)
        if target.is_multicast or target.is_unspecified or self.ip == "255.255.255.255":
            raise ValueError("Control requires a unicast device IPv4 address")
        self.mac = bytes.fromhex(mac.replace(":", "").replace("-", ""))
        if len(self.mac) != 6 or self.mac[0] & 1 or self.mac == bytes(6):
            raise ValueError("A valid unicast device MAC address is required")
        self.read_only = read_only
        self.simulated = False
        self.experimental_side_light = experimental_side_light
        self.timeout = timeout
        self.port = 55001
        self.device_id = 0
        self.initialized = False
        self.sku = "未知"
        self.version = "未知"
        self._serial = secrets.randbelow(1000) + 1
        self._lock = threading.RLock()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((str(ipaddress.IPv4Address(bind)), 0))
        self._socket.settimeout(timeout)

    def close(self):
        self._socket.close()

    def _next_serial(self) -> int:
        self._serial = self._serial % 0xFFFFFFFE + 1
        return self._serial

    def _send(self, message_type: int, body: bytes = b"") -> int:
        serial = self._next_serial()
        packet = build_packet(
            message_type,
            serial,
            body,
            local_port=self._socket.getsockname()[1] if self.initialized else 0,
            device_id=self.device_id if self.initialized else 0,
            mac=self.mac if self.initialized else None,
        )
        if self.read_only and message_type not in (SEARCH, QUERY):
            raise LampError("Read-only mode: light-changing commands are disabled")
        self._socket.sendto(packet, (self.ip, self.port))
        return serial

    def _receive(self, serial: int, message_type: int) -> Reply:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            self._socket.settimeout(max(0.01, deadline - time.monotonic()))
            try:
                data, address = self._socket.recvfrom(4096)
            except socket.timeout as error:
                raise LampError("台灯没有回复，请检查电源和局域网连接") from error
            if address[0] != self.ip or address[1] != self.port:
                continue
            try:
                reply = parse_reply(data, self.mac)
            except ProtocolError:
                continue
            if reply.response_serial == serial and reply.message_type == message_type:
                return reply
        raise LampError("未收到与本次请求匹配的台灯回复")

    def discover(self):
        with self._lock:
            self.initialized = False
            self.port = 55001
            reply = self._receive(self._send(SEARCH), SEARCH_RESPONSE)
            if len(reply.body) < 0x34:
                raise ProtocolError("发现回复缺少设备身份字段")
            body = reply.body
            reported_mac = body[9:15]
            reported_ip = socket.inet_ntoa(body[0x1F:0x23])
            if reported_mac != self.mac or reported_ip != self.ip:
                raise ProtocolError("设备IP或MAC不符合这台台灯，已停止控制")
            port = int.from_bytes(body[0x23:0x25], "big")
            if port != self.port:
                raise ProtocolError("Reported device port disagrees with the validated source endpoint")
            self.port = port
            self.device_id = int.from_bytes(body[0x13:0x17], "big")
            self.sku = hex(int.from_bytes(body[3:7], "big"))
            self.version = hex(int.from_bytes(body[0x1B:0x1F], "big"))
            if not self.read_only and (int(self.sku, 16) != SUPPORTED_SKU or not self.device_id or any(body[15:17])):
                raise ProtocolError("This device identity/layout is unverified; use --read-only for inspection")
            self.initialized = True

    def query(self) -> dict:
        with self._lock:
            for attempt in range(2):
                try:
                    if not self.initialized:
                        self.discover()
                    reply = self._receive(self._send(QUERY), QUERY_RESPONSE)
                    break
                except LampError:
                    self.initialized = False
                    if attempt:
                        raise
            if len(reply.body) < 9:
                raise ProtocolError("状态回复缺少灯光字段")
            body = reply.body
            if body[1] not in (0, 1):
                raise ProtocolError("台灯开关字段超出已适配范围")
            state = {
                "power": bool(body[1]),
                "brightness": body[2],
                "brightness_pct": round(body[2] * 100 / 255, 1),
                "color_temp": int.from_bytes(body[7:9], "big"),
                "observed_at": now_iso(),
            }
            if self.experimental_side_light and int(self.sku, 16) == SUPPORTED_SKU:
                state["experimental_channels"] = parse_channel_state(body)
            return state

    def write(self, field: str, value: bool | int):
        with self._lock:
            if not self.initialized:
                self.discover()
            if field == "power" and type(value) is bool:
                message_type, body = POWER, bytes([int(value)])
            elif field == "brightness" and type(value) is int and 0 <= value <= 255:
                message_type, body = BRIGHTNESS, bytes([value])
            elif field == "color_temp" and type(value) is int and 2700 <= value <= 6500:
                message_type, body = COLOR_TEMP, value.to_bytes(2, "big")
            else:
                raise ValueError("无效的台灯控制字段或数值")
            self._send(message_type, body)

    def write_side_light(self, changes: dict):
        if not self.experimental_side_light:
            raise LampError("Experimental side-light support is disabled")
        if self.read_only:
            raise LampError("Read-only mode: side-light writes are disabled")
        body = build_channel_body(changes)
        with self._lock:
            if not self.initialized:
                self.discover()
            if int(self.sku, 16) != SUPPORTED_SKU:
                raise ProtocolError("Experimental channels require SKU 0x50061")
            self._send(EXPERIMENTAL_CHANNELS, body)

    @property
    def identity(self) -> dict:
        return {
            "name": "欧普台灯",
            "model": MODEL,
            "ip": self.ip,
            "mac": self.mac.hex(":"),
            "port": self.port,
            "sku": self.sku,
            "version": self.version,
            "transport": "局域网 UDP",
        }
