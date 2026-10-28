# Channel observations · 通道观察

Date: 2026-10-28. One already-provisioned **MT428-D0.5×36+0.2×21-WTT**, SKU `0x50061`, raw version `0x210`. This summary uses the maintainer's saved daytime diagnostic records and supplied follow-up results. Preparing it involved no device or API connection. No real device identifiers, private paths, complete bodies, or raw frames are published.

日期：2026-10-28。对象为一台已配网样机，型号、SKU 与版本原始字段如上。依据维护者保存的白天诊断记录和补充结果整理；本次文档工作未连接设备或 API，不公开真实设备标识、私有路径、完整 body 或原始帧。

**Physical-device protocol write/readback confirmed; visual validation pending.** Actual emitted light, physical channel mapping, illuminance, color spectrum, and the brightness-to-light relationship were not independently observed by eye or instrument. The side-light feature remains experimental because firmware coverage is limited to one unit and optical validation is incomplete.

**已确认物理设备上的协议写入与回读；目视验证待完成。** 实际发光、物理光源对应、照度、光谱和亮度映射均未由目视或仪器独立观测。侧灯继续保留实验标记，原因是固件覆盖仅一台样机，且光学验证未完成。

## Historical read-only stage · 历史只读阶段

The initial nighttime stage used a read-only transport and sent SEARCH/QUERY only. **No lamp-changing command was sent in that stage; nighttime writes were prohibited.** Later daytime tests had new explicit authorization. These are separate stages, and the later results do not rewrite the earlier no-write record.

最初的夜间阶段使用只读传输，仅发 SEARCH/QUERY，**该阶段禁止写入，未发送改变灯光的命令**。后续白天取得新的明确授权后才进行写测，不能用新结果改写历史禁写记录。

| QUERY field / 查询字段 | Initial readback / 初始回读 | Boundary / 边界 |
| --- | --- | --- |
| Legacy power `@1` | `false` | Both channel power fields were `0` / 当时两个通道开关均为 `0` |
| Legacy brightness `@2`, CCT `[7:9]` | `28`, `2700 K` | Stored protocol values, not optical measurements / 存储协议值，非光学测量 |
| Arm/side power `@52`, brightness `@53` | `0`, `102` | Initially static-parser candidates / 当时仅为静态解析候选 |
| Head power `@54`, brightness `@55`, CCT `[56:58]` | `0`, `28`, `2700 K` | Matched legacy fields in this snapshot only / 当时仅确认此快照一致 |

That snapshot alone did not establish transitions or placeholder semantics. The following daytime results provide additional protocol evidence.

该快照本身不证明状态转换或占位语义；以下白天结果补充了协议证据。

## Authorized daytime results · 获授权的白天结果

Offsets are zero-based decoded body offsets. Each successful dedicated-channel test changed **one parameter per `0x03450000` payload**, leaving the other fields at the App template's unchanged values. Reported preservation concerns returned fields, not independently observed light.

偏移均为解码后 body 的零基偏移。专用通道的成功测试按 **每个 `0x03450000` payload 只改一个参数**执行，其余字段保留 App 模板的未改占位值。“保持不变”均指回读字段，不代表已独立观察光线。

| Test / 测试 | Request → readback / 请求→回读 | Finding / 结论 |
| --- | --- | --- |
| Side power, control `@4` / 侧灯开关 | `off → on → off` | QUERY `@52` followed; head stayed `0 / 28 / 2700 K` / 回读跟随，头灯三字段保持 |
| Side brightness, control `@5` / 侧灯亮度 | `51 → 51`, `178 → 178`, `102 → 102` | QUERY `@53` matched; same head baseline preserved / 精确回读，头灯基线保持 |
| Dedicated head controls / 专用头灯控制 | Power `@6`; brightness `@7` to `51`; CCT `[8:10]` to `4000 K` | Corresponding QUERY head fields followed single-parameter writes; side fields preserved / 单参数写入得到对应回读，侧灯字段保持 |
| Side clamp / 侧灯钳位 | `10 → 25`, `20 → 25`; `25 → 25`, `255 → 255` | Observed raw minimum `25` on this firmware; not an optical calibration or an exhaustive range test / 此固件观察到原始下限 `25`，非光学标定或全范围穷举 |
| Side off/on with head on / 头灯开启时切换侧灯 | Side `1 → 0 → 1` | Head power, brightness, and CCT preserved / 头灯开关、亮度、色温保持 |
| Head off with side on / 侧灯开启时关闭头灯 | Head `1 → 0`, side remains `1` | Legacy power `@1` remains `true`; both off returns `false` / 旧总电源仍为 `true`，全关才为 `false` |
| Dedicated off-state parameters / 专用关灯调参 | Side/head brightness and head CCT updated with both channel power fields `0` | Stored fields can change without a protocol power-on step; no optical observation / 无需协议开灯步骤即可更新存储字段，未观察光线 |
| Combined side payload / 侧灯合包 | Side power + brightness in one payload | Brightness ignored; an earlier combined restore did not restore side brightness / 亮度被忽略，早期合包恢复未还原侧灯亮度 |
| Later single-field restore / 后续单字段恢复 | Side `0 / 102`; head `0 / 28 / 2700 K` | Final readback returned to the known baseline / 最终回读恢复已知基线 |

Dedicated off-state behavior differs from the historical **legacy** dimming path, which needed a temporary power-on to update parameters on this unit. Legacy control could also change side fields; it is not an independent head-control substitute. No claim is made that an off-state parameter write was optically dark throughout.

专用关灯调参与历史 **legacy** 调光路径不同：后者在本样机上需要短暂开灯才能更新参数，且可能改变侧灯字段，不能代替独立头灯控制。这里不声称关灯调参全过程已经过光学确认。

## Adapter implications · 适配器约定

The Unreleased backend splits multi-field channel requests into single-parameter payloads and verifies each with QUERY. Side responses keep `verified:false`, add `protocol_verified`, `head_fields_preserved`, `requested`, `actual`, and `brightness_clamped`, and retain `candidate_readback_matched` for compatibility. Clients must distinguish requested brightness from the returned, possibly clamped value.

Unreleased 后端将多字段通道请求拆成单参数 payload，逐包 QUERY 核验。侧灯响应保留 `verified:false`，新增 `protocol_verified`、`head_fields_preserved`、`requested`、`actual`、`brightness_clamped`，并兼容 `candidate_readback_matched`。调用方应区分请求亮度与可能已被钳位的实际回读。

Experimental mode uses dedicated head controls for brightness/CCT requests; a request containing those parameters and `power:true` explicitly enables the head. Power-only control retains legacy semantics. Restore covers both channels' known initial fields only when that channel snapshot exists; otherwise the legacy fallback cannot reconstruct unknown channel state. Default hardware mode remains read-only, with both write and experimental flags required for dedicated-channel writes.

实验模式下，含亮度／色温的请求走专用头灯控制；同时带 `power:true` 时明确开启头灯。仅电源请求维持 legacy 语义。有初始通道快照时，恢复覆盖两个通道的已知字段；缺失时的 legacy 回退无法重建未知通道状态。实物默认仍为只读，专用通道写入需同时启用写入和实验选项。

See [protocol research](research.en.md#side-light-static-analysis), [中文研究](research.zh-CN.md#side-light-static-analysis), and the [API contract](api.md). Source and licensing provenance remain in the [source index](sources.md).
