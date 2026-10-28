# Changelog · 更新记录

## Unreleased

### Channel protocol and controls · 通道协议与控制

- Record authorized daytime single-parameter `0x03450000` side/head write/readback on one physical SKU `0x50061` unit: side off/on/off, brightness `51/178/102`, head brightness `51` and CCT `4000 K`, with other-channel fields preserved. Physical-device protocol write/readback confirmed; visual validation pending / 记录获授权白天实物单参数写入与回读，另一通道字段保持；目视与光学验证待完成。
- Document side brightness `10/20 → 25`, exact `25/255` readback, aggregate legacy `power@1`, and dedicated off-state brightness/CCT updates / 补充侧灯钳位、总电源语义及专用关灯调参行为。
- Split combined channel requests into one parameter per payload with QUERY after each: the tested firmware ignores side brightness when combined with side power / 通道请求按参数拆包并逐包查询，规避侧灯开关与亮度合包时亮度被忽略。
- Keep side responses `verified:false`; add `protocol_verified`, `head_fields_preserved`, `requested`, `actual`, and `brightness_clamped`, retaining `candidate_readback_matched` / 区分协议确认、头灯保持、请求／实际值与亮度钳位，保留兼容字段。
- Use dedicated head controls for brightness/CCT with experimental mode enabled; `power:true` in those requests explicitly enables the head. Power-only requests and operation without the experimental flag retain legacy behavior / 实验模式按专用头灯调参，带开灯要求时明确开头灯；仅电源与无实验选项维持 legacy 行为。
- Restore both channels' known initial fields when a channel snapshot exists; otherwise retain legacy fallback. Keep read-only defaults, experimental/write gates, historical nighttime no-write records, and source/license provenance / 有初始通道快照时恢复两路已知字段，否则回退 legacy；保留默认只读、双门禁、历史禁写记录及来源许可。

## 0.1.0 — 2026-10-28

- Initial public research release for MT428-D0.5×36+0.2×21-WTT / 首个公开研究版本。
- Explicit-interface or direct-IP read-only discovery; no legacy single-SKU discovery filter / 显式网卡或单播发现。
- Checked UDP framing, CRC, serial and identity; verified legacy power/brightness/CCT path / 严格报文与身份核验。
- Local responsive web demo, simulator, scenes, in-process timer and restore / 本地网页与模拟模式。
- Default hardware read-only; explicit write and experimental side-light gates / 实物默认只读。
- Vendor-app static evidence for SKU0x50061 channel command0x03450000; side-light hardware testing pending / 侧灯协议已定位，实机待验证。
- English/Chinese research and architecture, source index, license provenance and offline CI / 双语资料、来源、许可与离线测试。
