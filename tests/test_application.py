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
        with patch("socket.socket", side_effect=AssertionError("Device socket was attempted")):
            for experimental in (False, True):
                app = self.make_app(experimental_side_light=experimental)
                result = app.control({"power": True, "brightness": 128, "color_temp": 4000})
                self.assertTrue(result["simulated"])
                self.assertTrue(result["verified"])
                if experimental:
                    self.assertTrue(app.side_light({"power": True, "brightness": 10})["protocol_verified"])
                self.assertTrue(app.restore()["verified"])

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

    def test_side_light_combination_sends_brightness_then_power_with_each_query(self):
        app = self.make_app(experimental_side_light=True)
        calls = []
        original_write, original_query = app.lamp.write_side_light, app.lamp.query
        def write(changes):
            calls.append(("write", dict(changes)))
            original_write(changes)
        def query():
            calls.append(("query",))
            return original_query()
        app.lamp.write_side_light, app.lamp.query = write, query
        result = app.side_light({"power": True, "brightness": 123})
        self.assertEqual(calls, [("query",), ("write", {"brightness": 123}), ("query",), ("write", {"power": True}), ("query",)])
        self.assertTrue(result["protocol_verified"])
        self.assertTrue(result["candidate_readback_matched"])
        self.assertTrue(result["head_fields_preserved"])
        self.assertFalse(result["verified"])
        self.assertTrue(result["state"]["power"])
        self.assertEqual(result["state"]["experimental_channels"]["head_power_raw"], 0)
        self.assertEqual(result["requested"], {"power": True, "brightness": 123})
        self.assertEqual(result["actual"], result["requested"])

    def test_side_light_reports_requested_actual_and_firmware_clamp(self):
        app = self.make_app(experimental_side_light=True)
        for requested in (10, 20, 24, 25, 255):
            with self.subTest(requested=requested):
                result = app.side_light({"brightness": requested})
                self.assertTrue(result["protocol_verified"])
                self.assertTrue(result["candidate_readback_matched"])
                self.assertTrue(result["head_fields_preserved"])
                self.assertFalse(result["verified"])
                self.assertEqual(result["requested"], {"brightness": requested})
                self.assertEqual(result["actual"], {"brightness": max(25, requested)})
                self.assertEqual(result["brightness_clamped"], requested < 25)
                self.assertEqual(result["steps"][0]["requested"], requested)
                self.assertEqual(result["steps"][0]["actual"], max(25, requested))

    def test_side_light_head_corruption_fails_and_stops_the_sequence(self):
        for key, value in (("head_power_raw", 1), ("head_brightness_raw", 51), ("head_color_temp_raw", 3000)):
            with self.subTest(key=key):
                app = self.make_app(experimental_side_light=True)
                original = app.lamp.write_side_light
                def corrupt(changes):
                    original(changes)
                    app.lamp.arm[key] = value
                with patch.object(app.lamp, "write_side_light", side_effect=corrupt) as writer:
                    result = app.side_light({"power": True, "brightness": 178})
                writer.assert_called_once_with({"brightness": 178})
                self.assertFalse(result["ok"])
                self.assertFalse(result["protocol_verified"])
                self.assertFalse(result["head_fields_preserved"])
                self.assertFalse(result["verified"])
                self.assertEqual(result["state"]["experimental_channels"]["arm_power_raw"], 0)

    def test_side_light_ignored_write_is_a_failure(self):
        app = self.make_app(experimental_side_light=True)
        with patch.object(app.lamp, "write_side_light") as writer:
            result = app.side_light({"power": True, "brightness": 178})
        writer.assert_called_once_with({"brightness": 178})
        self.assertFalse(result["ok"])
        self.assertFalse(result["candidate_readback_matched"])
        self.assertFalse(result["protocol_verified"])
        self.assertTrue(result["head_fields_preserved"])

    def test_side_light_power_must_preserve_previously_written_brightness(self):
        app = self.make_app(experimental_side_light=True)
        original = app.lamp.write_side_light
        def corrupt(changes):
            original(changes)
            if "power" in changes:
                app.lamp.arm["arm_brightness_raw"] = 51
        app.lamp.write_side_light = corrupt
        result = app.side_light({"power": True, "brightness": 178})
        self.assertFalse(result["ok"])
        self.assertFalse(result["protocol_verified"])
        self.assertFalse(result["candidate_readback_matched"])
        self.assertTrue(result["head_fields_preserved"])
        self.assertEqual(result["actual"]["brightness"], 51)

    def test_side_light_validates_all_fields_before_any_write(self):
        app = self.make_app(experimental_side_light=True)
        with patch.object(app.lamp, "write_side_light") as writer, patch.object(app.lamp, "query") as query:
            for changes in ({}, {"power": True, "brightness": 9}, {"power": 1}, {"brightness": True}, {"color_temp": 4000}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    app.side_light(changes)
        writer.assert_not_called()
        query.assert_not_called()

    def test_main_apply_opens_head_while_side_is_already_on(self):
        app = self.make_app(experimental_side_light=True)
        app.lamp.write_side_light({"power": True})
        app.lamp.write_side_light({"brightness": 178})
        before = app.lamp.query()["experimental_channels"]
        with patch.object(app.lamp, "write", side_effect=AssertionError("legacy write")), patch.object(app.lamp, "write_head", wraps=app.lamp.write_head) as head, patch.object(app.lamp, "query", wraps=app.lamp.query) as query:
            result = app.control({"power": True, "brightness": 51, "color_temp": 3000})
        self.assertEqual([call.args[0] for call in head.call_args_list], [{"brightness": 51}, {"color_temp": 3000}, {"power": True}])
        self.assertEqual(query.call_count, 4)
        channels = result["state"]["experimental_channels"]
        self.assertTrue(result["state"]["power"])
        self.assertEqual(channels["head_power_raw"], 1)
        self.assertEqual(channels["head_brightness_raw"], 51)
        self.assertEqual(channels["head_color_temp_raw"], 3000)
        for key in ("arm_power_raw", "arm_brightness_raw"):
            self.assertEqual(channels[key], before[key])

    def test_main_parameters_while_head_is_off_do_not_touch_either_power(self):
        for side_on in (False, True):
            with self.subTest(side_on=side_on):
                app = self.make_app(experimental_side_light=True)
                app.lamp.write_side_light({"power": side_on})
                with patch.object(app.lamp, "write", side_effect=AssertionError("legacy write")), patch.object(app.lamp, "write_head", wraps=app.lamp.write_head) as head, patch.object(app.lamp, "write_side_light", side_effect=AssertionError("side write")):
                    result = app.control({"brightness": 51, "color_temp": 3000})
                self.assertEqual([call.args[0] for call in head.call_args_list], [{"brightness": 51}, {"color_temp": 3000}])
                channels = result["state"]["experimental_channels"]
                self.assertEqual(channels["head_power_raw"], 0)
                self.assertEqual(channels["arm_power_raw"], int(side_on))
                self.assertEqual(channels["arm_brightness_raw"], 102)
                self.assertEqual(result["state"]["power"], side_on)
                self.assertEqual(result["state"]["brightness"], 51)
                self.assertEqual(result["state"]["color_temp"], 3000)

    def test_main_apply_checks_head_power_even_when_overall_power_is_on(self):
        app = self.make_app(experimental_side_light=True)
        app.lamp.write_side_light({"power": True})
        original = app.lamp.write_head
        app.lamp.write_head = lambda changes: original(changes) if "power" not in changes else None
        with self.assertRaises(VerificationError):
            app.control({"power": True, "brightness": 51})
        self.assertTrue(app.state["power"])
        self.assertEqual(app.state["experimental_channels"]["head_power_raw"], 0)

    def test_head_write_that_changes_side_is_not_reported_success(self):
        app = self.make_app(experimental_side_light=True)
        original = app.lamp.write_head
        def corrupt(changes):
            original(changes)
            app.lamp.arm["arm_brightness_raw"] = 178
        app.lamp.write_head = corrupt
        with self.assertRaises(VerificationError):
            app.control({"brightness": 51})
        self.assertNotIn("brightness", app.verified_fields)

    def test_power_only_keeps_legacy_overall_semantics_without_assuming_head_on(self):
        app = self.make_app(experimental_side_light=True)
        def legacy(field, value):
            self.assertEqual(field, "power")
            app.lamp.arm["arm_power_raw"] = int(value)
            app.lamp.arm["head_power_raw"] = 0
        with patch.object(app.lamp, "write", side_effect=legacy) as writer, patch.object(app.lamp, "write_head", side_effect=AssertionError("dedicated head power")):
            on = app.control({"power": True})
            off = app.control({"power": False})
        self.assertEqual([call.args for call in writer.call_args_list], [("power", True), ("power", False)])
        self.assertTrue(on["state"]["power"])
        self.assertEqual(on["state"]["experimental_channels"]["head_power_raw"], 0)
        self.assertFalse(off["state"]["power"])

    def test_restore_recovers_all_channel_fields_for_each_power_baseline(self):
        for head_on, arm_on in ((0, 0), (0, 1), (1, 0), (1, 1)):
            with self.subTest(head_on=head_on, arm_on=arm_on):
                lamp = SimulatedLamp(experimental_side_light=True)
                lamp.arm.update({"head_power_raw": head_on, "arm_power_raw": arm_on, "head_brightness_raw": 51, "head_color_temp_raw": 3000, "arm_brightness_raw": 178})
                app = LampApplication(lamp)
                self.addCleanup(app.close)
                initial = app.snapshot(refresh=True)["initial_state"]
                lamp.arm.update({"head_power_raw": 1 - head_on, "arm_power_raw": 1 - arm_on, "head_brightness_raw": 200, "head_color_temp_raw": 5000, "arm_brightness_raw": 25})
                app.set_timer(1)
                with patch.object(lamp, "write", side_effect=AssertionError("global POWER breaks independent states")), patch.object(lamp, "write_head", wraps=lamp.write_head) as head, patch.object(lamp, "write_side_light", wraps=lamp.write_side_light) as side:
                    restored = app.restore()
                self.assertTrue(restored["protocol_verified"])
                self.assertTrue(restored["channels_restored"])
                self.assertEqual(restored["state"]["experimental_channels"], initial["experimental_channels"])
                for field in ("power", "brightness", "color_temp"):
                    self.assertEqual(restored["state"][field], initial[field])
                self.assertEqual([call.args[0] for call in head.call_args_list], [{"brightness": 51}, {"color_temp": 3000}, {"power": bool(head_on)}])
                self.assertEqual([call.args[0] for call in side.call_args_list], [{"brightness": 178}, {"power": bool(arm_on)}])
                self.assertIsNone(app.timer_deadline)

    def test_restore_ignored_channel_write_fails(self):
        app = self.make_app(experimental_side_light=True)
        app.lamp.arm["arm_brightness_raw"] = 178
        with patch.object(app.lamp, "write_side_light"):
            with self.assertRaises(VerificationError):
                app.restore()

    def test_channel_baseline_and_snapshots_do_not_alias_mutable_state(self):
        app = self.make_app(experimental_side_light=True)
        snapshot = app.snapshot()
        snapshot["initial_state"]["experimental_channels"]["arm_brightness_raw"] = 255
        snapshot["state"]["experimental_channels"]["head_power_raw"] = 1
        self.assertEqual(app.initial_state["experimental_channels"]["arm_brightness_raw"], 102)
        self.assertEqual(app.state["experimental_channels"]["head_power_raw"], 0)

    def test_simulator_power_is_or_and_legacy_side_brightness_does_not_change_head(self):
        lamp = SimulatedLamp(experimental_side_light=True)
        for head, arm in ((0, 0), (0, 1), (1, 0), (1, 1)):
            lamp.arm.update({"head_power_raw": head, "arm_power_raw": arm})
            self.assertEqual(lamp.query()["power"], bool(head or arm))
        lamp.arm.update({"head_power_raw": 0, "arm_power_raw": 1})
        lamp.write("brightness", 51)
        state = lamp.query()
        self.assertEqual(state["brightness"], 102)
        self.assertEqual(state["experimental_channels"]["arm_brightness_raw"], 51)
        lamp.write_head({"brightness": 178})
        self.assertEqual(lamp.query()["brightness"], 178)
        self.assertEqual(lamp.arm["head_power_raw"], 0)

    def test_simulator_blocks_read_only_and_combined_channel_writes(self):
        readonly = SimulatedLamp(read_only=True, experimental_side_light=True)
        baseline = dict(readonly.arm)
        for action in (lambda: readonly.write("power", True), lambda: readonly.write_side_light({"power": True}), lambda: readonly.write_head({"brightness": 51})):
            with self.assertRaises(LampError):
                action()
        self.assertEqual(readonly.arm, baseline)
        lamp = SimulatedLamp(experimental_side_light=True)
        for writer in (lamp.write_side_light, lamp.write_head):
            with self.assertRaises(ValueError):
                writer({"power": True, "brightness": 51})
        self.assertEqual(lamp.arm, baseline)
        disabled = SimulatedLamp()
        with self.assertRaises(LampError):
            disabled.write_head({"power": True})

    def test_side_light_requires_explicit_experimental_flag(self):
        app = self.make_app()
        with self.assertRaises(LampError):
            app.side_light({"power": True})

    def test_timer_expiry_turns_off_and_clears(self):
        app = self.make_app()
        app.lamp.write("power", True)
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
