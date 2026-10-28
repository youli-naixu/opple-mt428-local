# OPPLE MT428 Local · 欧普台灯局域网控制

[English](README.md)

通过局域网控制 **MT428-D0.5×36+0.2×21-WTT 华为 HiLink 欧普读写台灯**，提供设备发现、命令行查询和本地网页面板。台灯完成 Wi-Fi 配网后，使用本地 UDP 接口通信，无需为本工具提供华为或欧普云账号凭据。

![网页面板预览（模拟模式）](docs/images/demo-simulation.png)

## 功能

- 灯光开关、主灯亮度和 2700–6500 K 色温调节。
- 侧灯独立开关与亮度调节，需要启用实验通道选项。
- 状态刷新、本地场景、定时关灯和恢复启动时状态。
- 局域网设备发现，支持指定网卡广播或已知 IP 单播。
- 无需实物即可运行的模拟模式。

## 安装与运行要求

- Python **3.10 或更新版本**，无第三方运行时依赖。
- 台灯已接入 2.4 GHz Wi-Fi，电脑能够访问台灯所在局域网。

```sh
git clone https://github.com/youli-naixu/opple-mt428-local.git
cd opple-mt428-local
```

以下命令均在仓库根目录运行。也可用 `python -m pip install .` 安装，再用 `opple-mt428` 代替 `python -m opple_mt428`。

## 使用方法

### 1. 发现台灯

先用 `ipconfig`（Windows）、`ip -4 address`（Linux）或系统网络设置，查看**电脑网卡的 IPv4 地址与前缀**：

```sh
python -m opple_mt428 discover --interface 192.0.2.10/24 --json
```

如果已经从路由器 DHCP 租约中找到台灯 IP，可直接查询该地址：

```sh
python -m opple_mt428 discover --target 192.0.2.42 --json
```

发现结果包含 IP、MAC 和 SKU。核对设备身份后，将结果用于后续命令。发现过程不会改变灯光。

**示例中的 `192.0.2.*` 和 `02:00:00:00:00:01` 是占位值，必须替换为自己的网卡或台灯信息。** 多网卡、VPN 或发现失败时，参阅[设备发现与排错](docs/discovery.md)。

### 2. 查询状态

```sh
python -m opple_mt428 status --ip 192.0.2.42 --mac 02:00:00:00:00:01
```

### 3. 打开网页控制面板

启用真实控制和主灯／侧灯分通道功能：

```sh
python -m opple_mt428 serve --ip 192.0.2.42 --mac 02:00:00:00:00:01 --allow-write --experimental-side-light
```

打开 **http://127.0.0.1:8765/**。拖动滑块只改变预览，点击应用后才向台灯发送命令。侧灯在独立区域控制。

只查看真实状态、不允许改变灯光时，省略 `--allow-write`：

```sh
python -m opple_mt428 serve --ip 192.0.2.42 --mac 02:00:00:00:00:01 --experimental-side-light
```

实物模式默认只读。`--experimental-side-light` 用于启用专用通道支持，不能单独授予写入权限。使用 `--port 8766` 可更改网页端口，按 `Ctrl+C` 停止服务。

### 4. 不连接实物预览页面

```sh
python -m opple_mt428 serve --simulate --experimental-side-light
```

模拟模式只更新内存状态，不连接真实台灯。

## 使用说明与限制

- 当前适配型号为上述完整型号、SKU `0x50061`；其他 MT428 后缀或固件不保证兼容。侧灯功能保留实验标记，使用时核对实际灯光效果。
- 总电源表示至少一路光源开启；主灯与侧灯状态分别显示。亮度百分比由原始值换算，不保证与官方 App 刻度一致。
- 专用通道页面使用主灯 10–100%、侧灯原始值 25–255。调整参数可能改变灯光；旧版控制路径在关灯调参时可能短暂开灯。
- 定时由当前电脑进程执行，休眠、退出或重启可能影响执行。恢复功能只还原本次服务启动时保存的已知字段。
- 本工具不提供 Wi-Fi 配网、固件更新，以及原厂模式、灯内计划、番茄钟或指示灯设置。
- 网页仅监听本机。接口调用见 [HTTP API](docs/api.md)，请勿直接暴露到公网。分享日志前删除真实 IP、MAC、设备名及账号信息。

## 资料来源与致谢

| 来源 | 用途 |
| --- | --- |
| [jedmeng/python-oppleio](https://github.com/jedmeng/python-oppleio) | 欧普本地 UDP 报文格式及基础控制实现 |
| [tinysnake/python-oppleio-legacy](https://github.com/tinysnake/python-oppleio-legacy) | 旧版欧普本地控制库 |
| [Home Assistant Opple](https://www.home-assistant.io/integrations/opple/) | 欧普灯具的现成本地集成及使用说明 |
| [华为型号表](https://consumer.huawei.com/cn/support/content/zh-cn15885815/)与[功能说明](https://consumer.huawei.com/cn/support/content/zh-cn13251283/) | 完整型号、主侧灯及 App 功能说明 |
| [欧普官方下载专区](https://www.opple.com.cn/news/download/) | “欧普智慧灯光”应用分发入口，专用通道接口的资料来源 |

更多链接见[来源索引](docs/sources.md)。第三方归属及许可差异见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。仓库不分发厂商 APK、SDK、固件或提取资源。

## 许可证

[Apache-2.0](LICENSE)，并保留 [NOTICE](NOTICE) 中的归属声明。本项目与欧普、华为及相关品牌无隶属或认可关系。
