# LAN discovery · 局域网发现

[English README](../README.md) · [中文说明](../README.zh-CN.md)

## EN

1. Preserve the lamp's existing Wi-Fi provisioning. The tested model uses 2.4 GHz Wi-Fi; this tool does not perform provisioning, account binding, firmware updates, or reset.
2. Check the router's DHCP leases if available. Match the device label/MAC and connection time; a Broadlink hostname alone does not prove identity or protocol compatibility.
3. Identify your computer's active LAN IPv4 address **and prefix**. Avoid VPN, container, or disconnected interfaces. The default route does not necessarily identify the correct broadcast interface.
4. Replace this TEST-NET example with your own local interface address, then run:

   ```sh
   python -m opple_mt428 discover --interface 192.0.2.10/24 --json
   ```

   One UDP SEARCH is sent to that interface's directed broadcast on port55001. Valid replies are collected until the bounded deadline. There is no per-address subnet sweep and no light-changing command.

5. If router leases already provide the lamp IP, skip broadcasting:

   ```sh
   python -m opple_mt428 discover --target 192.0.2.42 --json
   ```

   With multiple routes, add `--bind YOUR_LOCAL_IPV4` to direct discovery. The selected source address must exist on your computer.

6. Select a candidate explicitly. Compare MAC with router/label, check model separately, then use its IP and MAC in `status` / `serve`. Do not automatically control the first discovery response. Unknown SKUs are returned but not assumed compatible. Duplicate MACs at different endpoints are marked non-controllable.
7. First inspect with `status` or default read-only `serve`. Only pass `--allow-write` when intentional light changes are acceptable.

### Validation

SEARCH is `0x02010000`; expected response is `0x02020000`. The receiver checks serial, CRC16-XMODEM, the complete message/package lengths, source port55001, body source-IP agreement, MAC validity and minimum identity body length. Name decoding uses GBK, removes NUL/`@` padding, and tolerates malformed text. It preserves the two bytes after the six-byte MAC as unknown metadata. Discovery has no SKU filter and returns candidates rather than write-enabled handles.

The 4096-byte parser cap is an implementation limit, not a protocol standard. Reply validation reduces accidental mismatches; unauthenticated UDP and MAC-based XOR do not establish a cryptographic identity.

### No results?

- Check power, 2.4GHz association, client/AP isolation, VLANs, the chosen mask and host firewall.
- Prefer known-IP unicast when broadcast does not cross your bridge/VPN. The tool does not configure multicast/broadcast relays or firewalls.
- A quiet lamp may ignore a packet. Repeat the explicit discovery command; do not blindly try control commands.
- A device can have a local interface even while it also talks to a cloud service. Conversely, a familiar hostname/model prefix does not prove support.
- Do not use a failed generic CoAP probe as proof that the lamp lacks OPPLE UDP control.

## 中文

先保留已有配网，确认2.4GHz连接正常。可以从路由器DHCP租约找IP，再核对MAC、连接时间和铭牌；`Broadlink-*` 名称只是线索。

广播发现需要明确指定**电脑网卡的IP/前缀**。用 `ipconfig`、`Get-NetIPAddress`、`ip -4 address` 或系统网络设置查找，避开VPN、容器和断开连接的虚拟网卡。示例 `192.0.2.10/24` 是文档地址，必须替换。

`discover --interface ...` 只向该接口的定向广播55001发一条SEARCH，在限定时间内收集多个合法应答；不逐个扫描网段、不发送QUERY或写入。已知台灯IP时用 `discover --target ...` 单播，可加 `--bind` 指定本机源地址。

工具检查报文类型、响应序号、CRC、两个长度、源端口、包内IP、MAC和字段边界。旧库的单SKU白名单已移除，未知SKU也会列出，不会因此自动变成可控制设备；相同MAC对应多个端点时禁止自动控制。

发现后按MAC显式选择，先运行 `status` 或默认只读网页，确认自己有意改变灯光时才加 `--allow-write`。UDP与MAC编码不提供密码学认证，不能当安全隔离边界。

无结果时依次检查供电、Wi-Fi关联、AP隔离、VLAN、掩码、网卡和主机防火墙；广播通常不跨普通VPN，优先用已知IP单播。设备可能漏回UDP，可重新执行明确的只读发现，不盲试写命令。工具不替你修改路由器、防火墙或配网。

**不要把发现JSON、真实MAC、设备名、原始抓包直接发到Issue。** 先按[贡献指南](../CONTRIBUTING.md)脱敏。
