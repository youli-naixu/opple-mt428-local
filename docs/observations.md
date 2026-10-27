# Read-only channel observation · 只读通道观察

Date:2026-10-28. One already-provisioned SKU0x50061 unit, raw version0x210. Only SEARCH/QUERY were sent through a transport configured read-only. **No lamp-changing command was sent in this research stage.** No device IP/MAC/name, protocol device ID, complete packet, account or private topology is included.

| Field | Observed value | Interpretation boundary |
| --- | --- | --- |
| Verified legacy power@1 | false | Reported off; no visual channel test in this stage |
| Verified legacy brightness@2 | 28 | Raw byte, not calibrated lux |
| Verified legacy CCT@7:9 | 2700 | Device-reported Kelvin |
| Candidate arm power@52 | 0 | Consistent with static mapping; physical arm unverified |
| Candidate arm brightness@53 | 102 | Candidate stored raw value; not a physical measurement |
| Candidate head power@54 | 0 | Matches legacy power in this one snapshot |
| Candidate head brightness@55 | 28 | Matches legacy brightness in this one snapshot |
| Candidate head CCT@56:58 | 2700 | Matches legacy CCT in this one snapshot |

The head candidates align with the known legacy fields in a single returned state. That is useful corroboration of the static parser layout, **not** a transition experiment, proof of physical arm/head mapping, or acceptance of command0x03450000. No inference about unchanged-field placeholders was tested. Repeated A→B→A daylight observations remain necessary before declaring independent side-light control hardware-verified.

中文：本轮只读查询，没有开灯或调光。头灯候选值与已知旧版状态在这一个快照中一致，支持继续验证该布局，但不证明侧灯的物理对应、独立控制命令或占位保持语义已被实物确认。侧灯原始亮度102只是候选存储字段，不代表正在发光。后续应白天逐项做可逆差分与目视确认。

See [research](research.en.md#side-light-static-analysis), [中文研究](research.zh-CN.md), and [source index](sources.md).
