# Third-party notices · 第三方归属与许可

The project uses **Apache-2.0** for its implementation and documentation. Packet layouts and observations were independently organized into a new adapter, with conservative retention of the original pyoppleio Apache-2.0 provenance. No upstream package is installed at runtime or bundled unchanged. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

本项目按Apache-2.0发布，协议布局与观察结果重新组织为适配器，保守保留原始pyoppleio的Apache-2.0来源。无第三方运行时依赖，未原样打包上游软件包。

## Original protocol lineage / 原始协议来源

| Reference | Pinned revision | License-file finding |
| --- | --- | --- |
| [jedmeng/python-oppleio](https://github.com/jedmeng/python-oppleio) | [245cf932112d0c029d1932451db6fa1e0e2e784e](https://github.com/jedmeng/python-oppleio/tree/245cf932112d0c029d1932451db6fa1e0e2e784e) | [Apache-2.0 LICENSE](https://github.com/jedmeng/python-oppleio/blob/245cf932112d0c029d1932451db6fa1e0e2e784e/LICENSE); package metadata says MIT inconsistently |
| [tinysnake/python-oppleio-legacy](https://github.com/tinysnake/python-oppleio-legacy) | [90c57f778554fcf3a00e42757d0e92caebcfd149](https://github.com/tinysnake/python-oppleio-legacy/tree/90c57f778554fcf3a00e42757d0e92caebcfd149) | Current GitHub [LICENSE](https://github.com/tinysnake/python-oppleio-legacy/blob/90c57f778554fcf3a00e42757d0e92caebcfd149/LICENSE) says MIT; initial repository and PyPI 1.0.8 bundled LICENSE contain Apache-2.0 |
| [Home Assistant core / Opple](https://github.com/home-assistant/core/tree/dev/homeassistant/components/opple) | [447b0c194ac0859ebf1342a8c66a431e92649b37](https://github.com/home-assistant/core/tree/447b0c194ac0859ebf1342a8c66a431e92649b37/homeassistant/components/opple) | Project [Apache-2.0](https://github.com/home-assistant/core/blob/447b0c194ac0859ebf1342a8c66a431e92649b37/LICENSE.md); its separate dependency has its own provenance |
| [jedmeng/homebridge-opple](https://github.com/jedmeng/homebridge-opple) | [0a9773dbe2068163685533025ef8f10a3610852f](https://github.com/jedmeng/homebridge-opple/tree/0a9773dbe2068163685533025ef8f10a3610852f) | [Apache-2.0 LICENSE](https://github.com/jedmeng/homebridge-opple/blob/0a9773dbe2068163685533025ef8f10a3610852f/LICENSE), despite ISC package metadata |

The legacy fork's six core Python files match the original at the reviewed revisions. A later license-file change alone is not used here to erase that history. No project-specific original copyright header or separate NOTICE file was found in the reviewed original source; the author identifier `jedmeng` is retained as credit. The current legacy license's copyright and permission notice are also reproduced below for conservative attribution.

legacy分支核心源码与原版在审查版本一致，不能只看后续MIT声明就丢掉Apache来源链。本项目保留原作者标识及下列legacy当前许可文字；这不是对上游许可不一致问题作法律保证。

### Legacy fork's current MIT notice

```text
MIT License

Copyright (c) 2023 tinysnake

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Linked references only / 仅链接的研究项目

No code, test vectors, prose, vendor-extracted profiles, or assets from these projects are copied into this repository. Their licenses do not become the license of this project merely because they are cited.

| Project | Reviewed revision | Status |
| --- | --- | --- |
| [0xlic/ha-huawei-hilink-opple](https://github.com/0xlic/ha-huawei-hilink-opple) | [4e8eb8dce70663c440cbdb8cddbf90e2e4cd5a25](https://github.com/0xlic/ha-huawei-hilink-opple/tree/4e8eb8dce70663c440cbdb8cddbf90e2e4cd5a25) | No LICENSE/SPDX found; link and independent summary only |
| [teflux77/ha-opple-smart-desk-lamp](https://github.com/teflux77/ha-opple-smart-desk-lamp) | [3ce10fab25d268d8991808a48f0d2e7dc3ab67c4](https://github.com/teflux77/ha-opple-smart-desk-lamp/tree/3ce10fab25d268d8991808a48f0d2e7dc3ab67c4) | MIT, Copyright (c) 2026 Stéphane Kiès (teflux77); references the preceding unlicensed project, so its license is not assumed to authorize that source |
| [xiasi0/ha-huawei-smarthome](https://github.com/xiasi0/ha-huawei-smarthome) | [8b26b639aebb88cff4b8e0d2c8c5d6c06a47259e](https://github.com/xiasi0/ha-huawei-smarthome/tree/8b26b639aebb88cff4b8e0d2c8c5d6c06a47259e) | Project-declared GPL-3.0-only; no code or vendor-extracted profile files bundled |
| [Zer0wAve/ha-opple-local](https://github.com/Zer0wAve/ha-opple-local) | [feacbb92c4f00fbc01d2a0c7122a21366a6c2bdd](https://github.com/Zer0wAve/ha-opple-local/tree/feacbb92c4f00fbc01d2a0c7122a21366a6c2bdd) | MIT, Copyright (c) 2026 Zer0wAve; reference only |

## Proprietary vendor evidence / 厂商资料

Official Huawei help pages and the OPPLE-distributed app are linked for provenance. The repository contains independently written factual summaries, package identifiers/hashes, and protocol field observations. It does **not** distribute the APK, DEX, decompiled class bodies, SDK, extracted profile JSON, product photos, logos, or long quotations. No open-source redistribution license for the vendor app was established.

官方公开可下载不等于获得开源再分发许可。厂商材料权利仍归权利人；本仓库只整理必要事实与来源，不打包原材料。See [source index](docs/sources.md) / 见[来源索引](docs/sources.md)。

Python and its standard library are provided by the user's Python distribution, not bundled here. GitHub Actions used by name in CI retain their respective licenses.
