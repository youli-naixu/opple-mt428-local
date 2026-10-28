# Security and privacy · 安全与隐私

This is an experimental local-device research tool. It is not an authenticated production gateway. Only inspect/control devices you own or are authorized to test.

- Hardware mode defaults to read-only. Real writes require explicit `--allow-write`; independent side-light writes additionally require `--experimental-side-light`.
- The HTTP server binds loopback and validates Host/Origin. Keep it local. Do not expose it or the lamp UDP port directly to the Internet. A future authenticated service/private-network adapter needs a separate design.
- UDP discovery, CRC and MAC-derived XOR do not provide cryptographic authentication or confidentiality against a hostile LAN peer.
- A timer is owned by this process. Sleep, process termination or restart can delay/cancel it. It is not a safety-critical control.
- Parameter changes can briefly power on the light, even when the requested final state is off. Use read-only mode if any light change is unacceptable.
- Dedicated channel power, dimming, and unchanged-channel fields have passed physical-device protocol write/readback tests on one unit. Physical light mapping and optical behavior remain unobserved; the experimental endpoint distinguishes `protocol_verified` from visual verification and does not claim broad firmware compatibility.

If the repository exposes a security defect or secret, use the repository's **private vulnerability reporting** channel if available. Do not post credentials, local captures or identifying logs in a public Issue. If that channel is unavailable, open a minimal non-sensitive issue asking for a private contact; do not publish the exploit or secret while arranging contact.

中文：请仅研究自有或获授权设备。默认只读与回环监听不能替代生产鉴权；不要直接公网暴露。CRC／MAC编码不是安全认证。定时不适用于关键安全控制。任何亮灯都不可接受时保持只读。侧灯已完成一台样机协议写入与回读，光线效果仍需目视核对，不能外推其他固件。发现漏洞或凭据泄漏优先私下报告，不要在公开Issue贴原始抓包或敏感日志。
