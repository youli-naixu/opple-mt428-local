# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 youli-naixu and contributors

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .protocol import LampError, build_channel_body, build_head_body, now_iso


LOG = logging.getLogger("opple.demo")
CHANNEL_FIELDS = {
    "arm": {"power": "arm_power_raw", "brightness": "arm_brightness_raw"},
    "head": {"power": "head_power_raw", "brightness": "head_brightness_raw", "color_temp": "head_color_temp_raw"},
}
STATIC = Path(__file__).parent / "static"
SCENES = [
    {"id": "reading", "name": "专注阅读", "brightness_pct": 70, "color_temp": 4000, "description": "中性光 · 70%亮度"},
    {"id": "screen", "name": "屏幕陪伴", "brightness_pct": 35, "color_temp": 4500, "description": "清爽光 · 35%亮度"},
    {"id": "relax", "name": "晚间放松", "brightness_pct": 20, "color_temp": 3000, "description": "暖光 · 20%亮度"},
]


class VerificationError(LampError):
    pass


def validate_control(payload: dict) -> dict:
    if not payload or set(payload) - {"power", "brightness", "color_temp"}:
        raise ValueError("请提供开关、亮度或色温，暂不支持其他控制字段")
    if "power" in payload and type(payload["power"]) is not bool:
        raise ValueError("开关必须是true或false")
    if "brightness" in payload and (type(payload["brightness"]) is not int or not 0 <= payload["brightness"] <= 255):
        raise ValueError("亮度必须是0至255的整数")
    if "color_temp" in payload and (type(payload["color_temp"]) is not int or not 2700 <= payload["color_temp"] <= 6500):
        raise ValueError("色温必须是2700至6500 K的整数")
    return payload


def same_value(field: str, actual, expected) -> bool:
    if field == "color_temp":
        return abs(actual - expected) <= 80
    if field == "brightness":
        return abs(actual - expected) <= 2
    return actual == expected


class LampApplication:
    def __init__(self, lamp):
        self.lamp = lamp
        self.read_only = getattr(lamp, "read_only", True)
        self.simulated = getattr(lamp, "simulated", False)
        self.lock = threading.RLock()
        self.state = None
        self.initial_state = None
        self.online = False
        self.error = "尚未查询台灯"
        self.activity = deque(maxlen=40)
        self.verified_fields = set()
        self.timer_deadline = None
        self.timer_ends_at = None
        self._stop = threading.Event()
        self._timer_thread = threading.Thread(target=self._timer_loop, name="lamp-timer", daemon=True)
        self._timer_thread.start()

    def close(self):
        self._stop.set()
        self._timer_thread.join(timeout=2)
        self.lamp.close()

    def event(self, label: str, outcome: str, details: str = ""):
        self.activity.appendleft({"id": time.time_ns(), "at": now_iso(), "label": label, "outcome": outcome, "details": details})
        LOG.info("%s | %s | %s", label, outcome, details)

    def _read(self):
        try:
            # power remains the device's overall (head OR arm) state.
            self.state = deepcopy(self.lamp.query())
        except (LampError, OSError) as error:
            was_online = self.online
            self.online = False
            self.error = str(error)
            if was_online:
                self.event("台灯连接中断", "error", str(error))
            raise
        was_offline = not self.online
        self.online = True
        self.error = None
        if self.initial_state is None:
            self.initial_state = deepcopy(self.state)
            self.event("已保存本次启动时状态", "info", "恢复按钮仅恢复本次服务启动后首次读到的状态")
        if was_offline:
            self.event("已连接台灯", "success", "本地发现与状态查询校验通过")
        return self.state

    def capabilities(self):
        items = [
            {"id": "status", "title": "实时状态", "status": "verified" if self.state else "available", "description": "从台灯直接读取，显示最近一次更新时间"},
            {"id": "power", "title": "灯光开关", "description": "总开关为任一通道开启；单独开关请求使用兼容命令，不保证同时开启两个通道"},
            {"id": "brightness", "title": "主灯亮度", "description": "本地协议0–255级；面板以百分比显示"},
            {"id": "color_temp", "title": "主灯色温", "description": "按本地库2700–6500 K范围请求，以设备回报为准"},
            {"id": "scene", "title": "本地光线场景", "status": "available", "description": "本页组合亮度与色温，不调用原厂模式"},
            {"id": "timer", "title": "定时关灯", "status": "available", "description": "由本机服务计时；关闭服务或重启后取消"},
            {"id": "restore", "title": "恢复启动时状态", "status": "available", "description": "保存通道状态时分别恢复主灯与侧灯；否则恢复旧版开关、亮度和色温"},
            {"id": "side_light", "title": "侧灯／副灯（实验性）", "status": "experimental", "description": "专用协议写入与回读已实测；物理目视验证待完成，需显式启用实验支持"},
            {"id": "native_reading", "title": "原厂阅读／书写", "status": "unadapted", "description": "官方App分别4000／5000 K，并包含侧灯联动；本页场景只组合已适配参数"},
            {"id": "native_computer", "title": "原厂电脑模式", "status": "unadapted", "description": "官方模式为仅侧灯照明；原厂模式组合尚未适配"},
            {"id": "native_favorite", "title": "原厂最爱模式", "status": "unadapted", "description": "官方支持保存色温、亮度及侧灯开关；本页本地场景不写入原厂最爱"},
            {"id": "native_schedule", "title": "原厂定时与重复", "status": "unadapted", "description": "官方App支持一组可重复定时；设备端计划协议尚未适配"},
            {"id": "native_countdown", "title": "原厂倒计时", "status": "unadapted", "description": "官方最长23小时59分，支持断网继续；本页定时由电脑服务执行"},
            {"id": "native_pomodoro", "title": "原厂番茄钟", "status": "unadapted", "description": "官方支持25分钟专注、暂停及结束提醒；本地协议尚未适配"},
            {"id": "button_indicator", "title": "按键指示灯设置", "status": "unadapted", "description": "同型号评测记录了常亮设置；当前固件及本地协议尚待验证"},
        ]
        for item in items:
            if "status" not in item:
                item["status"] = "verified" if item["id"] in self.verified_fields else "available"
        return items

    def snapshot(self, refresh: bool = False) -> dict:
        with self.lock:
            if refresh:
                try:
                    self._read()
                except (LampError, OSError):
                    pass
            remaining = max(0, int(self.timer_deadline - time.monotonic() + 0.999)) if self.timer_deadline else 0
            return {
                "ok": True,
                "online": self.online,
                "read_only": self.read_only,
                "simulated": self.simulated,
                "experimental_side_light": getattr(self.lamp, "experimental_side_light", False),
                "message": self.error,
                "device": self.lamp.identity,
                "state": deepcopy(self.state),
                "initial_state": deepcopy(self.initial_state),
                "timer": {"active": self.timer_deadline is not None, "seconds_remaining": remaining, "ends_at": self.timer_ends_at},
                "capabilities": self.capabilities(),
                "scenes": SCENES,
                "activity": list(self.activity),
            }

    def control(self, changes: dict, label: str = "应用灯光") -> dict:
        validate_control(changes)
        self.require_write()
        with self.lock:
            try:
                self._read()
                use_head = (getattr(self.lamp, "experimental_side_light", False)
                            and self.state.get("experimental_channels")
                            and any(field in changes for field in ("brightness", "color_temp")))
                if use_head:
                    self._control_head(changes)
                else:
                    self._control_legacy(changes)
                for field, value in changes.items():
                    if not same_value(field, self.state[field], value):
                        raise VerificationError(f"组合操作后{self.field_name(field)}未保持请求值")
                detail = "；".join(f"{self.field_name(field)}={self.state[field]}" for field in changes)
                self.event(label, "success", detail)
            except (LampError, OSError) as error:
                self.event(label, "error", str(error))
                raise
            result = self.snapshot()
            result["verified"] = True
            return result

    def _control_legacy(self, changes):
        """Power-only requests retain legacy overall semantics; ON need not enable both lamps."""
        starting_power = self.state["power"]
        final_power = changes.get("power", starting_power)
        needs_light = any(field in changes and not same_value(field, self.state[field], changes[field]) for field in ("brightness", "color_temp"))
        temporary_power = needs_light and not starting_power and not final_power
        order = []
        if not starting_power and (needs_light or final_power):
            order.append(("power", True))
        order.extend((field, changes[field]) for field in ("brightness", "color_temp") if field in changes)
        if not final_power and (starting_power or needs_light or "power" in changes):
            order.append(("power", False))
        elif final_power and not order and "power" in changes:
            order.append(("power", True))
        temporary_power_attempted = False
        operation_error = None
        try:
            for field, value in order:
                if temporary_power and field == "power" and value is True:
                    temporary_power_attempted = True
                self._write_verified(field, value)
                if field == "power" and value is False:
                    temporary_power_attempted = False
        except (LampError, OSError) as error:
            operation_error = error
            raise
        finally:
            # A failed readback can leave stale OFF state after a successful ON packet.
            if temporary_power_attempted:
                try:
                    self._write_verified("power", False)
                except (LampError, OSError) as restore_error:
                    self.event("临时开灯恢复失败", "error", str(restore_error))
                    if operation_error is not None:
                        raise VerificationError(f"原操作失败：{operation_error}；恢复关灯也失败：{restore_error}") from operation_error
                    raise

    def _control_head(self, changes):
        """Dedicated parameters work while head is off; combined ON explicitly enables head."""
        for field in ("brightness", "color_temp"):
            if field in changes:
                self._write_channel_verified("head", field, changes[field])
        if changes.get("power") is True:
            self._write_channel_verified("head", "power", True)
        elif changes.get("power") is False:
            self._write_verified("power", False)
        channels = self._channels()
        for field in ("brightness", "color_temp"):
            if field in changes and channels[CHANNEL_FIELDS["head"][field]] != changes[field]:
                raise VerificationError(f"组合操作后主灯{self.field_name(field)}未保持请求值")
        if changes.get("power") is True and channels["head_power_raw"] != 1:
            raise VerificationError("总开关为开，但主灯通道未开启")

    def _channels(self):
        channels = (self.state or {}).get("experimental_channels") or {}
        if any(key not in channels for fields in CHANNEL_FIELDS.values() for key in fields.values()):
            raise VerificationError("缺少完整的通道回读字段")
        return channels

    def _write_channel_once(self, channel, field, value):
        """Write one parameter, QUERY once, and check every unselected channel field."""
        before = dict(self._channels())
        key = CHANNEL_FIELDS[channel][field]
        expected = max(25, value) if channel == "arm" and field == "brightness" else value
        writer = self.lamp.write_side_light if channel == "arm" else self.lamp.write_head
        writer({field: value})
        time.sleep(0.2)
        self._read()
        after = self._channels()
        other = "head" if channel == "arm" else "arm"
        other_preserved = all(after[name] == before[name] for name in CHANNEL_FIELDS[other].values())
        untouched_preserved = all(after[name] == before[name] for fields in CHANNEL_FIELDS.values() for name in fields.values() if name != key)
        matched = after[key] == expected
        power_consistent = self.state["power"] == bool(after["arm_power_raw"] or after["head_power_raw"])
        return {
            "channel": channel, "field": field, "requested": value, "expected": expected,
            "actual": bool(after[key]) if field == "power" and after[key] in (0, 1) else after[key],
            "candidate_readback_matched": matched,
            "other_channel_preserved": other_preserved,
            "untouched_fields_preserved": untouched_preserved,
            "protocol_verified": matched and untouched_preserved and power_consistent,
            "readback": dict(after),
        }

    def _write_channel_verified(self, channel, field, value):
        step = self._write_channel_once(channel, field, value)
        if not step["protocol_verified"]:
            raise VerificationError(f"{channel}.{field}通道核验失败；请求={value}，回报={step['actual']}；其他字段保持={step['untouched_fields_preserved']}")
        if channel == "head":
            self.verified_fields.add(field)
        return step

    def require_write(self):
        if self.read_only:
            raise LampError("只读模式禁止改变灯光 / Read-only mode blocks light changes")

    def side_light(self, changes: dict) -> dict:
        """Protocol write/readback tested; optical validation pending. Each field gets its own QUERY."""
        self.require_write()
        if not getattr(self.lamp, "experimental_side_light", False):
            raise LampError("Experimental side-light support is disabled")
        if not changes or set(changes) - {"power", "brightness"}:
            raise ValueError("Side-light control accepts power and/or brightness")
        for field, value in changes.items():
            build_channel_body({field: value})
        with self.lock:
            self._read()
            before = dict(self._channels())
            steps = []
            for field in ("brightness", "power"):
                if field in changes:
                    step = self._write_channel_once("arm", field, changes[field])
                    steps.append(step)
                    if not step["protocol_verified"]:
                        break
            channels = self._channels()
            actual = {field: bool(channels[key]) if field == "power" else channels[key]
                      for field, key in CHANNEL_FIELDS["arm"].items() if field in changes}
            expected = {field: max(25, value) if field == "brightness" else value for field, value in changes.items()}
            matched = all(step["candidate_readback_matched"] for step in steps) and actual == expected
            head_preserved = (all(step["other_channel_preserved"] for step in steps)
                              and all(channels[key] == before[key] for key in CHANNEL_FIELDS["head"].values()))
            protocol_verified = len(steps) == len(changes) and matched and head_preserved and all(step["protocol_verified"] for step in steps)
            message = "协议字段回读匹配，主灯字段保持；物理目视验证待完成" if protocol_verified else "侧灯协议核验失败：请求值未保持或其他通道字段发生变化"
            self.event("实验侧灯写入", "info" if protocol_verified else "error", f"{message}；请求={changes}；实际={actual}")
            result = self.snapshot()
            result.update({
                "ok": protocol_verified, "experimental": True, "protocol_verified": protocol_verified,
                "candidate_readback_matched": matched, "head_fields_preserved": head_preserved,
                "requested": dict(changes), "actual": actual,
                "brightness_clamped": "brightness" in changes and changes["brightness"] < 25 and actual["brightness"] == 25,
                "steps": steps, "verified": False, "message": message,
            })
            return result

    def _write_verified(self, field, value):
        for attempt in range(3):
            self.lamp.write(field, value)
            time.sleep(0.12 + attempt * 0.08)
            actual = self._read()
            if same_value(field, actual[field], value):
                self.verified_fields.add(field)
                return
        raise VerificationError(f"{self.field_name(field)}未达到请求值；当前设备回报：{self.state[field]}")

    @staticmethod
    def field_name(field: str) -> str:
        return {"power": "开关", "brightness": "亮度", "color_temp": "色温"}[field]

    def scene(self, scene_id: str) -> dict:
        scene = next((item for item in SCENES if item["id"] == scene_id), None)
        if scene is None:
            raise ValueError("未找到这个本地场景")
        return self.control({"power": True, "brightness": round(scene["brightness_pct"] * 255 / 100), "color_temp": scene["color_temp"]}, "场景：" + scene["name"])

    def restore(self) -> dict:
        self.require_write()
        with self.lock:
            if self.initial_state is None:
                raise ValueError("还没有可恢复的启动状态")
            baseline = self.initial_state.get("experimental_channels")
            if not baseline:
                self.cancel_timer(log=False)
                return self.control({field: self.initial_state[field] for field in ("power", "brightness", "color_temp")}, "恢复启动时状态")
            if not getattr(self.lamp, "experimental_side_light", False):
                raise LampError("Experimental channel support is required to restore the saved channels")
            order = []
            for channel, field in (("head", "brightness"), ("head", "color_temp"), ("arm", "brightness"), ("head", "power"), ("arm", "power")):
                key = CHANNEL_FIELDS[channel][field]
                if key not in baseline or (field == "power" and baseline[key] not in (0, 1)):
                    raise VerificationError("启动基线缺少可恢复的通道字段")
                value = bool(baseline[key]) if field == "power" else baseline[key]
                (build_head_body if channel == "head" else build_channel_body)({field: value})
                order.append((channel, field, value))
            self.cancel_timer(log=False)
            try:
                self._read()
                for channel, field, value in order:
                    self._write_channel_verified(channel, field, value)
                channels = self._channels()
                if any(channels[key] != baseline[key] for fields in CHANNEL_FIELDS.values() for key in fields.values()):
                    raise VerificationError("恢复后通道字段与完整启动基线不一致")
                if any(self.state[field] != self.initial_state[field] for field in ("power", "brightness", "color_temp")):
                    raise VerificationError("恢复后总状态与启动基线不一致")
                self.event("恢复启动时状态", "success", "主灯和侧灯全部协议字段已恢复启动基线")
            except (LampError, OSError) as error:
                self.event("恢复启动时状态", "error", str(error))
                raise
            result = self.snapshot()
            result.update({"verified": True, "protocol_verified": True, "channels_restored": True})
            return result

    def set_timer(self, minutes: int) -> dict:
        self.require_write()
        if type(minutes) is not int or not 1 <= minutes <= 120:
            raise ValueError("定时关灯支持1至120分钟")
        with self.lock:
            self.timer_deadline = time.monotonic() + minutes * 60
            self.timer_ends_at = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
            self.event("设置定时关灯", "success", f"{minutes}分钟后；仅本机服务运行期间有效")
            return self.snapshot()

    def cancel_timer(self, log=True) -> dict:
        with self.lock:
            had_timer = self.timer_deadline is not None
            self.timer_deadline = None
            self.timer_ends_at = None
            if log and had_timer:
                self.event("取消定时关灯", "success")
            return self.snapshot()

    def _timer_loop(self):
        while not self._stop.wait(0.25):
            with self.lock:
                if self.timer_deadline is None or time.monotonic() < self.timer_deadline:
                    continue
                self.timer_deadline = None
                self.timer_ends_at = None
                try:
                    self.control({"power": False}, "定时关灯")
                except (LampError, OSError):
                    pass


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, app):
        self.app = app
        super().__init__(address, DemoHandler)


class DemoHandler(BaseHTTPRequestHandler):
    server: DemoServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        LOG.info("HTTP %s", format % args)

    def _valid_host(self) -> bool:
        port = self.server.server_port
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _send(self, status: int, data: bytes, content_type: str):
        # Rejected request bodies must never become another request on this connection.
        self.close_connection = True
        self.send_response(status)
        self.send_header("Connection", "close")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, status: int, value: dict):
        self._send(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._valid_host():
            return self._json(403, {"ok": False, "message": "只接受本机地址访问"})
        path = urlsplit(self.path).path
        if path == "/api/status":
            return self._json(200, self.server.app.snapshot(refresh=self.command != "HEAD"))
        if path == "/api/health":
            return self._json(200, {"ok": True, "service": "欧普台灯本地Demo"})
        assets = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8")}
        if path not in assets:
            return self._json(404, {"ok": False, "message": "页面或接口不存在"})
        filename, content_type = assets[path]
        try:
            data = (STATIC / filename).read_bytes()
        except FileNotFoundError:
            return self._json(503, {"ok": False, "message": "页面资源正在准备"})
        self._send(200, data, content_type)

    def do_POST(self):
        self._mutate()

    def do_DELETE(self):
        self._mutate()

    def _mutate(self):
        port = self.server.server_port
        allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        if not self._valid_host() or self.headers.get("Origin") not in allowed_origins | {None}:
            return self._json(403, {"ok": False, "message": "控制请求必须来自本机页面"})
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 2048:
                raise ValueError("请求内容过大")
            if self.command == "POST" and self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise ValueError("控制请求需要JSON格式")
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("控制请求需要JSON对象")
            app = self.server.app
            if path == "/api/control" and self.command == "POST":
                result = app.control(payload)
            elif path == "/api/experimental/side-light" and self.command == "POST":
                result = app.side_light(payload)
            elif path == "/api/scene" and self.command == "POST":
                if set(payload) != {"id"} or not isinstance(payload["id"], str):
                    raise ValueError("场景请求需要id")
                result = app.scene(payload["id"])
            elif path == "/api/restore" and self.command == "POST":
                if payload:
                    raise ValueError("恢复接口不接受其他参数")
                result = app.restore()
            elif path == "/api/timer" and self.command == "POST":
                if set(payload) != {"minutes"}:
                    raise ValueError("定时请求需要minutes")
                result = app.set_timer(payload["minutes"])
            elif path == "/api/timer" and self.command == "DELETE":
                result = app.cancel_timer()
            else:
                return self._json(404, {"ok": False, "message": "控制接口不存在"})
            self._json(200 if result.get("ok", True) else 409, result)
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"ok": False, "message": str(error)})
        except VerificationError as error:
            self._json(409, {**self.server.app.snapshot(), "ok": False, "verified": False, "message": str(error)})
        except (LampError, OSError) as error:
            self._json(503, {**self.server.app.snapshot(), "ok": False, "verified": False, "message": str(error)})


def serve(lamp, port: int = 8765):
    app = LampApplication(lamp)
    try:
        server = DemoServer(("127.0.0.1", port), app)
    except OSError:
        app.close()
        raise
    app.snapshot(refresh=True)
    LOG.info("Demo: http://127.0.0.1:%d/ | read_only=%s | simulated=%s", port, app.read_only, app.simulated)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()
