# Opple MT428 local protocol research and evidence boundaries

[简体中文](research.zh-CN.md) · [Architecture](architecture.en.md)

Updated on 2026-10-28 for **MT428-D0.5×36+0.2×21-WTT**, including authorized daytime channel tests. This document summarizes saved device-test records, maintainer-supplied follow-up results, and public references. Preparing it did not involve connecting to the lamp or API, sending packets, signing into private accounts, or repeating hardware tests. Findings apply to one tested device and its firmware at the time, not to every MT428, HiLink, or Opple product. Channel adapter changes are documented under Unreleased; the published alpha's history is unchanged.

Every example lamp address is `192.0.2.42`, and every example device MAC is `02:00:00:00:00:01`. The address belongs to the **TEST-NET-1 documentation range** in RFC 5737; the MAC is an invented, locally administered unicast address. Replace both with the address and MAC of an authorized device before deployment; they cannot validate a real lamp.[N4] Real device identifiers, user networks, cloud addresses, account material, and raw packets are excluded. `238.238.238.238:5683` is an observed protocol multicast constant, explained in section 6, rather than the example lamp address.

## 1. Reading the evidence

| Tag | Evidence level | What it supports and its limits |
| --- | --- | --- |
| T | Device-tested protocol evidence | Responses, write/readback transitions, or controlled behavior in existing records. Channel results mean physical-device protocol write/readback confirmed; visual validation pending. They do not establish emitted light, physical channel mapping, photometry, or brightness calibration. |
| S | Public source code | Inspectable implementations, constants, and ranges; code support does not establish compatibility with this model. |
| O | Official documentation | Product features and official operating procedures; these do not directly identify UDP commands. |
| A | Static analysis of an officially distributed APK | SKU branches, UI calls, and protocol fields in the identified App version. The APK is not public source code, and a static path does not establish acceptance or execution by current firmware. |
| H | Hypothesis / proposed design | An explanation or implementation requiring verification, not a compatibility promise. |

Third-party reviews are identified separately as historical corroboration. They provide model and usage clues, not device-test or official evidence. Early records covered discovery and queries only; later records added write tests. The capability boundary below incorporates the later evidence while preserving unverified items.

## 2. Known capabilities and unverified scope

Discovery reported `CLASS_SKU = 0x50061` and **raw version field `0x210`**. Do not reformat `0x210` as “2.1.0” or assign it an official firmware release. The official model table also lists a different product with the MT428 prefix, so the complete model suffix matters.[H3]

| Capability | Current evidence | Findings and limitations |
| --- | --- | --- |
| UDP unicast discovery and query | T + S | SEARCH and QUERY succeeded on `55001`; records include matching response types, request/response serials, target identity, and CRC. This path did not require cloud account credentials. |
| Power | T + S + A | On/off writes succeeded with readback. Legacy `power@1` is aggregate: either channel on reports true; both off reports false. Dedicated channel power is separate; actual light was not independently observed. |
| Main-light brightness | T + S + A | Legacy writes and dedicated head brightness `51` read back successfully. The byte represents raw `0–255`; percentages are not calibrated against the App slider or illuminance. Not every value was tested. |
| Main-light color temperature | T + S + O + A | Legacy request points include `2700 / 4000 / 5000 / 6500 K`; dedicated head `4000 K` also read back successfully. Adapter range `2700–6500 K` is not spectral calibration or an exhaustive test.[H1] |
| Local scene presets | T | Combinations of supported power, brightness, and color temperature were applied and read back; these are not native reading, writing, computer, or favorite modes. |
| In-process off timer | T | Setting, cancellation, and one actual 1-minute expiry were verified. The service process executes the timer; stopping or restarting it loses the timer. This is not a countdown stored in the lamp. |
| Restore first observed state | T (field restoration); Unreleased adapter | With experimental mode and an initial channel snapshot, restore covers known side power/brightness and head power/brightness/CCT. Otherwise it falls back to legacy three-field restore; unknown initial channel, mode, and schedule state cannot be reconstructed. |
| Independent arm / side light | O + A + T | Single-parameter side power and brightness writes/readback confirmed on one physical unit, including head-field preservation. Observed brightness clamp `10/20 → 25`; visual validation and other-firmware coverage remain pending. See sections 3 and 5. |
| Native modes / favorite | O; local mapping unknown | Officially documented features, without verified local mappings for this model. |
| Native recurring schedules, countdown, Pomodoro | O; local mapping unknown | Local scenes and process timers must not be presented as native implementations. |
| Touch-key indicators, independent “night light” | Historical corroboration / unknown | A review of the complete model provides an indicator-setting clue. An independent night-light feature is not established by the official documentation or local testing for this model.[P2] |
| Internet disconnected, offline provisioning after factory reset, other firmware | Not tested | Using local commands without cloud credentials does not establish a fully offline device lifecycle or compatibility after firmware updates. |
| Persistent router deployment, ESP management page, MCP | H | Future architecture goals described in the architecture document, not completed hardware acceptance tests. |

**Legacy off-state warning:** the tested legacy dimming path needs the compatibility sequence on → apply brightness/CCT → off, so it may illuminate the lamp temporarily. This remains the fallback without experimental channels. Daytime records show that dedicated channel brightness and head CCT can update stored fields with both power fields off, without a protocol power-on step; no independent optical observation establishes darkness throughout. Connection failure can prevent restoration, and any write may have an unknown outcome. The historical nighttime investigation prohibited writes; later authorized daytime tests are a separate stage.

### read-only and simulate

- **read-only (default)**: the real-device path permits targeted SEARCH and QUERY only. It rejects power, brightness, and color-temperature writes, including indirect writes from scenes, restore, and timer expiry. It still sends query traffic; it is neither passive observation nor offline simulation. Disabling UI buttons alone is insufficient: the protocol send layer must enforce the restriction.
- **simulate**: synthetic state and controlled faults exercise parsing, APIs, queueing, timers, and the off-lamp compatibility sequence. It must send no packets to the lamp, multicast group, or cloud services. Results must identify their simulated origin and must not be counted as T-level hardware evidence.
- **Experimental channel gates**: `--experimental-side-light` enables experimental parsing and the dedicated-channel path; real writes also require `--allow-write`. Neither flag alone permits dedicated-channel writes. Enabling a flag is not evidence of compatibility. Single-parameter write/readback is now recorded for one physical unit, but visual validation and firmware-variant coverage remain pending. During the historical nighttime stage, writes were prohibited and only SEARCH/QUERY were sent; separate explicit authorization covered the subsequent daytime tests.

These are the public release's mode and gating contracts. Consult the README and the relevant release's tests for startup details. Neither mode was rerun for this document, and historical prototype test counts are not substituted for the public project's results.

## 3. Reviewable UDP55001 protocol summary

This summary draws on original `pyoppleio`, the legacy branch, and existing device tests.[S1][S2] All offsets are **zero-based**. A “body offset” refers to the decoded application body, not the entire UDP payload. Only commands, fields, and algorithms are listed; raw captures and complete replayable packets are excluded.

### Commands and payloads

| Operation | Message type | Known body semantics |
| --- | --- | --- |
| SEARCH | `0x02010000` | Targeted discovery request, empty body. |
| SEARCH response | `0x02020000` | Identity, SKU, raw version, and communication parameters; not complete lighting state. |
| QUERY | `0x030f0000` | State request, empty body. |
| QUERY response | `0x03100000` | The observed body length for this device is **58 bytes**. |
| POWER | `0x03110000` | One byte: `0` off, `1` on. |
| BRIGHTNESS | `0x03130000` | One raw brightness byte; source code accepts `0–255`. |
| COLOR_TEMP | `0x031b0000` | Two bytes, big-endian, Kelvin; adapter range `2700–6500`. |
| Dedicated channels | `0x03450000` | 10-byte template; change one parameter per payload and QUERY-verify each write, as below. |

The three legacy fields below were the original cross-checked state. Authorized daytime writes now also corroborate channel QUERY offsets `52–57` at the protocol level, with visual validation pending. These remain separately exposed experimental channel fields rather than silently replacing legacy state. Unexplained bytes must not be assigned mode, schedule, clock, or Pomodoro meanings merely because they change.

| Query field | Body offset / slice | Length and meaning |
| --- | --- | --- |
| `power` | `1`, or `[1:2]` | 1 byte, `0 / 1`; aggregate power on this unit, not dedicated head power. |
| `brightness` | `2`, or `[2:3]` | 1 raw-value byte. |
| `cct` | `7`, or `[7:9]` | 2 bytes, big-endian, device-reported color temperature. |

### Framing, discovery, and validation

Public source code defines a fixed header of `0x7c` (124 bytes). The observed 182-byte QUERY response therefore contains a 124-byte header and 58-byte body. The observed SEARCH response is 185 bytes in total; the two response bodies must not be treated interchangeably.

| Field | Frame-header offset | Purpose |
| --- | --- | --- |
| Request serial | `0x64`, 4 bytes | Correlates a request. |
| Response serial | `0x68`, 4 bytes | This device's replies can be matched to the request serial. |
| Message length | `0x6c`, 4 bytes | Validates application message length. |
| Checksum field | `0x70`, 4-byte slot | Stores the CRC16-XMODEM result. |
| Message type | `0x74`, 4 bytes | Distinguishes discovery, query, and control. |
| Body start | `0x7c` | Start of the control/query body to decode. |

Known SEARCH-body offsets include SKU at `0x03` (4 bytes), MAC at `0x09` (read 6 bytes), low protocol device identifier at `0x13` (4 bytes), version at `0x1b` (4 bytes), IPv4 at `0x1f` (4 bytes), and UDP port at `0x23` (2 bytes). Accept only the expected device configured by the operator. These identifiers do not belong in public diagnostic files. The logical API `deviceId` is different from the protocol device identifier returned by discovery.

The source builds plaintext and calculates the CRC before applying MAC-based XOR to an initialized device's body. It repeats the 6-byte MAC and truncates it into a **20-byte mask, then cycles that 20-byte mask**. This is not equivalent to continuously cycling six bytes. On reception, decode according to the known message type, clear the checksum field, and validate CRC16-XMODEM over application data starting at `0x64`. Neither CRC nor this XOR provides trustworthy authentication or secure encryption.[S2b] The old library's parser is not a substitute for complete receive validation: the adapter should also check source address/port, type, length, serial, and discovered identity.

Writes to this device are confirmed by QUERY readback; a successful UDP send is not execution confirmation. Combined controls are not an atomic device transaction and must be able to report partial success or an unknown outcome. Other products that do not echo request serials do not justify disabling serial checks for this device.[S7]

<a id="side-light-static-analysis"></a>

### SKU-specific arm / side-light protocol: static evidence plus device readback

Static analysis of the officially distributed App supplied the mapping.[A1] `SKUUtil.getDeiveTypeBySku` maps `0x50061` to `WifiDesklamp_0061`. The `ArmControl` UI calls `SEND_ARM_OPENCLOSE` and `SEND_ARM_BRIGHT`; the send path uses `SEND_SMARTFUNCTION`, message type **`0x03450000`**, and local UDP55001. Subsequent authorized daytime tests added T-level single-parameter write/readback evidence. This is an independent protocol summary, not decompiled code or a raw packet.

| Control-body field | Offset / slice | Static meaning and recorded device result |
| --- | --- | --- |
| Product / template prefix | `[0:4]` | Four-byte product SKU prefix; template length **10 bytes**. |
| arm/side power | `4` | `0 / 1`; unchanged template value `2`. Off → on → off read back successfully. |
| arm/side brightness | `5` | App raw range `10–255`; unchanged template value `0`. `51/178/102` matched; `10/20` clamped to `25`; `25/255` matched. |
| head power | `6` | `0 / 1`; unchanged template value `2`. Independent single-field transitions read back successfully. |
| head brightness | `7` | Raw brightness; unchanged template value `0`. Request `51` read back successfully. |
| head color temperature | `[8:10]` | Two-byte big-endian; unchanged template value `0`. Request `4000 K` read back successfully. |

With **one parameter changed per payload**, the other App-template values preserved returned channel fields in the recorded tests. Side power/brightness tests preserved head `0 / 28 / 2700 K`; side off/on also preserved an enabled head, and dedicated head writes preserved side fields. This confirms protocol preservation for these cases on one unit. `arm` and `head` remain App-derived names: their emitted light and physical correspondence were not independently observed by eye or instrument.

**Combined-payload limitation:** side power + brightness in one payload caused brightness to be ignored, including an earlier API restoration attempt. The Unreleased backend splits channel requests and restore operations into one parameter per payload, retaining other template values and QUERY-verifying every step. A multi-field HTTP request is not an atomic device transaction. Dedicated head/side brightness and head CCT can update stored values with both channel power fields off; this differs from the historical legacy dimming workaround and does not prove optical darkness.

| QUERY-body field | Decimal offset / slice | Current evidence boundary |
| --- | --- | --- |
| arm/side power | `52` | Static mapping plus single-parameter write/readback on the tested unit. |
| arm/side brightness | `53` | Same; report actual raw value, including the observed clamp to `25`. |
| head power | `54` | Dedicated head state; distinct from aggregate legacy `power@1`. |
| head brightness | `55` | Dedicated readback corroborated; keep separately exposed from legacy brightness. |
| head color temperature | `[56:58]` | Two-byte big-endian; dedicated write/readback corroborated, not a spectrum measurement. |

Legacy `power@1` remains true with only the side on and becomes false with both channels off; it is not head state. Experimental channels remain under `state.experimental_channels`, with evidence describing **physical-device protocol write/readback confirmed; visual validation pending**. Side responses retain `verified:false` and `candidate_readback_matched`, adding `protocol_verified`, `head_fields_preserved`, `requested`, `actual`, and `brightness_clamped`. Both gates remain because other firmware and optical behavior are unverified. See [observations](observations.md) and the [Unreleased API contract](api.md).

With experimental mode enabled, brightness/CCT control uses dedicated head fields; including `power:true` explicitly enables the head. Power-only control retains legacy semantics. Restore covers side power/brightness and head power/brightness/CCT only when the initial channel snapshot is known; missing channel state or a disabled flag uses the original legacy fallback, which cannot reconstruct unknown initial channels.

## 4. Applicability of public implementations

| Source | Useful evidence | Boundary for this model |
| --- | --- | --- |
| Original `jedmeng/python-oppleio` [S1] | UDP control library and power / brightness / color-temperature APIs. | The broad “Wi-Fi lights supported” statement is not a model-specific test. |
| `tinysnake/python-oppleio-legacy` [S2] | Protocol source used by the existing tests; maintenance notes describe limitations with newer Wi-Fi firmware. | The automatic `search()` SKU branch accepts only `0x100010e`, excluding this device's `0x50061`. Initialization with an explicit address bypasses that automatic discovery filter. The source also does not establish that all error handling is sufficient. |
| Home Assistant `opple` [S3] | A `local_polling` integration; the reviewed revision depends on `pyoppleio-legacy==1.0.8` and accepts an explicit `host`. | A reusable integration lead, not a completed end-to-end HA hardware test for this project. The reviewed entity declares `3000–5700 K`, unlike the library and this model's tested `2700–6500 K` range. UI limits must not be copied as hardware limits. |
| `0xlic/ha-huawei-hilink-opple` [S4] | Ceiling-light local HiLink / CoAP over UDP5686; distinguishes routine local operation from initial device-credential acquisition. | Its listed tested models are `MX420-D24-WTT` and `MX480-D48-WTT`. Initial credential acquisition involves an account / cloud service. No accounts were accessed here, and its commands are not applied to MT428. |
| `teflux77/ha-opple-smart-desk-lamp` [S5] | A cloud MQTT implementation for an older HiLink desk lamp, including side-light descriptions. | Cloud properties and its author's hardware findings do not directly map to this model's UDP55001 commands. Its narrative also does not override this model's successful local tests. |
| `xiasi0/ha-huawei-smarthome` [S6] | AI Life cloud integration with product-specific adapters; its reviewed manifest declares `cloud_push`. | Not a universal local protocol for older HiLink devices. Support for an Opple product does not establish support for this complete model. |
| `Zer0wAve/ha-opple-local` [S7] | UDP55001 reference for ceiling lights / other Wi-Fi light SKUs, documenting fixed reply serials and plaintext / XOR differences. | Its listed SKUs differ from this device and supply no MT428-specific evidence. Do not copy its relaxed serial-checking policy or other exceptions automatically. |

Searching for “HiLink API” can also return Huawei LTE router / modem interfaces, such as Home Assistant `huawei_lte`.[S8] Those management interfaces are not the lamp's UDP55001 protocol. A shared module name or HiLink brand likewise does not establish compatibility with standard Broadlink integrations, router login APIs, or arbitrary standard CoAP controls.

## 5. Official features, the side-light gap, and daytime experiments

### Differences between official descriptions

The official App guide lists overall power, main-light brightness, side light, reading / writing / computer / favorite modes, schedules, countdown, and Pomodoro.[H1] The physical-key guide gives different default background-light values for its scenes.[H2] The table below summarizes the two guides. These are not local preset definitions and were not visually retested during documentation work.

| Scene | AI Life App guide [H1] | Physical-key guide [H2] |
| --- | --- | --- |
| Reading | Main light `4000 K`, default brightness `40%`; side light `40%`, switchable. | Main light `4000 K`, background light `100%`. |
| Writing | Main light `5000 K`, default brightness `40%`; side light `40%`, switchable. | Main light `5000 K`, background light `100%`. |
| Computer | Main light off, side light defaults to `40%` and is dimmable. | Background light `30%`. |
| Favorite | Defaults to `3000 K`, brightness `40%`, side light on; customizable. | No separate favorite key is listed in this guide. |

The App guide specifies main-light dimming of `10–100%` and favorite-mode color temperature of `2700–6500 K`. These are not the same scale as the raw protocol byte range. It describes overall power as controlling main and side lights together. Daytime protocol records now distinguish aggregate legacy `power@1` from dedicated head/side power; they do not independently establish emitted light or official-App behavior.

The same guide describes one native schedule with daily repetition, with the next scheduled occurrence remaining effective after loss of network access. It describes a native countdown up to `23 hours 59 minutes`, remaining effective for that occurrence after disconnection and continuing even if the lamp is switched off early. Pomodoro includes a `25-minute` session, pause, and completion indications.[H1] These are official feature descriptions. They do not establish that all execution logic resides in the lamp, or that this adapter implements configuration interfaces for them.

### 2026-10-28 daytime update and remaining research

The side light is documented officially and appears in third-party physical reviews. A 2020-02-27 review names the complete model in its title and body, corroborating model identity and the side light. A 2021-12-21 article mentions both AI Life and “欧普智慧灯光” (Opple's lighting App), and reports side-light dimming in the latter. Its body does not identify the complete model, and comments include unsuccessful connection reports.[P1][P2] This does not guarantee the same dual-App path for the tested lamp, current Apps, or firmware.

Authorized daytime tests now establish single-parameter command acceptance, matching channel readback, and preservation of the other channel's returned fields in the tested cases. The [observation table](observations.md) records side switching/brightness, dedicated head controls, aggregate power, off-state parameter storage, combined-payload failure, and later restoration. Follow-up head brightness tests also show `10 → 25`, `25 → 25`, and `255 → 255` with head power still off and side fields preserved. Together with side `10/20 → 25`, these are sampled clamp observations for both channels, not an exhaustive range test. The five numeric channel fields were subsequently confirmed restored to baseline.

Still unverified are actual light output and physical arm/head correspondence, photometry and brightness mapping, other firmware, native scene codes, favorite storage, schedule/countdown/Pomodoro interfaces, and execution responsibilities. Protocol readback is not complete native local support; unexplained bytes remain H-level hypotheses.

### Historical nighttime boundary and proposed experiment plan

**During the earlier nighttime stage, unknown-feature writes were frozen and no lamp-changing command was sent.** The plan below was unexecuted at that stage. Later explicit daytime authorization permitted the protocol tests summarized above; the plan is retained as a historical snapshot, not a current ban on those authorized tests or a claim that its visual/App/key comparisons were completed. Blind enumeration of unknown commands or payloads is not part of this project.

| Step | Single-variable experiment and record | Acceptance / stop condition |
| --- | --- | --- |
| 1. Establish a baseline | The operator confirms the complete model, official App, and firmware information, records visible main/side-light state and the three known query fields, and selects an acceptable brightness. | Keep sanitized summaries only; do not assume an old article describes the current UI. |
| 2. AI Life differences | Hold scene, main-light brightness, and color temperature constant; change only the side light. Run A→B→A and compare known state with authorized target-device traffic. | Observe main and side lights separately. If the App also changes other parameters, explain that coupling rather than calling it a pure side-light command. |
| 3. Physical-key differences | Short-press the known reading, writing, and computer scenes separately, and test documented background-light actions. Avoid the power-key hold that resets the lamp. | Compare the App's and keys' starting states; do not assume identical factory presets. |
| 4. Second-App comparison | Only if the operator already has a legitimate App, the device is normally visible, and no reset is needed, the operator tries side-light switching / dimming in “欧普智慧灯光”. | If the device is absent, record that limitation. Do not rebind, change firmware, or sign into another person's account to obtain evidence. |
| 5. Repeat and map | Repeat isolated transitions, distinguish commands from readback, heartbeat, and cloud traffic, and record candidate message types / offsets and readback relationships. | A candidate mapping needs reproducibility, an explanation of reverse transitions, and independent evidence. Consider a minimal daytime write only after simulation checks and subsequent explicit authorization. |
| 6. Regress and stop | Restore the state approved by the operator and check the supported three-field controls and side effects. | Stop on unexpected illumination, conflicting state, or failure to restore. Unresolved items remain unknown. |

Publish only manually prepared summaries of field relationships, message types, offsets, and observed behavior. Raw captures, complete decoded bodies, App screenshots, account information, and device identifiers are not project attachments.

## 6. Multicast constant and network boundaries

Existing observations include CoAP `GET /.well-known/core` addressed to **`238.238.238.238:5683`**. This establishes a discovery request, not its responders, group membership, available CoAP control resources, or compatibility with generic CoAP controls. Unicast standard discovery probes to UDP5683 and UDP5686 received no application reply. That means those probes did not succeed under the tested conditions, not that every HiLink protocol is absent.

- IPv4 multicast belongs to `224.0.0.0/4` and identifies receiver groups. `238.238.238.238` is not the lamp's own IP address, device hostname, or a cloud server. It is retained as an observed protocol constant, not private network information.[N1]
- A receiving application normally selects an interface, binds its UDP port, and joins the group. A sender normally need not join first. **IGMP** can express IPv4 group membership; IGMP Snooping switches can use it to limit forwarding. Without appropriate optimization traffic may flood, and Wi-Fi APs may convert multicast to unicast.[N1][N2][N3]
- IPv4-to-Ethernet multicast mapping retains the low 23 bits. This group maps to **`01:00:5e:6e:ee:ee`**. This is a calculated protocol address, not the device MAC. Multiple groups can share a MAC, so IP-layer filtering remains necessary.[N1]
- **IP TTL limits routed hops, not seconds.** No reliable measured IP TTL is retained in this summary, so none is invented. The application header's field named `TTL` must not be mistaken for the outer IPv4 TTL.[S2a]
- A `238` prefix alone does not imply link-local scope. Routed propagation depends on TTL, multicast routing, and policy. Ordinary NAT, HTTP proxies, and general-purpose VPNs do not automatically extend this discovery traffic; cross-network operation also depends on membership, firewalls, AP isolation, and IGMP configuration.

**The verified control path uses unicast UDP55001 on the target device and does not depend on UDP5683 multicast discovery.** An explicit address with identity validation supports this path. Cross-network management should call an adapter near the device, without first extending multicast for HTTP / MCP integration. Unicast still needs a permitted request-and-reply path; it does not bypass arbitrary network isolation.

## 7. Sources and licensing note

Referenced and linked only; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for licensing. This document does not infer third-party licenses or redistribute APKs, SDKs, images, or lengthy source text. Source revisions below make code claims reviewable; project homepages and official pages can still change.

### Official documentation

- [H1] [Functions available through the AI Life App](https://consumer.huawei.com/cn/support/content/zh-cn13251283/), Chinese official support page.
- [H2] [Huawei Select Opple desk-lamp function keys](https://consumer.huawei.com/cn/support/content/zh-cn00759564/), Chinese official support page.
- [H3] [After-sales product and model table for Opple desk, sleep, and ceiling lights](https://consumer.huawei.com/cn/support/content/zh-cn15885815/), Chinese official support page.
- [H4] [Connecting the Opple desk lamp to AI Life](https://consumer.huawei.com/cn/support/content/zh-cn00751653/): describes 2.4 GHz WLAN provisioning requirements, not evidence that this project has verified offline provisioning.

### Historical corroboration

- [P1] [2021-12-21 usage review: AI Life and Opple lighting dual-App lead](https://post.smzdm.com/p/avwmo9d9/); the complete model is not established in its body.
- [P2] [2020-02-27 review naming MT428-D0.5×36+0.2×21-WTT](https://post.smzdm.com/p/ag87m853/).

### Static evidence from the officially distributed APK

- [A1] Distribution chain: [Opple official download index](https://www.opple.com.cn/news/download/) → [Tencent App Store page for `com.sigboat.opple`](https://a.app.qq.com/o/simple.jsp?pkgname=com.sigboat.opple). The analyzed package is `com.sigboat.opple`, version `3.9.11`, versionCode `346`, SHA-256 `bde846073c0154fcb9648326bf8cc439e69dd5593791f1c643ffccbfdb086b4e`. Store downloads can change; verify the hash before treating another download as this evidence.
- Static inspection entry points: `SKUUtil.getDeiveTypeBySku`, `WifiDesklamp_0061`, `ArmControl`, `SEND_ARM_OPENCLOSE`, `SEND_ARM_BRIGHT`, and `SEND_SMARTFUNCTION`. These class / method / symbol names identify the relevant paths; the APK was not run and no device was connected.
- This is an independent summary of protocol facts from a proprietary application, **not public source code or permission to execute or redistribute it**. The project does not distribute APKs, SDKs, decompiled code, resources, or images. This page includes neither a complete control template nor captures.

### Public source code and integrations

- [S1] [Original jedmeng/python-oppleio](https://github.com/jedmeng/python-oppleio), reviewed revision [`245cf932112d0c029d1932451db6fa1e0e2e784e`](https://github.com/jedmeng/python-oppleio/tree/245cf932112d0c029d1932451db6fa1e0e2e784e).
- [S2] [tinysnake/python-oppleio-legacy](https://github.com/tinysnake/python-oppleio-legacy), reviewed revision `90c57f778554fcf3a00e42757d0e92caebcfd149`:
  - [S2a] [const.py: message types and offsets](https://github.com/tinysnake/python-oppleio-legacy/blob/90c57f778554fcf3a00e42757d0e92caebcfd149/pyoppleio/const.py)
  - [S2b] [Message.py: framing, CRC, and XOR](https://github.com/tinysnake/python-oppleio-legacy/blob/90c57f778554fcf3a00e42757d0e92caebcfd149/pyoppleio/Message.py)
  - [S2c] [OppleDevice.py: discovery and SKU filter](https://github.com/tinysnake/python-oppleio-legacy/blob/90c57f778554fcf3a00e42757d0e92caebcfd149/pyoppleio/OppleDevice.py)
  - [S2d] [OppleLightDevice.py: the three known properties](https://github.com/tinysnake/python-oppleio-legacy/blob/90c57f778554fcf3a00e42757d0e92caebcfd149/pyoppleio/OppleLightDevice.py)
- [S3] [Home Assistant Opple documentation](https://www.home-assistant.io/integrations/opple/); reviewed core revision `c79dc18871cb8e6f462c95fd37b4f5ea3edfd2df`, including [manifest.json](https://github.com/home-assistant/core/blob/c79dc18871cb8e6f462c95fd37b4f5ea3edfd2df/homeassistant/components/opple/manifest.json) and [light.py](https://github.com/home-assistant/core/blob/c79dc18871cb8e6f462c95fd37b4f5ea3edfd2df/homeassistant/components/opple/light.py).
- [S4] [0xlic/ha-huawei-hilink-opple: local HiLink for ceiling lights](https://github.com/0xlic/ha-huawei-hilink-opple).
- [S5] [teflux77/ha-opple-smart-desk-lamp: cloud desk-lamp integration](https://github.com/teflux77/ha-opple-smart-desk-lamp).
- [S6] [xiasi0/ha-huawei-smarthome: AI Life cloud integration](https://github.com/xiasi0/ha-huawei-smarthome), also see its [manifest.json](https://github.com/xiasi0/ha-huawei-smarthome/blob/master/custom_components/huawei_smarthome/manifest.json).
- [S7] [Zer0wAve/ha-opple-local: local UDP compatibility for other SKUs](https://github.com/Zer0wAve/ha-opple-local).
- [S8] [Home Assistant Huawei LTE: router / modem interfaces](https://www.home-assistant.io/integrations/huawei_lte/).

### Network standards

- [N1] [RFC 1112: IPv4 multicast host requirements and Ethernet mapping](https://www.rfc-editor.org/rfc/rfc1112.html), particularly sections 6.4 and 7.
- [N2] [RFC 2236: IGMPv2](https://www.rfc-editor.org/rfc/rfc2236.html).
- [N3] [RFC 4541: IGMP / MLD Snooping considerations](https://www.rfc-editor.org/rfc/rfc4541.html).
- [N4] [RFC 5737: IPv4 documentation addresses](https://www.rfc-editor.org/rfc/rfc5737.html).
