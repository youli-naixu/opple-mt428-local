# OPPLE MT428 Local · 欧普台灯局域网控制

[English](README.md) · [协议研究](docs/research.zh-CN.md) · [接入架构](docs/architecture.zh-CN.md)

为 **MT428-D0.5×36+0.2×21-WTT 华为 HiLink 欧普读写台灯**整理的局域网发现、控制工具、网页 Demo 和研究笔记。实测样机同时存在旧 HiLink 与欧普 UDP 通信；后者能够直接在局域网内控制，无需提取华为云账号 token。

希望给后来研究这盏灯的人留下一条可复核的路径：完整型号、绕开旧库 SKU 过滤的设备发现、报文核验、关灯调光的固件行为，以及新找到的**灯臂／侧灯独立控制协议**。

**当前为 Alpha。** 开关、旧版亮度和色温已在一台 `SKU 0x50061` 样机完成写入与回读测试。**独立侧灯写入尚未实机验证**，默认关闭，需实验支持与写入授权两个启动选项。模拟测试或候选状态字段匹配，都不能代替物理灯光验证。

这是独立社区研究，与欧普、华为、博联、Home Assistant 无隶属、赞助或认可关系。仓库不包含厂商 APK、反编译代码、固件、SDK、Logo、凭据或原始抓包。

![模拟模式网页预览，不连接真实台灯](docs/images/demo-simulation.png)

## 没有台灯也能先看页面

需要 **Python 3.10+**，无第三方运行时依赖。在仓库根目录运行：

```sh
python -m opple_mt428 serve --simulate
```

打开 **http://127.0.0.1:8765/**。模拟模式醒目标注，不创建台灯 UDP socket。包含灯光示意、开关、亮度、色温、本地场景、进程内定时关灯、恢复初始状态、能力目录、接入规划和组播说明。

无需实物预览实验侧灯面板：

```sh
python -m opple_mt428 serve --simulate --experimental-side-light
```

网页目前为中文，运行模式与实验提示中英双语；项目文档与贡献说明提供中英双语。

## 如何在局域网寻找台灯

发现过程只向 UDP **55001** 发送**一条只读 SEARCH**并收集回复，不开灯、不调光、不配对、不重置，也不逐个扫描整个网段。

1. 保留现有2.4 GHz Wi-Fi配网，让电脑与台灯处于可达局域网。主机防火墙需要允许本地UDP应答。
2. 用Windows `ipconfig` / `Get-NetIPAddress`、Linux `ip -4 address` 或macOS网络设置查看电脑的IPv4及前缀；也可以查看路由器DHCP租约。`Broadlink-*` 主机名只是线索，不能直接认定支持标准博联协议。
3. 有多网卡或VPN时明确选择接口。下方示例替换为**电脑自己的本地IP/前缀**，不是台灯IP。

```sh
python -m opple_mt428 discover --interface 192.0.2.10/24 --json
```

已从路由器知道台灯IP时，只做一次指定目标的单播发现：

```sh
python -m opple_mt428 discover --target 192.0.2.42 --json
```

`192.0.2.0/24` 是文档用TEST-NET地址，必须替换。发现结果含本地IP、MAC、设备名，分享前请脱敏。

发现工具核对类型、序号、长度、CRC、源端点和设备回报地址，继续收集所有合法候选，不再只认旧库的 `0x100010e`；这台读写灯实测为 **`0x50061`**。未知SKU会列出，但不会自动取得写权限。请按路由器或铭牌核对MAC，显式选择设备。UDP与MAC循环XOR不构成密码学身份认证。

详见[发现与排错指南](docs/discovery.md)。

## 只查询，不改变灯光

将两个占位值替换为自己的发现结果：

```sh
python -m opple_mt428 status --ip 192.0.2.42 --mac 02:00:00:00:00:01
python -m opple_mt428 serve --ip 192.0.2.42 --mac 02:00:00:00:00:01
```

**实物网页模式默认只读。** 查询只发送SEARCH/QUERY，服务端与传输层都会阻止灯光写入及关灯定时。网页仅监听 **127.0.0.1**。

确定要控制实物时再运行：

```sh
python -m opple_mt428 serve --ip 192.0.2.42 --mac 02:00:00:00:00:01 --allow-write
```

**可能亮灯：**实测固件关灯时忽略调光。为了设置参数，后端可能暂时开灯、调整亮度／色温，再恢复关灯；“开灯并应用”会保持开启。夜间只读研究请勿启用写入。

## 侧灯研究的新发现

对厂商渠道发行的“**欧普智慧灯光**”Android App做静态分析，找到 **`SKU 0x50061 → WifiDesklamp_0061`** 的明确分支、灯臂控制界面，以及本地UDP命令 **`0x03450000`**。它包含灯臂开关／亮度和灯头开关／亮度／色温；候选QUERY字段位于body **52–57**。

[研究文档](docs/research.zh-CN.md)记录了官方分发链接、包名、版本、SHA-256、类方法与字段表，不分发厂商代码或资源。证据已超过按名称猜测，但**当前固件对占位值的处理、物理光源对应关系、是否影响另一光源仍待白天验证**。

后续[只读观察](docs/observations.md)发现头灯候选值在一个快照中与旧版状态一致；这仍不证明独立灯臂写入及占位保持语义已经验证。

仅查看候选状态：

```sh
python -m opple_mt428 status --ip 192.0.2.42 --mac 02:00:00:00:00:01 --experimental-side-light
```

侧灯实验写入必须同时提供 `--allow-write` 与 `--experimental-side-light`。页面每次仅发一条写请求，只报告候选字段是否匹配，不显示“真机已验证”。项目没有未知命令枚举或暴力尝试功能。

## 功能范围

| 功能 | 实现／证据 |
| --- | --- |
| 只读发现、旧版状态 | 样机已测试，核验设备回复 |
| 开关、原始亮度0–255、2700–6500 K | 一台样机写入与回读通过；不是物理光度测量 |
| 独立侧灯／灯臂 | 厂商App静态证据，实验适配，未实机测试 |
| 本地场景 | 已知参数组合，不等同原厂模式 |
| 本地定时／恢复 | 由电脑进程执行，休眠／退出／重启可能取消或延迟 |
| 原厂阅读／书写／电脑／最爱 | 官方已说明，完整原生协议未实现 |
| 原厂灯内计划／倒计时、番茄钟、指示灯 | 官方说明或同型号记录，未实现 |
| 首次完全离线配网 | 未证实；保留已有配网 |
| 其他固件与型号 | 不作普遍兼容承诺，MT428前缀不足以识别版本 |

亮度百分比是原始值的线性显示，未证明等于官方App刻度；版本字是原始字段，未解码为固件版本；MAC循环XOR是观察到的编码，不是安全加密。

## HTTP与后续接入

API包含 `GET /api/status`、`POST /api/control`、`/api/scene`、`/api/timer`、`/api/restore` 和受门禁保护的 `/api/experimental/side-light`，详见[API说明](docs/api.md)。

推荐单一常驻局域网适配器统一处理UDP，通过HTTP提供给路由器管理页、ESP面板和MCP工具。观察到的 **`238.238.238.238:5683`** 是发现用组播地址，不是台灯IP；已验证控制走UDP55001单播，无需把组播搬到另一张网络。详见[总体架构](docs/architecture.zh-CN.md)。

本项目不是Home Assistant自定义组件，也不是华为路由器／4G上网卡HiLink接口。已有[Home Assistant Opple集成](https://www.home-assistant.io/integrations/opple/)可作为现成选项，本仓库补充MT428专属证据。

## 资料、来源与致谢

- [研究、协议与证据分级](docs/research.zh-CN.md) · [English](docs/research.en.md)
- [路由器、ESP、MCP接入架构](docs/architecture.zh-CN.md) · [English](docs/architecture.en.md)
- [重要来源与相关项目](docs/sources.md)
- [第三方归属与许可来源链](THIRD_PARTY_NOTICES.md)
- [贡献指南](CONTRIBUTING.md) · [安全与隐私](SECURITY.md)

感谢 **jedmeng/python-oppleio** 的原始工作，以及legacy分支、Home Assistant与其他社区项目提供的线索。原仓库／发布包许可证与元数据存在不一致，本项目会保留来源链，不简单地把它们全称为MIT。

## 测试

测试使用合成报文、假传输、内存模拟灯及本机回环HTTP，**不需要连接或控制真实台灯**。

```sh
python -m unittest discover -s tests -v
node --check opple_mt428/static/app.js
```

可选安装：`python -m pip install .`，然后用 `opple-mt428` 代替 `python -m opple_mt428`。

## 许可证

**Apache-2.0**，见[LICENSE](LICENSE)、[NOTICE](NOTICE)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。研究表格是独立整理的协议事实。链接中的厂商资料权利归原权利人，不受本项目许可证重新授权。

检索关键词：OPPLE、欧普、欧普智慧灯光、MT428、MT428-D0.5×36+0.2×21-WTT、Huawei HiLink、华为智选、智慧生活、Broadlink、局域网控制、UDP55001、SKU0x50061、灯臂、侧灯、背景光、arm light、side light、CoAP组播、Home Assistant、ESP32、MCP。
