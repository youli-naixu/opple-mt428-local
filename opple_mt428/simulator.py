# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 youli-naixu and contributors

from .protocol import MODEL, LampError, build_channel_body, now_iso


class SimulatedLamp:
    """In-memory demonstration; creates no UDP socket and cannot reach hardware."""

    def __init__(self, *, read_only=False, experimental_side_light=False):
        self.read_only = read_only
        self.simulated = True
        self.experimental_side_light = experimental_side_light
        self.state = {"power": False, "brightness": 102, "color_temp": 4000}
        self.arm = {"arm_power_raw": 0, "arm_brightness_raw": 102, "head_power_raw": 0, "head_brightness_raw": 102, "head_color_temp_raw": 4000}

    def close(self):
        pass

    def query(self):
        state = {**self.state, "brightness_pct": round(self.state["brightness"] * 100 / 255, 1), "observed_at": now_iso()}
        if self.experimental_side_light:
            state["experimental_channels"] = {**self.arm, "evidence": "simulation-only"}
        return state

    def write(self, field, value):
        if self.read_only:
            raise LampError("Read-only simulation")
        if field == "power" or self.state["power"]:
            self.state[field] = value

    def write_side_light(self, changes):
        if self.read_only or not self.experimental_side_light:
            raise LampError("Experimental writes are disabled")
        build_channel_body(changes)
        if "power" in changes:
            self.arm["arm_power_raw"] = int(changes["power"])
        if "brightness" in changes:
            self.arm["arm_brightness_raw"] = changes["brightness"]

    @property
    def identity(self):
        return {"name": "模拟台灯 / Simulated lamp", "model": MODEL, "ip": "192.0.2.42", "mac": "02:00:00:00:00:01", "port": 55001, "sku": "0x50061", "version": "simulated", "transport": "simulation (no hardware)"}
