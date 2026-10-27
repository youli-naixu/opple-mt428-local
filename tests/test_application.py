import json
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from opple_mt428.protocol import LampError
from opple_mt428.server import DemoServer, LampApplication, VerificationError, validate_control
from opple_mt428.simulator import SimulatedLamp


class ApplicationTests(unittest.TestCase):
    def make_app(self, **kwargs):
        app = LampApplication(SimulatedLamp(**kwargs))
        self.addCleanup(app.close)
        app.snapshot(refresh=True)
        return app

    def test_simulation_never_creates_device_socket(self):
        with patch("socket.socket", side_effect=AssertionError("UDP socket was attempted")):
            app = self.make_app()
            result = app.control({"power": True, "brightness": 128, "color_temp": 4000})
        self.assertTrue(result["simulated"])
        self.assertTrue(result["verified"])

    def test_read_only_blocks_control_restore_scene_timer_and_side_light(self):
        app = self.make_app(read_only=True, experimental_side_light=True)
        for action in (lambda: app.control({"power": True}), app.restore, lambda: app.scene("reading"), lambda: app.set_timer(1), lambda: app.side_light({"power": True})):
            with self.assertRaises(LampError):
                action()
        self.assertFalse(app.lamp.state["power"])
        self.assertIsNone(app.timer_deadline)

    def test_off_state_parameter_change_returns_to_off(self):
        app = self.make_app()
        result = app.control({"brightness": 51, "color_temp": 3000})
        self.assertFalse(result["state"]["power"])
        self.assertEqual(result["state"]["brightness"], 51)
        self.assertEqual(result["state"]["color_temp"], 3000)
        restored = app.restore()
        self.assertFalse(restored["state"]["power"])
        self.assertEqual(restored["state"]["color_temp"], 4000)

    def test_ignored_write_is_not_reported_success(self):
        app = self.make_app()
        original = app.lamp.write
        app.lamp.write = lambda field, value: original(field, value) if field != "brightness" else None
        with self.assertRaises(VerificationError):
            app.control({"brightness": 200})
        self.assertFalse(app.lamp.state["power"])
        self.assertNotIn("brightness", app.verified_fields)

    def test_temporary_power_is_reverted_when_on_readback_fails(self):
        app = self.make_app()
        original_query = app.lamp.query
        writes = []
        original_write = app.lamp.write
        def write(field, value):
            writes.append((field, value))
            original_write(field, value)
        def query():
            if writes and writes[-1] == ("power", True):
                raise LampError("simulated lost ON readback")
            return original_query()
        app.lamp.write, app.lamp.query = write, query
        with self.assertRaises(LampError):
            app.control({"brightness": 200})
        self.assertEqual(writes, [("power", True), ("power", False)])
        self.assertFalse(app.lamp.state["power"])

    def test_rejected_body_cannot_become_second_control_request(self):
        app = self.make_app()
        server = DemoServer(("127.0.0.1", 0), app)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        host = f"127.0.0.1:{server.server_port}"
        inner = (f'POST /api/control HTTP/1.1\r\nHost: {host}\r\nContent-Type: application/json\r\nContent-Length: 14\r\n\r\n' + '{"power":true}').encode()
        outer = f'POST /api/control HTTP/1.1\r\nHost: {host}\r\nOrigin: https://unrelated.example\r\nContent-Type: text/plain\r\nContent-Length: {len(inner)}\r\n\r\n'.encode() + inner
        with socket.create_connection(("127.0.0.1", server.server_port), timeout=3) as client:
            client.sendall(outer)
            received = b""
            while True:
                try:
                    chunk = client.recv(4096)
                except ConnectionResetError:
                    break
                if not chunk:
                    break
                received += chunk
        self.assertIn(b"403", received)
        self.assertNotIn(b"200 OK", received)
        self.assertFalse(app.lamp.state["power"])

    def test_side_light_is_single_shot_and_never_hardware_verified(self):
        app = self.make_app(experimental_side_light=True)
        with patch.object(app.lamp, "write_side_light", wraps=app.lamp.write_side_light) as writer:
            result = app.side_light({"power": True, "brightness": 123})
        writer.assert_called_once()
        self.assertTrue(result["candidate_readback_matched"])
        self.assertFalse(result["verified"])
        self.assertFalse(result["state"]["power"])

    def test_side_light_requires_explicit_experimental_flag(self):
        app = self.make_app()
        with self.assertRaises(LampError):
            app.side_light({"power": True})

    def test_timer_expiry_turns_off_and_clears(self):
        app = self.make_app()
        app.lamp.state["power"] = True
        app.set_timer(1)
        with app.lock:
            app.timer_deadline = time.monotonic() - 1
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with app.lock:
                if app.timer_deadline is None and not app.lamp.state["power"]:
                    break
            time.sleep(0.02)
        self.assertFalse(app.lamp.state["power"])
        self.assertIsNone(app.timer_deadline)

    def test_validation_rejects_unknown_and_wrong_types(self):
        for payload in ({}, {"reset": True}, {"brightness": True}, {"power": 1}, {"color_temp": 2600}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_control(payload)

    def test_http_cross_origin_and_read_only_are_enforced(self):
        app = self.make_app(read_only=True)
        server = DemoServer(("127.0.0.1", 0), app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        for origin, expected in (("https://unrelated.example", 403), (base, 503)):
            request = urllib.request.Request(base + "/api/control", data=b'{"power":true}', headers={"Content-Type": "application/json", "Origin": origin})
            with self.assertRaises(urllib.error.HTTPError) as result:
                urllib.request.urlopen(request)
            with result.exception as response:
                self.assertEqual(response.code, expected)
                self.assertFalse(json.load(response)["ok"])
        self.assertFalse(app.lamp.state["power"])


if __name__ == "__main__":
    unittest.main()
