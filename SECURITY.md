# Security and privacy · 安全与隐私

This is an experimental local-device research tool. It is not an authenticated production gateway. Only inspect/control devices you own or are authorized to test.

- Hardware mode defaults to read-only. Real writes require explicit `--allow-write`; independent side-light writes additionally require `--experimental-side-light`.
- The HTTP server binds loopback and validates Host/Origin. Keep it local. Do not expose it or the lamp UDP port directly to the Internet. A future authenticated service/private-network adapter needs a separate design.
- UDP discovery, CRC and MAC-derived XOR do not provide cryptographic authentication or confidentiality against a hostile LAN peer.
- A timer is owned by this process. Sleep, process termination or restart can delay/cancel it. It is not a safety-critical control.
- Parameter changes can briefly power on the light, even when the requested final state is off. Use read-only mode if any light change is unacceptable.
- Side-light physical mapping and unchanged-channel behavior remain unverified on the current firmware. The experimental endpoint does not claim hardware verification.

If the repository exposes a security defect or secret, use the repository's **private vulnerability reporting** channel if available. Do not post credentials, local captures or identifying logs in a public Issue. If that channel is unavailable, open a minimal non-sensitive issue asking for a private contact; do not publish the exploit or secret while arranging contact.

中文：请仅研究自有或获授权设备。默认只读与回环监听不能替代生产鉴权；不要直接公网暴露。CRC／MAC编码不是安全认证。定时不适用于关键安全控制。任何亮灯都不可接受时保持只读。侧灯候选字段仍需实物核验。发现漏洞或凭据泄漏优先私下报告，不要在公开Issue贴原始抓包或敏感日志。
