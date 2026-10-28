# Source index · 重要来源与相关项目

Reviewed on2026-10-28. Links identify evidence, not blanket compatibility. Official/vendor materials remain proprietary unless a separate license says otherwise. / 链接用于复核，不表示所有项目兼容本型号；厂商材料不因公开可见而成为开源。

## Official product evidence / 官方型号与功能

| Source | What it establishes / 用途 |
| --- | --- |
| [Huawei model/support table](https://consumer.huawei.com/cn/support/content/zh-cn15885815/) | MT428-D0.5×36+0.2×21-WTT maps to the original Huawei-selected OPPLE reading/writing lamp; distinguish2S/Pro |
| [Huawei app feature guide](https://consumer.huawei.com/cn/support/content/zh-cn13251283/) | Main/side lighting, modes, native timer/countdown and Pomodoro; no UDP field map |
| [Huawei physical controls](https://consumer.huawei.com/cn/support/content/zh-cn00759564/) | Reading4000K, writing5000K, computer/background control; physical defaults can differ from app defaults |
| [Huawei Wi-Fi provisioning](https://consumer.huawei.com/cn/support/content/zh-cn00751653/) | 2.4GHz Wi-Fi and app provisioning |
| [OPPLE official download center](https://www.opple.com.cn/news/download/) | Official distribution entry for 欧普智慧灯光 |
| [Tencent app listing](https://a.app.qq.com/o/simple.jsp?pkgname=com.sigboat.opple) | Official-linked distribution for com.sigboat.opple |

## Vendor-app static evidence / 厂商App静态证据

- Package: `com.sigboat.opple`; app version `3.9.11`, versionCode `346`.
- SHA-256: `bde846073c0154fcb9648326bf8cc439e69dd5593791f1c643ffccbfdb086b4e`.
- [Reviewed distributor APK URL](https://imtt.dd.qq.com/sjy.00022/sjy.00004/16891/apk/262A5A7ECCC29F8D0FC1A8062DA43E33.apk?fsname=com.sigboat.opple_3.9.11.apk). Availability can change; no copy is committed.
- Relevant identifiers: `sdk.util.SKUUtil.getDeiveTypeBySku`, `sdk.device.WIFI.WifiDesklamp_0061`, `com.zhuoapp.opple.activity.spec.desklamp_0061.ArmControl`, `SEND_ARM_OPENCLOSE`, `SEND_ARM_BRIGHT`, `SEND_SMARTFUNCTION`, `BaseDevice.ProcessQueryState`.
- Findings: explicit `0x50061` mapping; local UDP55001; command `0x03450000`; 10-byte body; candidate state offsets52–57. See [research](research.en.md#side-light-static-analysis) / [中文](research.zh-CN.md).

These are independently summarized interface facts, not vendor source code. No APK/DEX/SDK, class-body dump, image, or extracted profile is redistributed. Subsequent authorized tests confirmed dedicated side/head protocol writes, readback, and unchanged opposite-channel fields on one unit; physical light mapping and optical output remain unobserved. See the dated [observations](observations.md). / 后续白天授权测试已确认分通道协议写入、回读与另一通道字段保持，目视光学验证仍待完成。

## Community observations / 同型号与双生态记录

| Source | Scope |
| --- | --- |
| [2020 full-model review](https://post.smzdm.com/p/ag87m853/) | Full model, app/UI observations and button indicator; do not extrapolate one sample's module to every batch |
| [2021 HiLink and OPPLE app coexistence](https://post.smzdm.com/p/avwmo9d9/) | User report of OPPLE Smart Lighting control after Wi-Fi setup; article does not identify every model suffix |
| [2017 launch report](https://www.sohu.com/a/190215421_355133) | Distinguishes2016 cooperation agreement from2017 智清 launch; not a manufacturing-date proof |

## Protocol/software references / 协议与软件参考

| Project | Relevance and boundary |
| --- | --- |
| [jedmeng/python-oppleio](https://github.com/jedmeng/python-oppleio) | Foundational OPPLE UDP layout, commands, CRC/XOR and three legacy fields |
| [tinysnake/python-oppleio-legacy](https://github.com/tinysnake/python-oppleio-legacy) | Legacy fork; automatic search's `0x100010e` filter can miss MT428 `0x50061` |
| [Home Assistant Opple docs](https://www.home-assistant.io/integrations/opple/) / [source](https://github.com/home-assistant/core/tree/dev/homeassistant/components/opple) | Existing local integration; fixed host path avoids old search filter; generic support wording is not proof for every firmware |
| [jedmeng/homebridge-opple](https://github.com/jedmeng/homebridge-opple) | Parallel legacy implementation, no independent arm fields found |
| [Zer0wAve/ha-opple-local](https://github.com/Zer0wAve/ha-opple-local) | Ceiling-lamp reply compatibility research; different tested SKUs |
| [0xlic/ha-huawei-hilink-opple](https://github.com/0xlic/ha-huawei-hilink-opple) | Local HiLink CoAP5686 for specific ceiling lamps; first-time local-key acquisition uses cloud; no MT428 support claim here |
| [teflux77/ha-opple-smart-desk-lamp](https://github.com/teflux77/ha-opple-smart-desk-lamp) | Huawei cloud MQTT desk-lamp project; cloud backlight naming is not a UDP field map |
| [xiasi0/ha-huawei-smarthome](https://github.com/xiasi0/ha-huawei-smarthome) | Product-specific cloud adapters; GPL code and vendor-extracted reference data are not bundled |
| [sdrpsps/opple-light](https://github.com/sdrpsps/opple-light) | App built around legacy pyoppleio; reference link only |

Exact reviewed revisions and license-file discrepancies are in [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md). No source from no-license/GPL reference projects is merged here.

## Networking / 网络原理

- [RFC1112 — Host Extensions for IP Multicasting](https://www.rfc-editor.org/rfc/rfc1112): IPv4 multicast group semantics and Ethernet mapping.
- [RFC7252 — CoAP](https://www.rfc-editor.org/rfc/rfc7252): CoAP request structure; observing a discovery GET does not establish an authenticated control interface.
- [RFC5737 — Documentation IPv4 blocks](https://www.rfc-editor.org/rfc/rfc5737): why examples use192.0.2.0/24.

The observed public group `238.238.238.238:5683` is retained as a protocol observation. Personal device identifiers, real LAN topology, cloud session addresses, and raw captures are excluded.
