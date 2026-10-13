# Reference Analysis — `dwm_dashboard_developer.html`

Status: Phase 1 (read-only analysis). Source files inspected: `dwm_dashboard_developer.html`
(2,465 lines, single file, inline CSS+JS), `server.py` (746 lines), `terminal_server.py`,
`host_metrics.py`, `DEVELOPER.md`. Nothing here was executed against a robot; statements about
behaviour come from reading code, not from observed runs.

## 1. What the reference is

A single HTML page with three workspaces (User, Developer, plus navigation/map-editor/depth tabs).
Only the **Developer workspace** is in scope. It is a browser app that talks to a ROS 2 graph
through **rosbridge** (roslib 1.x, CDN) and to a **local Tornado backend** for filesystem, shell and
rosbag operations.

Page list (`names` array): Overview, Signals, Motion, Sensors, ROS Graph, TF Tree, Diagnostics,
Host Resources, Inspector, Services, Parameters, Publish, Logs, Rosbag, Files & Terminal.

## 2. Runtime dependencies of the reference

| Dependency | Where | Notes |
|---|---|---|
| rosbridge WebSocket (default `ws://localhost:9090`) | roslib `ROSLIB.Ros` | All live data. Dashboard URL is user-editable. |
| rosapi services | `/rosapi/topics`, `/rosapi/nodes`, `/rosapi/node_details`, `/rosapi/services`, `/rosapi/service_type` | Graph discovery. No QoS, no actions, no publisher/subscriber QoS. |
| ROS 2 parameter services | `ListParameters`, `GetParameters`, `SetParameters` via rosbridge | Typed ParameterValue JSON entered by hand. |
| Tornado backend (`server.py` / `terminal_server.py`) | `/terminal-api/*` | Token injected into served page as `<meta name="terminal-token">`. Loopback only, Host/Origin checks. |
| CDN assets | Tailwind play CDN, lucide@latest, roslib@1, xterm 5.5.0 | **Unpinned/CDN** — fails on offline robot LANs. New app must bundle. |
| `host_metrics.py` | publishes `/developer/host_metrics` (std_msgs/String JSON) | Custom node the user must start on the robot. |
| External web | `api.open-meteo.com`, browser geolocation | User-workspace feature; irrelevant, excluded. |

## 3. Feature inventory (Developer workspace)

**Connection.** Single rosbridge URL, connect/disconnect, link text in header, epoch counter that
discards stale async results after reconnect. Buffers reset on disconnect.

**Discovery & subscriptions.** `discover()` calls `/rosapi/topics`, then subscribes to a hard-coded
default list: `/odom /cmd_vel /wheel_rpm /imu/data /scan /battery_state /rosout /tf /tf_static
/diagnostics /developer/host_metrics`. Other topics are added through the Signals "Monitor" toggles
and the Inspector.

**Measurement.** `receive()` records per-topic count, last-arrival time and arrival timestamps in a
rolling **5-second** window (cap 2,000 samples) → Hz. Age = now − last arrival (browser clock).
Hz/age are *browser receipt* measurements through rosbridge, not DDS-level rates.

**Time series.** `add(key,value,t)`: numeric-only, finite-only, **10-minute** window, **12,000-point**
cap per key. Keys are hand-written strings per page (e.g. `odom linear`, `left RPM`).

**Pages.**
- *Overview*: metrics tiles, wheel feedback chart, command-vs-response chart, quick read, stream activity.
- *Signals*: topic table (type, Hz, count, age, monitor toggle).
- *Motion*: left/right RPM, mean RPM, wheel linear speed (radius **0.095 m**), wheel difference,
  command-minus-measured linear velocity, command/odom linear & angular, odometry XY trajectory canvas, position history.
- *Sensors*: IMU orientation (roll/pitch/yaw), accel, gyro; LiDAR canvas, nearest return, invalid %; battery voltage and charge %.
- *Camera* (visualization toggle): `/camera/image_raw/compressed` (CompressedImage) rendered to canvas. Visualization buttons: camera / lidar / imu.
- *ROS Graph*: explicit refresh; nodes → topics → subscribers; click node highlights edges.
- *TF Tree*: parent→child from `/tf` and `/tf_static`; shows transform values and browser-receipt age; static frames never age out.
- *Diagnostics*: DiagnosticArray from `/diagnostics`, plus "stale topic" hints (default topics silent > 3 s; excludes `/tf_static`, `/rosout`).
- *Host Resources*: renders JSON from `/developer/host_metrics`.
- *Inspector*: pick any topic, raw JSON view, pause freezes rendering (collection continues).
- *Services*: discover, pick, enter type + JSON request, call once.
- *Parameters*: list/get/set for a node via parameter services.
- *Publish*: manual publish once per click, advertise-on-demand, JSON object only.
- *Logs*: `/rosout` (`rcl_interfaces/Log`) buffer.
- *Rosbag*: record / stop / play / stop / list, driven by `/terminal-api/rosbag/*` (see §5).
- *Files & Terminal*: read-only directory browser (64 KB UTF-8 preview) + xterm over WebSocket PTY or SSH. Up to 4 shells.
- *Export*: JSON of series, topic counts and logs ("ROS bridge browser receipt").

**Also in the file, out of scope:** User workspace (joystick/keyboard teleop, relay, weather), 2D navigation
(`/nav-api`, `navigation_2d.html`), map editor, OAK depth navigation (`/oak-proxy`, `/api/state`, `/api/goal`…).

## 4. Classification

| Category | Items |
|---|---|
| Browser-only logic (reusable as algorithms) | Hz window math, bounded series, TF frame table, diagnostic staleness hints, JSON export |
| Requires rosbridge | All live subscriptions, services, parameters, publish |
| Requires custom backend | Files, shell, rosbag, host metrics collector |
| Depends on DWM topics/format | `/wheel_rpm` (`Float32MultiArray`-like, `data[0..1]`), `/relay_cmd`, wheel radius 0.095 m, two-wheel assumption, hard-coded series names, `/developer/host_metrics` |
| Hard-coded message formats | Odometry/Twist/Imu/LaserScan/BatteryState/CompressedImage field access by name |
| Incomplete / unverifiable | See §6 |

## 5. Rosbag backend — corrected finding

An earlier draft of this analysis stated the rosbag backend was missing. **That was wrong.**
`terminal_server.py` has no rosbag route, but the uploaded `server.py` does:
`/terminal-api/rosbag/(state|record-start|record-stop|play-start|play-stop)`.

What it does (from reading, not running):
- Wraps the CLI: `ros2 bag record -o <root>/bags/<name> [topics | -a]` and `ros2 bag play <path> --rate N [--loop]` as subprocesses, one of each at a time, with a 200-line rolling log tail.
- Topic names validated by regex `/[A-Za-z0-9_/]+`; bag names sanitised; bags confined to `<root>/bags`.
- Bag metadata is read by **regex over `metadata.yaml`** (duration, topic names, message counts) — fragile; no YAML parser, no message access.
- Playback publishes into a ROS graph on a **separate ROS_DOMAIN_ID (default 187)** with localhost-only discovery, which the dashboard then reads through a second rosbridge (`/rosbridge/replay`). Visualisation of a bag therefore requires replay.
- Recording over SSH is explicitly unsupported.

**Consequence for the new project:** the *replay-through-a-second-graph* model contradicts the requirement
that offline analysis not need a ROS graph or rosbridge. The new implementation reads bags directly with
`rosbag2_py` (§ARCHITECTURE). `server.py` is a useful reference for safety ideas (confined directory,
domain isolation, rolling log, sanitised names) only. Recording may still shell out to `ros2 bag record`
or use `rosbag2_py.Recorder` — to be decided in Phase 4 after testing on Humble and Jazzy.

## 6. Unverified / incomplete in the reference

- No test run against hardware or a real bridge (DEVELOPER.md says so explicitly).
- Per-core CPU is collected but not charted. Host GPU limited to `nvidia-smi` (no Jetson `tegrastats`/jtop).
- `rosapi` provides no QoS, no actions, no per-endpoint info; incompatible-QoS detection is impossible with this path.
- Message schemas are not validated beyond "JSON object".
- Images: only CompressedImage; raw `Image` not handled.
- No zoom/pan, no CSV export, no saved layouts, no session replay.
- Frequency measured in browser → inflated latency/jitter and rosbridge throttling are invisible.
- Host metrics arrive as a ROS String, so they cannot be used without a ROS bridge and are not label-checked as "robot host vs. browser host".

## 7. Reusable vs. refactor

**Reuse (ideas/algorithms):** windowed Hz, bounded series, pause-freezes-render semantics, epoch guard against stale async results,
explicit-click service/publish, explicit graph refresh, TF age semantics, token + Host/Origin checks, symlink-escape rejection, localhost-only binding.

**Refactor:** all robot-specific keys to configurable field mappings; rosapi → native `rclpy` graph API; roslib JSON → server-side introspection with typed
payloads; CDN → bundled assets; ad-hoc string-built HTML → React components.

**Drop:** User/Nav/Map/Depth workspaces, weather, relay, joystick.
