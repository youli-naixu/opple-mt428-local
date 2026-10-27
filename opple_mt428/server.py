# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 youli-naixu and contributors

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .protocol import LampError, now_iso


LOG = logging.getLogger("opple.demo")
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
            self.state = self.lamp.query()
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
            self.initial_state = dict(self.state)
            self.event("已保存本次启动时状态", "info", "恢复按钮仅恢复本次服务启动后首次读到的状态")
        if was_offline:
            self.event("已连接台灯", "success", "本地发现与状态查询校验通过")
        return self.state

    def capabilities(self):
        items = [
            {"id": "status", "title": "实时状态", "status": "verified" if self.state else "available", "description": "从台灯直接读取，显示最近一次更新时间"},
            {"id": "power", "title": "灯光开关", "description": "本地开关命令与状态回读已实现；侧灯联动尚未目视确认"},
            {"id": "brightness", "title": "主灯亮度", "description": "本地协议0–255级；面板以百分比显示"},
            {"id": "color_temp", "title": "主灯色温", "description": "按本地库2700–6500 K范围请求，以设备回报为准"},
            {"id": "scene", "title": "本地光线场景", "status": "available", "description": "本页组合亮度与色温，不调用原厂模式"},
            {"id": "timer", "title": "定时关灯", "status": "available", "description": "由本机服务计时；关闭服务或重启后取消"},
            {"id": "restore", "title": "恢复启动时状态", "status": "available", "description": "恢复本次服务首次读取到的开关、亮度和色温"},
            {"id": "side_light", "title": "侧灯／副灯（实验性）", "status": "experimental", "description": "已定位SKU专用灯臂协议；尚未实机验证，需显式启用实验支持"},
            {"id": "native_reading", "title": "原厂阅读／书写", "status": "unadapted", "description": "官方App分别4000／5000 K，并包含侧灯联动；本页场景只组合已适配参数"},
            {"id": "native_computer", "title": "原厂电脑模式", "status": "unadapted", "description": "仅侧灯照明；缺少独立侧灯协议，暂不能复现"},
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
                "state": dict(self.state) if self.state is not None else None,
                "initial_state": dict(self.initial_state) if self.initial_state is not None else None,
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

    def require_write(self):
        if self.read_only:
            raise LampError("只读模式禁止改变灯光 / Read-only mode blocks light changes")

    def side_light(self, changes: dict) -> dict:
        self.require_write()
        if not getattr(self.lamp, "experimental_side_light", False):
            raise LampError("Experimental side-light support is disabled")
        from .protocol import build_channel_body
        build_channel_body(changes)
        with self.lock:
            before = self._read()
            if not before.get("experimental_channels"):
                raise LampError("No candidate channel state is available")
            self.lamp.write_side_light(changes)
            time.sleep(0.2)
            state = self._read()
            channels = state.get("experimental_channels") or {}
            expected = {"arm_power_raw": int(changes["power"])} if "power" in changes else {}
            if "brightness" in changes:
                expected["arm_brightness_raw"] = changes["brightness"]
            matched = all(channels.get(key) == value for key, value in expected.items())
            self.event("实验侧灯写入", "info" if matched else "error", "候选字段已匹配，需目视确认" if matched else "候选字段未匹配")
            result = self.snapshot()
            result.update({"experimental": True, "candidate_readback_matched": matched, "verified": False, "message": "仅候选字段回读，需确认物理侧灯与其他光源未受影响"})
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
        with self.lock:
            if self.initial_state is None:
                raise ValueError("还没有可恢复的启动状态")
            self.cancel_timer(log=False)
            return self.control({field: self.initial_state[field] for field in ("power", "brightness", "color_temp")}, "恢复启动时状态")

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
            self._json(200, result)
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
