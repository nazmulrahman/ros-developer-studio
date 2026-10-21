# Feature Matrix

Verification: ☐ not implemented/unverified · ◐ implemented, automated tests against a controlled fake (no real ROS 2, UI not browser-tested) · ✔ verified on a real ROS 2 system (none yet).

Legend — **Preserved**: same behaviour kept · **Improved**: kept and extended · **Replaced**: new mechanism, same user goal ·
**Deferred**: planned, later phase · **Excluded**: intentionally not carried over.
"Verified" stays ☐ until tested; no row is marked done by scaffold alone. Phases refer to ARCHITECTURE.md §10.

| # | Reference feature | Reference mechanism | New status | New mechanism / change | Phase | Verified |
|---|---|---|---|---|---|---|
| 1 | Connect to ROS | rosbridge URL | Replaced | Agent (rclpy) ↔ backend; browser talks only to backend. No rosbridge. | 2 | ◐ fake-ROS tests |
| 2 | Topic discovery | `/rosapi/topics` | Improved | `rclpy` graph API: types, pub/sub counts, QoS, namespaces | 2 | ◐ fake-ROS tests |
| 3 | Default hard-coded subscriptions | list of 11 DWM topics | Excluded | No auto-subscribe. User opt-in, bandwidth warnings | 2 | ◐ fake-ROS tests |
| 4 | Signals table (Hz, count, age, monitor) | browser 5 s window | Improved | Agent-side arrival window, documented, plus no-publisher / no-data / QoS-mismatch states | 2 | ◐ fake-ROS tests |
| 5 | Inspector (raw JSON, pause) | roslib message | Improved | Nested tree, search, copy, field select, export, frequency history, size/bandwidth | 2 | ◐ fake-ROS tests |
| 6 | Pause freezes rendering, not collection | UI flag | Preserved | Same semantics, per-view | 2 | ◐ fake-ROS tests |
| 7 | Bounded time series (10 min / 12k pts) | JS arrays | Improved | Configurable ring buffers, decimation; shared by live and bag | 3 | ☐ |
| 8 | Signals graphs | hand-keyed series | Replaced | User-chosen numeric field paths from any topic; labels; overlay; zoom/pan; min/max/avg/latest; CSV; saved configs | 3 | ☐ |
| 9 | Motion (RPM, wheel speed, cmd vs odom, trajectory) | `/wheel_rpm`, `/cmd_vel`, `/odom`; r=0.095 m | Replaced | Motion widgets driven by field mappings; wheel count/radius user-configured; no DWM defaults | 3 | ☐ |
| 10 | Sensors: IMU | `/imu/data` | Preserved | Imu adapter (orientation, accel, gyro) | 3 | ☐ |
| 11 | Sensors: LiDAR canvas | `/scan` | Preserved | LaserScan adapter, decimated | 3 | ☐ |
| 12 | Sensors: battery | `/battery_state` | Preserved | BatteryState adapter | 3 | ☐ |
| 13 | Camera (CompressedImage) | canvas | Improved | CompressedImage + raw Image, server-side downscale/rate limit | 3 | ☐ |
| 14 | Odometry plot / trajectory | `/odom` | Preserved | Odometry adapter | 3 | ☐ |
| 15 | ROS Graph | rosapi nodes/details, list view | Improved | Nodes↔topics graph view, filters, search, QoS, actions | 2 | ◐ fake-ROS tests |
| 16 | TF Tree | `/tf` `/tf_static` parse | Improved | Merged hierarchy, roots/groups, transform details, stale/cycle/multiple-parent/invalid-rotation diagnostics | 3 | ✔ Humble fixture + browser |
| 17 | Diagnostics page | `/diagnostics` + stale hints | Improved | Findings with severity/evidence/causes/checks, numeric expectation profiles, incident-window correlation and navigation | 5 | ☐ |
| 18 | Logs | `/rosout` buffer | Preserved | Bounded live log capture/view with level and text filters; report correlation | 5 | ☐ |
| 19 | Host Resources | `host_metrics.py` → String topic | Replaced | Agent collector served over backend (no ROS topic). Adds per-core charts, uptime, processes, disk free, Jetson telemetry. Labeled with host name | 2 (basic) / 5 | ◐ fake-ROS tests |
| 20 | Services console | type + JSON, call once | Preserved | Schema-aware request form; explicit enable (Test Tools) | 6* | ☐ |
| 21 | Parameters list/get | param services | Improved | Read in Explorer (read-only) | 3 | ☐ |
| 22 | Parameters set | `SetParameters` | Preserved | Test Tools only, disabled by default | 6* | ☐ |
| 23 | Manual publish | advertise + publish once | Preserved | Test Tools, schema validation, disabled by default | 6* | ☐ |
| 24 | Velocity test w/ timeout | (User workspace teleop) | Replaced | Short timed command + auto zero; warning that it is not a safety system | 6* | ☐ |
| 25 | Export JSON | series/topics/logs | Improved | CSV + JSON of selected data; message export | 3 | ☐ |
| 26 | Rosbag record | `ros2 bag record` subprocess | Replaced | Backend-managed recorder, topic picker, status, size, errors | 4 | ◐ API tested; live recording pending |
| 27 | Rosbag play (into replay domain 187) | `ros2 bag play` + 2nd bridge | Replaced | Direct file reads; no ROS graph needed. Live-graph replay is a future opt-in | 4 | ✔ Humble SQLite3 fixture |
| 28 | Rosbag list / metadata | regex over metadata.yaml | Replaced | SQLite read-only queries + metadata; MCAP through `rosbag2_py` where installed | 4 | ◐ SQLite3 verified; MCAP pending |
| 29 | Bag seek / speed / step / timeline | — | New | Browser timeline over bounded message windows | 4 | ◐ build + API tests |
| 30 | Bag analysis (gaps, discontinuities, per-topic Hz) | — | New | Bounded on-demand timestamp analysis | 4–5 | ✔ Humble SQLite3 fixture |
| 31 | Files browser (read-only) | Tornado `/terminal-api/list,preview` | Replaced | Configured restricted bag library; general file browser remains out of scope | 4 | ◐ root escape tests |
| 32 | Embedded shell (PTY/SSH) | xterm + Tornado | Deferred | Off by default; separate explicit enable + auth if ever added | post-V1 | ☐ |
| 33 | Token + Host/Origin + loopback bind | Tornado | Preserved | FastAPI auth dependency, WS origin check, loopback default | 2 | ◐ fake-ROS tests |
| 34 | Symlink-escape protection | resolve + commonpath | Preserved | Same rule for bag directories | 4 | ◐ automated tests |
| 35 | Saved layouts / preferences | — (none) | New | Backend JSON store | 3 | ☐ |
| 36 | QoS incompatibility detection | — (impossible via rosapi) | New | `rclpy` endpoint info | 5 | ☐ |
| 37 | Offline bag mode | — | New | Mode B, first-class Bag Studio | 4 | ✔ Humble SQLite3 fixture |
| 38 | User workspace (teleop, relay, weather) | — | Excluded | Not a developer feature | — | n/a |
| 39 | 2D navigation / goals | `/nav-api` | Excluded | Out of scope | — | n/a |
| 40 | Map editor | `map_editor.html` | Excluded | Out of scope | — | n/a |
| 41 | OAK depth navigation | `/oak-proxy` | Excluded | Out of scope | — | n/a |
| 42 | CDN-loaded libs | Tailwind/roslib/lucide/xterm | Replaced | All bundled via npm; works on offline LAN | 1 | ☐ |

\* Test Tools are optional; they ship after the read-only core, but are listed in Phase 6 so the read-only product is complete first.

## Reference features that could not be verified from supplied files
- Exact `/wheel_rpm` message type (code reads `m.data[0..1]`; type not confirmed).
- Behaviour of the rosbridge proxy and `replay.html` (`/rosbridge/replay`) — `replay.html` was not supplied.
- Whether `host_metrics.py` values match what the Host page expects field-for-field.

## Phase 2 implementation status

| Capability | Implemented | Automated test | Real ROS 2 | Notes / limits |
|---|---|---|---|---|
| Agent ↔ backend link, reconnect, resync of watches | yes | yes (incl. agent restart) | n/a | JSON over loopback WebSocket (not msgpack) |
| Agent/ROS/discovery status (distro, domain, RMW) | yes | yes | no | distro/domain read from environment variables |
| Graph: nodes, topics+types, pub/sub counts, services, actions | yes | yes | **no** | actions use `rclpy.action` helper; failure degrades with a warning |
| Topic endpoints + QoS, QoS conflict detection | yes | yes (conflict rules, endpoints) | **no** | conflicts are between *other* graph endpoints |
| Dynamic subscription (raw, BEST_EFFORT/VOLATILE), refcounted, released on viewer close | yes | yes | **no** | raw subscription = no deserialization for statistics |
| Hz / period / jitter / bandwidth / size / status enum | yes | yes (math, window, high rate) | no | 5 s arrival window at the agent |
| Unsupported / missing message type | yes | yes | no | stats still available only if subscription succeeds; payload/fields report error |
| Numeric field schema + extraction + array indexes | yes | yes | no | uses `get_fields_and_field_types()`; fixed arrays ≤32 expanded, sequences need an index |
| Explorer, Inspector, Signals, Host, Overview UI | yes | build + type-check only | no | **UI not exercised in a browser** |
| Host metrics (psutil, GPU nvidia-smi, Jetson sysfs) | yes | yes (psutil real; GPU absent path) | n/a | Jetson sysfs path is best-effort and **unverified on hardware**; no `jtop`/tegrastats |
| Live CSV export, zoom/pan, pause | yes | no | n/a | client-side; untested in browser |
| Series buffers | yes | no | n/a | 10 min / 12 000 points per series; reset when leaving Signals |

## Phase 3 status update — 2026-10-13 (supersedes earlier unverified labels)

The user confirmed Phase 2 topic discovery/live messages in their demo-node run. A local real-Humble synthetic fixture and browser checks now cover Motion mappings, Image, LaserScan, Imu, BatteryState, Odometry, Twist, read-only parameters and TF relationships. Signals plotting predates this increment. Layout/preferences persistence has API and browser verification. Camera conversion/limits and sampled sensor handling have unit tests.

| Reference rows | Current result | Limits |
|---|---|---|
| 9 | Configurable Motion widgets and measured/reference plots | Up to 16 widgets; no geometry inference, unit conversion or cross-topic synchronization; generic numeric motor status only |
| 10–14 | IMU, scan, battery, camera and odometry viewers | Standard supported encodings; bounded sampled previews; no depth image rendering |
| 16 | Unified TF hierarchy and diagnostics | Merges watched TFMessage topics, retains late static delivery, and reports structural/age/rotation faults; bounded observation model rather than historical TF2 lookup |
| 21 | Read-only parameter inspection | Up to 500 names; bounded values, 3-second service timeout |
| 35 | Settings + backend saved workspace layouts | Sampling/freshness settings and widget/series definitions; no credentials, live data, window geometry or dock layout |

Phase 4 is implemented. Its direct SQLite3 read path is verified with a real Humble-generated bag; MCAP, live recording, Jazzy and hardware acceptance remain. Phase 5 implementation is present; its live/runtime and browser acceptance are pending. Phase 6 remains deferred.

Phase 5 implementation is present; live/runtime and browser acceptance are pending. Logs are retained in bounded process-memory buffers and are not an archival store.
