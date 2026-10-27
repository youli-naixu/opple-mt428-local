# HTTP API · 接口

The demo binds 127.0.0.1 only. Default hardware mode is read-only. It is a development server, not a publicly exposed authenticated gateway. / 仅监听本机；实物默认只读，不应直接作为公网网关。

| Method | Path | JSON request | Behavior |
| --- | --- | --- | --- |
| GET | `/api/status` | none | Real SEARCH/QUERY or simulation; returns online/state/initial_state/capabilities/activity/mode |
| GET | `/api/health` | none | Process health only, not device reachability |
| POST | `/api/control` | `{"power":true,"brightness":128,"color_temp":4000}` | Partial fields accepted; writes then checks readback |
| POST | `/api/scene` | `{"id":"reading"}` | Local parameter combination; also screen/relax |
| POST | `/api/timer` | `{"minutes":30}` | Process-owned off timer, 1..120 minutes |
| DELETE | `/api/timer` | none | Cancel process timer |
| POST | `/api/restore` | `{}` | Cancel timer, restore session's initial legacy state |
| POST | `/api/experimental/side-light` | `{"power":true}` or `{"brightness":102}` | Explicitly gated, single write, candidate readback only |

Send `Content-Type: application/json` for POST. Browsers must be same-origin. No CORS wildcard is provided. Explicitly validate status/response fields in a client; HTTP arrival does not imply physical execution.

Status mode fields: `read_only`, `simulated`, `experimental_side_light`. `state.observed_at` is an ISO UTC timestamp. When `online=false`, `state` may be an older value and must not be displayed as current. `device.version` is a raw version word, not a decoded semantic version.

Legacy control success: `ok:true, verified:true`; verification is protocol state readback (CCT tolerance80K, brightness tolerance2 raw steps), not a photometric measurement. Simulation can return verified state but `simulated:true` always distinguishes it from hardware.

Experimental response: `ok:true, experimental:true, verified:false, candidate_readback_matched:bool`. This deliberately never claims hardware acceptance. Experimental channel values live under `state.experimental_channels` with an evidence label. Failures return4xx/5xx and a message; transport-offline replies may include last state.

侧灯字段候选来自公开发行App的静态证据。开启实验功能仍不代表当前固件的“保持其他光源”语义已验证；不要让自动化把候选字段匹配直接提升为已验证状态。普通恢复只覆盖旧版开关／亮度／色温，不保证还原实验侧灯状态。

Known quirk / 已知行为：legacy dimming may temporarily power on an off lamp. The server serializes operations and tries to return to off after temporary parameter changes. A transport failure can still leave unknown physical state; inspect before retrying.
