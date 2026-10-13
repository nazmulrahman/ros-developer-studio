# ROS Developer Studio — Architecture (review draft)

Scope: observability, diagnostics, offline analysis and optional controlled tests for **one** ROS 2 environment (Humble, Jazzy).
Not an operator UI. No navigation/mapping/missions/fleet/cloud.

## 1. Principles
1. Read-only by default; every write path is separately gated.
2. Live and recorded data share one normalized sample model and one set of visualization components.
3. No hard-coded topics. Discovery is dynamic; widgets use user field mappings.
4. Offline mode needs **no ROS graph, no agent, no rosbridge**.
5. Two Python processes at most (backend, agent). No Docker, no message broker, no database server.
6. Don't claim what wasn't measured; findings carry evidence.

## 2. Components

```
 Browser (React/TS/Vite)
     │  REST + WebSocket (token auth, loopback by default)
     ▼
 Backend  (FastAPI, Python) ──────────────  works without ROS installed*
   ├─ api/            REST + WS routers (thin)
   ├─ core/           config, auth, session, ring buffers, normalized Sample, logging
   ├─ data_sources/   LiveSource (talks to agent) · BagSource (rosbag2_py)  ← same interface
   ├─ bags/           bag library, indexer, offline player, recorder control
   └─ diagnostics/    rule engine over Samples/stats (source-agnostic)
     │  loopback WebSocket, msgpack frames (agent is the server)
     ▼
 Agent  (rclpy, Python, runs on robot host)  — Live mode only
   ├─ ros_graph/      nodes, topics, services, actions, QoS, endpoint info
   ├─ subscriptions/  opt-in generic subscriptions, rate-limited, bounded queues
   ├─ host_metrics/   psutil + optional Jetson/NVIDIA
   └─ processes/      process table, (later) recorder/test-tool executors
```
\* Offline analysis needs `rosbag2_py` + message packages for deserialization, not a running graph. The backend degrades to metadata-only if types are missing.

### Why a separate agent (and not rosbridge)
- rclpy needs the sourced ROS environment and its own executor; isolating it keeps the FastAPI event loop unblocked.
- Native `rclpy` gives QoS, endpoint info, actions and typed deserialization that rosapi cannot.
- Backend can run on a laptop for offline analysis without ROS or on the robot with the agent. In V1 the agent defaults to `127.0.0.1:8770`; LAN exposure of the agent is not supported (only the backend is exposed).
- Cost: one small internal protocol (§6). Accepted.

## 3. Operating modes
| | Live Robot Analysis | Offline Bag Analysis |
|---|---|---|
| Data source | `LiveSource` → agent | `BagSource` → `rosbag2_py` |
| Needs agent / ROS graph | yes | **no** |
| Time axis | wall clock, receive time | recording timeline, seek/play |
| Stats | measured arrival Hz (window documented) | recorded counts + computed intervals; never presented as live Hz |
| Host metrics | agent host | **absent** unless recorded in the bag |
| Write tools | optional Test Tools (gated) | none, ever |

Mode is a property of the session (`/api/session`), shown permanently in the top bar. Switching mode stops the other source.

## 4. Normalized sample (the shared data contract)
```
Sample {
  source_mode : "live" | "bag"
  source_id   : str            # "live:<host>" or "bag:<bag_id>"
  topic       : str
  type        : str            # e.g. "sensor_msgs/msg/Imu"
  stamps      : { header_ns?: int, receive_ns?: int, record_ns?: int }   # three distinct clocks, never merged
  payload     : dict | bytes-ref   # decoded fields, or a reference for large blobs (images)
  meta        : { size_bytes?: int, seq?: int, qos?: {...}, decode_error?: str }
}
```
- Numeric field extraction (`topic` + dotted `field path`) is done in the backend into **columnar float arrays** `(t[], v[])`; plots receive arrays, not per-message JSON.
- Images/scans are decimated server-side (rate and resolution caps) and sent as binary frames.
- Frontend adapters (Imu, LaserScan, Image, TF, …) consume `Sample`s and do not know whether the source is live or bag.
- Buffers: backend per-topic ring buffers (count and bytes caps, configurable); frontend per-series ring buffers with decimation.

## 5. Frequency & health semantics
- Live Hz = arrivals at the agent over a sliding **5 s window** (configurable); period and jitter reported with it. Bandwidth = Σ serialized size / window. Documented in UI tooltip.
- Topic status (explicit enum): `no_publisher` · `publisher_no_data` · `qos_incompatible` · `receiving` · `unknown` (not subscribed / not measured). A topic is never "healthy" merely because it exists.
- Bag stats: counts from metadata; intervals/gaps computed by indexer; labelled "recorded".
- Subscriptions are opt-in. High-bandwidth types (Image, PointCloud2) show a warning and default to rate-limited.

## 6. Agent ↔ backend protocol
Loopback WebSocket, shared token. Control = JSON `{id, op, args}` → `{id, ok, result|error}`. Data = msgpack frames `{ch, ...}`.
Ops: `graph.snapshot`, `topic.info`, `sub.start`, `sub.stop`, `sub.list`, `host.start|stop`, `tf.snapshot`, `logs.tail`, `bag.record.*`, `test.*` (gated).
Channels: `sample`, `stats`, `host`, `log`, `diag`. Backpressure: bounded per-client queues, drop-oldest with a counted `dropped` field exposed in the UI.

## 7. API design (summary; full generated schema at `/docs`, snapshot in `docs/openapi.json`)
Auth: `Authorization: Bearer <token>` (REST) / `?token=` (WS). Token generated at start, printed once, never stored in source. Default bind `127.0.0.1`; LAN needs `--host` plus explicit config.

| Area | Endpoints |
|---|---|
| Core | `GET /api/health` · `GET /api/session` · `POST /api/session/mode` · `GET/PUT /api/settings` |
| Live graph | `GET /api/live/status` · `GET /api/live/graph` · `GET /api/live/topics` · `GET /api/live/topic?name=` · `GET /api/live/services` · `GET /api/live/actions` · `GET /api/live/nodes/{node}/parameters` |
| Live data | `POST /api/live/subscriptions` · `DELETE /api/live/subscriptions/{id}` · `GET /api/live/subscriptions` · `GET /api/live/topic/stats?name=` · `WS /ws/live` |
| Series | `POST /api/series/query` (live buffer or bag range, field paths → arrays) · `POST /api/series/export` (CSV/JSON) |
| TF / logs | `GET /api/live/tf` · `GET /api/live/logs` |
| Host | `GET /api/host/metrics` · `GET /api/host/processes` · `WS /ws/live` channel `host` |
| Bags | `GET /api/bags` · `POST /api/bags/open` · `GET /api/bags/{id}/metadata` · `GET /api/bags/{id}/topics` · `GET /api/bags/{id}/messages` · `POST /api/bags/{id}/export` · `GET /api/bags/{id}/analysis` · `WS /ws/bag/{id}` (play/pause/seek/rate/step) |
| Recording | `GET /api/record/status` · `POST /api/record/start` · `POST /api/record/stop` |
| Diagnostics | `GET /api/diagnostics/findings?source=` |
| Layouts | `GET/POST /api/layouts` · `PUT/DELETE /api/layouts/{id}` |
| Test tools (gated) | `GET /api/testtools/state` · `POST /api/testtools/enable` · `POST /api/testtools/publish` · `POST /api/testtools/service` · `POST /api/testtools/velocity` · `POST /api/testtools/disable` |

Scaffold status: all except `health`, `session` (read) and `settings` (read) return **HTTP 501** with the target phase. No endpoint returns invented data.

## 8. Security & safety
- Loopback default; Host/Origin checks (carried over); token compare via `secrets.compare_digest`.
- Test Tools: off at start; enabling requires explicit request + (for motion) a second confirmation; every write logged; velocity = bounded magnitude, max duration, auto-zero on timeout/disconnect. UI states a software timeout is **not** an e-stop.
- Bags: restricted to configured directories, symlink escape rejected, names sanitised (ideas from reference `server.py`).
- No shell in V1. If added, separate flag, separate token scope.
- Offline playback never publishes to ROS.

## 9. Frontend
React + TypeScript + Vite; CSS variables (Graphite Dark tokens in `src/styles/tokens.css`), fonts bundled (Inter, JetBrains Mono) for offline LANs.
Planned libs (added when needed, not now): **uPlot** (high-rate numeric plots), a virtualized table, `msgpack` decoder. Layout: collapsible sidebar, top status bar (mode, connection, host label), resizable inspector panel, route-less page state.
Pages: Overview · ROS Explorer · Topic Inspector · Signals · Motion · Visualizations · Bag Studio · Diagnostics · Host Metrics · Test Tools · Settings.
(Reference "Sensors/TF/Camera" → Visualizations; "Logs" → Diagnostics; "Services/Parameters/Publish" read parts → Explorer, write parts → Test Tools.)

## 10. Implementation priorities
1. **Phase 2 core:** auth + session, agent graph snapshot, topic list/info, opt-in subscription, Hz/bandwidth/status enum, Inspector tree, basic host metrics, WS plumbing.
2. **Phase 3:** series engine + plots (uPlot), field mapping, Motion/Visualizations adapters, TF, saved layouts.
3. **Phase 4:** `BagSource` (open/metadata/messages/seek/play), offline player, recorder, bag indexer. *Early spike:* verify `rosbag2_py` read + MCAP on Humble and Jazzy before building on it.
4. **Phase 5:** diagnostics engine, QoS findings, logs, reports.
5. **Phase 6:** Test Tools, installer, dependency checks, tests, performance measurements.
Each phase ends with: what was built, what was tested, what remains, known limits.

## 11. Open questions for review
1. Recorder: `rosbag2_py.Recorder` vs `ros2 bag record` subprocess?
2. Agent→backend: is single-host (loopback) enough for V1, or should the agent be reachable over LAN?
3. Plot lib: uPlot OK?
4. Is a read-only file browser needed beyond bag selection?
5. Need the reference `replay.html` or `/wheel_rpm` message type? Only if we want parity details; not required.
6. Python floor: 3.10 (Humble) assumed.

## Phase 3 implementation update (2026-10-13)

The preceding sections include target architecture. The shipped data transport remains JSON WebSockets. Bounded camera thumbnails use base64 JPEG, not binary frames. Numeric series remain browser-side. Live events now carry source ID/mode, message type and distinct timestamps (nanoseconds encoded as strings on the wire), alongside backwards-compatible `t_ns`/`values`/`payload` fields.

Agent preview workers keep decoding away from the ROS executor; one pending task per monitored topic, two concurrent workers. Sensor renderers consume the normalized preview envelope independently of live transport. TF history is partial and sampled; `/api/live/tf` remains a future snapshot/lookup API. Read-only parameter listing uses only ListParameters/GetParameters with bounded waiting and client cleanup.

User preferences/layouts use atomic JSON replacement with size/count limits. API settings updates only change display preferences; connection configuration and robot-write permissions cannot be changed there. Test Tools remain unavailable. See PROGRESS.md for exact acceptance limits.
