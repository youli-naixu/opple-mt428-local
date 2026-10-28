# HTTP API · 接口

The demo binds `127.0.0.1` only. Hardware mode is read-only by default; writes require `--allow-write`, and dedicated-channel controls additionally require `--experimental-side-light`. The channel behavior below describes the **Unreleased** update, not a retroactive claim about the published alpha. This is a development server, not a public authenticated gateway.

仅监听本机，实物默认只读；写入需 `--allow-write`，专用通道控制还需 `--experimental-side-light`。下述通道行为属于 **Unreleased** 更新，不改写已发布 Alpha 的历史能力。此服务用于本地开发，不应直接作为公网认证网关。

| Method | Path | JSON request | Behavior / 行为 |
| --- | --- | --- | --- |
| GET | `/api/status` | none | SEARCH/QUERY or simulation; returns `online/state/initial_state/capabilities/activity/mode` / 查询或模拟状态 |
| GET | `/api/health` | none | Process health, not device reachability / 仅进程健康 |
| POST | `/api/control` | `{"power":true,"brightness":128,"color_temp":4000}` | Partial fields accepted; routing depends on fields and experimental mode, as below / 支持部分字段，按下文选择通道 |
| POST | `/api/scene` | `{"id":"reading"}` | Local parameter combination; also `screen/relax` / 本地参数组合，非原厂模式 |
| POST | `/api/timer` | `{"minutes":30}` | Process-owned off timer, `1..120` minutes / 进程内关灯定时 |
| DELETE | `/api/timer` | none | Cancel process timer / 取消定时 |
| POST | `/api/restore` | `{}` | Cancel timer; restore known initial channel fields when available, otherwise legacy state / 取消定时，按已知初始通道字段恢复，否则回退 legacy |
| POST | `/api/experimental/side-light` | `{"power":true}`, `{"brightness":102}`, or both | Gated side control; one parameter per device payload, QUERY after each / 受门禁保护，逐参数拆包并回读 |

Send `Content-Type: application/json` for POST. Browsers must be same-origin; no CORS wildcard is provided. Failures return 4xx/5xx and a message; transport-offline replies may include an older state. HTTP arrival alone is not execution confirmation.

POST 使用 `Content-Type: application/json`；浏览器需同源，不提供 CORS 通配。失败返回 4xx/5xx 与消息，设备离线响应可能带旧状态；HTTP 请求到达不等于执行成功。

## Status and aggregate power · 状态与总电源

Mode fields are `read_only`, `simulated`, and `experimental_side_light`. `state.observed_at` is ISO UTC. When `online=false`, `state` may be stale. `device.version` is a raw version word, not a decoded firmware version. Experimental channel data lives under `state.experimental_channels`; its evidence describes physical-device protocol write/readback with visual validation pending. Simulation must remain labeled `simulated:true` and is not device evidence.

模式字段为 `read_only`、`simulated`、`experimental_side_light`；时间戳为 ISO UTC。`online=false` 时状态可能过期；版本字未经固件版本解码。实验通道位于 `state.experimental_channels`，证据边界是物理设备协议写入／回读，目视待验证。模拟始终带 `simulated:true`，不计入设备实测证据。

`state.power` is legacy QUERY `power@1`, an **aggregate** indication on the tested firmware. It remains `true` with head off and side on, or head on and side off; it is `false` when both are off. Use `head_power_raw@54` and `arm_power_raw@52` under `state.experimental_channels` for individual channel state. Legacy brightness/CCT do not turn aggregate power into head power.

`state.power` 来自 legacy QUERY `power@1`，在已测固件上是**总电源指示**：任一通道开时仍为 `true`，全关为 `false`。独立状态需读 `state.experimental_channels` 的 `head_power_raw@54`、`arm_power_raw@52`；不能因旧版亮度／色温对应头灯，就把总电源当头灯电源。

## Control routing and combined writes · 控制路径与合包限制

With experimental channels enabled, `/api/control` requests containing brightness or CCT use the dedicated **head** fields in `0x03450000`: power `@6`, brightness `@7`, CCT `[8:10]`. Including `power:true` explicitly turns on the head even if aggregate power was already true because the side was on. Parameter-only writes preserve channel power. On the tested unit, dedicated head/side brightness and head CCT can update stored values with both channels off, without the legacy temporary-on sequence.

开启实验通道后，`/api/control` 中含亮度或色温的请求使用 `0x03450000` 专用**头灯**字段：开关 `@6`、亮度 `@7`、色温 `[8:10]`。同时带 `power:true` 时明确开启头灯，不能因侧灯使总电源已经为 true 就跳过。仅调参时保持通道开关；已测样机全关时也可更新专用头灯／侧灯亮度和头灯色温存储值，无需 legacy 临时开灯流程。

**Power-only `/api/control` retains legacy semantics**, including when experimental parsing is enabled. Without `--experimental-side-light`, the original legacy control and restore implementation remains in use. Legacy dimming of an off lamp may temporarily turn it on, apply brightness/CCT, and turn it off again; legacy operations can affect side fields. A failed transport can leave an unknown state.

**仅含电源的 `/api/control` 保留 legacy 语义**，启用实验解析时也一样。不带 `--experimental-side-light` 时维持原 legacy 控制与恢复实现。legacy 关灯调参可能先短暂开灯、调整再关灯，且可能影响侧灯字段；传输失败后结果可能未知。

**Do not encode side power + brightness together in one device payload.** The tested firmware ignores brightness in that combination; an earlier combined API write/restore therefore failed to apply it. One HTTP request may still contain both fields: the updated backend splits channel changes into separate payloads, changing only one parameter and retaining all other App-template unchanged values, then QUERY-verifies each step. This also applies to dedicated head changes and channel restore. Multiple writes are not atomic; partial execution must not be treated as a completed restore or a reason to resend blindly.

**不要在同一个设备 payload 同时设置侧灯电源与亮度。** 已测固件会忽略亮度，因此早期 API 合包写入／恢复未能应用该亮度。HTTP 请求仍可同时带两个字段，新后端按参数拆成多个 payload，每包仅改一个参数，其他字段保留 App 模板未改占位值，并逐包 QUERY 核验。专用头灯调参与通道恢复同样按此方式执行。多包不是原子事务，部分执行不能算完整恢复，也不应盲目重发。

## Side response and brightness clamp · 侧灯响应与亮度钳位

Side brightness requests `10` and `20` read back as **`25`** on the tested firmware; requests `25`, `51`, `102`, `178`, and `255` matched exactly in recorded tests. This is an observed raw-value clamp, not a validated illuminance floor, a slider calibration, or a guarantee for other firmware. Read the returned values rather than assuming the request was applied exactly.

已测固件将侧灯亮度请求 `10`、`20` 钳位回读为 **`25`**；记录中的 `25`、`51`、`102`、`178`、`255` 精确返回。这是原始值钳位观察，不是照度下限、滑块标定或跨固件保证，应以返回值为准。

Dedicated head brightness was also observed at `10 → 25`, with `25` and `255` returning exactly; the head API still requires an exact dedicated readback and reports a mismatch rather than silently accepting a clamp. The UI avoids this path by using a10–100% head slider and raw25–255 side slider. These observations do not establish every intermediate value.

专用头灯另测 `10 → 25`，`25`、`255` 精确返回；当前头灯 API 仍按专用字段精确核验，钳位造成不一致时报告失败，不静默当作成功。页面以主灯10–100%、侧灯原始25–255避免低值误报，未穷举所有中间值。

A successful experimental response retains `ok:true`, `experimental:true`, and **`verified:false`**. Its fields distinguish protocol results from pending optical validation:

成功的实验响应保留 `ok:true`、`experimental:true` 和 **`verified:false`**，以下字段区分协议结果与尚未完成的光学验证：

| Field | Meaning / 含义 |
| --- | --- |
| `protocol_verified` | Protocol write/readback confirmation, including the documented clamp; not optical verification / 协议写入与回读确认，考虑已记录钳位，不代表光学验证 |
| `head_fields_preserved` | Head power, brightness, and CCT readback stayed unchanged across the side operation / 侧灯操作前后头灯开关、亮度、色温回读保持 |
| `requested` | Requested control values / 请求的控制值 |
| `actual` | Returned control values; these may differ because of clamping / 实际回读值，钳位时可能与请求不同 |
| `brightness_clamped` | Explicit indication that brightness was clamped / 明确标记亮度钳位 |
| `candidate_readback_matched` | Retained readback-match field for existing clients; inspect the new fields for preservation and clamping / 保留兼容字段，保持与钳位详情读新字段 |
| `verified` | Always `false` for this experimental endpoint while optical validation is pending / 本实验端点光学验证待完成，始终为 `false` |

The evidence wording is **“physical-device protocol write/readback confirmed; visual validation pending.”** Neither a successful response nor head-field preservation independently proves physical light mapping, lack of a flash, or photometric performance. Legacy `ok:true, verified:true` still means protocol readback only (brightness tolerance 2 raw steps; CCT tolerance 80 K), not photometry.

证据措辞为“**已确认物理设备上的协议写入与回读；目视验证待完成**”。成功响应及头灯字段保持，都不独立证明物理光源对应、无闪亮或光度表现。legacy 的 `ok:true, verified:true` 也仅指协议回读（亮度容差 2 原始步、色温容差 80 K），不是光学测量。

## Restore known channel state · 恢复已知通道状态

With experimental mode enabled **and a saved initial channel snapshot**, `/api/restore` restores side power/brightness and head power/brightness/CCT, using single-parameter writes with readback. It cancels the process timer. A complete known-channel restore requires all those initial values; neither current aggregate power nor a legacy-only snapshot can reconstruct missing initial channel values.

启用实验模式且**保存了初始通道快照**时，`/api/restore` 逐参数写入并回读侧灯开关／亮度、头灯开关／亮度／色温，并取消进程定时。完整的已知通道恢复需要这些初始值；当前总电源或只有 legacy 的快照不能重建缺失的初始通道状态。

If channel state is unavailable, or experimental mode is disabled, restore falls back to the legacy initial power/brightness/CCT path. This fallback does not promise independent side restoration. Unknown vendor modes, favorites, schedules, and other fields are outside either restore contract. See [observations](observations.md) for the dated protocol evidence and historical nighttime boundary.

缺少通道状态或未启用实验模式时，恢复回退到初始 legacy 开关／亮度／色温，不保证独立还原侧灯。未知原厂模式、最爱、计划等字段均不在恢复范围内。日期化协议证据及历史夜间边界见[观察记录](observations.md)。
