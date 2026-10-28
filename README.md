# OPPLE MT428 Local

[简体中文](README.zh-CN.md)

Local control for the **OPPLE MT428-D0.5×36+0.2×21-WTT Huawei HiLink desk lamp**, with device discovery, command-line status queries, and a browser control panel. Once the lamp is connected to Wi-Fi, the tool communicates over local UDP without requiring Huawei or OPPLE cloud account credentials.

![Web control panel in simulation mode](docs/images/demo-simulation.png)

## Features

- Light power, main-light brightness, and 2700–6500 K color temperature.
- Independent side-light power and brightness through the experimental channel option.
- Status refresh, local presets, an off timer, and session-state restore.
- LAN discovery using an explicit interface broadcast or a known device IP.
- Simulation mode that works without a physical lamp.

## Requirements and setup

- **Python 3.10 or newer**, with no third-party runtime dependencies.
- A lamp already provisioned on 2.4 GHz Wi-Fi and reachable from your computer.

```sh
git clone https://github.com/youli-naixu/opple-mt428-local.git
cd opple-mt428-local
```

Run the commands below from the repository root. Alternatively, install with `python -m pip install .` and use `opple-mt428` instead of `python -m opple_mt428`.

## Usage

### 1. Discover the lamp

Find **your computer's LAN IPv4 address and prefix** using `ipconfig` on Windows, `ip -4 address` on Linux, or your system's network settings:

```sh
python -m opple_mt428 discover --interface 192.0.2.10/24 --json
```

If the router's DHCP lease table already provides the lamp IP, discover that address directly:

```sh
python -m opple_mt428 discover --target 192.0.2.42 --json
```

Results include the IP, MAC, and SKU. Check the device identity before using those values in subsequent commands. Discovery does not change the light.

**The `192.0.2.*` addresses and `02:00:00:00:00:01` MAC are placeholders. Replace them with your own interface or lamp details.** For multiple adapters, VPNs, or discovery failures, see [discovery and troubleshooting](docs/discovery.md).

### 2. Read status

```sh
python -m opple_mt428 status --ip 192.0.2.42 --mac 02:00:00:00:00:01
```

### 3. Open the web control panel

Enable real controls and dedicated main/side channels:

```sh
python -m opple_mt428 serve --ip 192.0.2.42 --mac 02:00:00:00:00:01 --allow-write --experimental-side-light
```

Open **http://127.0.0.1:8765/**. Sliders change the preview only; click Apply to send a command. Side-light controls have their own panel.

To display real state without allowing light changes, omit `--allow-write`:

```sh
python -m opple_mt428 serve --ip 192.0.2.42 --mac 02:00:00:00:00:01 --experimental-side-light
```

Hardware mode is read-only by default. `--experimental-side-light` enables dedicated channel support but does not grant write access on its own. Use `--port 8766` to change the HTTP port. Press `Ctrl+C` to stop the service.

### 4. Preview without hardware

```sh
python -m opple_mt428 serve --simulate --experimental-side-light
```

Simulation changes in-memory state only and does not connect to a real lamp.

## Notes and limitations

- Supported target: the full model above, SKU `0x50061`. Other MT428 variants or firmware are not guaranteed compatible. Side-light support remains experimental; check the physical result when using it.
- Overall power means at least one channel is on. Main and side states are displayed separately. Brightness percentages are converted from raw values and may differ from the official app's scale.
- The dedicated-channel UI uses 10–100% main brightness and raw25–255 side brightness. Parameter changes can alter the light; the legacy path may briefly power on an off lamp while applying parameters.
- Timers run in the current computer process. Sleep, exit, or restart may affect execution. Restore covers only known fields saved when the current service session started.
- Wi-Fi provisioning, firmware updates, vendor-native modes, device-stored schedules, Pomodoro, and indicator settings are not provided.
- HTTP listens on loopback only. See the [HTTP API](docs/api.md) for client usage; do not expose this server directly to the Internet. Remove real IPs, MACs, device names, and account information before sharing logs.

## Sources and acknowledgments

| Source | Used for |
| --- | --- |
| [jedmeng/python-oppleio](https://github.com/jedmeng/python-oppleio) | OPPLE local UDP framing and basic control implementation |
| [tinysnake/python-oppleio-legacy](https://github.com/tinysnake/python-oppleio-legacy) | Legacy OPPLE local-control library |
| [Home Assistant Opple](https://www.home-assistant.io/integrations/opple/) | Existing local integration and usage documentation |
| [Huawei model table](https://consumer.huawei.com/cn/support/content/zh-cn15885815/) and [feature guide](https://consumer.huawei.com/cn/support/content/zh-cn13251283/) | Full-model identification and main/side-light app features |
| [OPPLE official download center](https://www.opple.com.cn/news/download/) | Distribution entry for OPPLE Smart Lighting, a source for dedicated-channel interface details |

Additional links are listed in the [source index](docs/sources.md). Attribution and license-file differences are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No vendor APK, SDK, firmware, or extracted assets are distributed.

## License

[Apache-2.0](LICENSE), with attribution retained in [NOTICE](NOTICE). This project is not affiliated with or endorsed by OPPLE, Huawei, or the referenced brands.
