# Contributing · 贡献指南

Thanks for making an old lamp easier to understand and maintain. Small, evidence-backed reports are more useful than broad compatibility claims.

## English

1. Start with a read-only inspection or `--simulate`. The test suite does not require hardware.
2. State the full model, anonymized SKU/version word, firmware context if known, and whether a finding comes from physical readback, a visible light change, source inspection, static vendor-app analysis, or a hypothesis.
3. Keep independent side-light behavior experimental until current-firmware tests establish: arm/head correspondence, off-state behavior, placeholder semantics, and whether another channel changes. Never brute-force unknown commands on a live device.
4. For a daylight side-light test, record an initial state; make one official-app or physical-button change at a time; compare decoded state fields and message type; verify the other light channel; restore the baseline. A matching candidate byte alone is insufficient.
5. Add synthetic regression tests for new parsing/control code. Do not commit actual device packets as fixtures. Tests must not discover or change real LAN devices.
6. Keep English/Chinese documentation consistent. Mark unsupported/experimental behavior explicitly. Preserve Apache-2.0 provenance and update third-party notices for any newly included code.

Before sharing, replace real device IP/MAC/name, account/device identifiers, SSID, home topology, cloud session endpoints, tokens/authCodes, cookies, credentials and user paths. Use documentation addresses such as192.0.2.42 and a synthetic MAC such as02:00:00:00:00:01. Do not upload raw PCAP, APK, DEX, firmware, SDK, extracted vendor JSON, screenshots containing private network identities, or long proprietary source excerpts.

```sh
python -m unittest discover -s tests -v
node --check opple_mt428/static/app.js
```

A useful PR describes the concrete before/after behavior, evidence, tests, and limits. Follow the PR template. Do not include secrets in an Issue or PR; see [SECURITY.md](SECURITY.md).

## 中文

先用只读查询或模拟模式。报告完整型号、已脱敏SKU／版本原始字，并区分真机回读、物理光线变化、源码、App静态分析和假设。一个型号或版本成功，不能外推全部MT428或HiLink设备。

侧灯仍是实验能力。白天可在记录初态后逐项操作官方App或物理按键，比较命令与状态差分，确认灯臂／灯头对应、关灯行为、占位保持语义以及是否影响另一个光源，最后还原。不要对实物枚举未知命令，也不要把候选字节匹配当成物理验证。

代码变更附合成报文测试；测试不能在贡献者不知情时发现或控制真实设备。新增来源保留许可与归属，双语文档同步更新。

分享前删除真实IP、MAC、设备名、账号／设备标识、SSID、家庭拓扑、云会话地址、token、authCode、cookie、密码和用户路径。禁止提交原始抓包、APK／DEX／固件／SDK、厂商提取JSON、含私人身份的截图或长段反编译代码。协议事实可以用自己的表格和实验结果描述，原材料只链接。
