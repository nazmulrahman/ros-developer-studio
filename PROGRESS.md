# Progress checklist

- [x] Phase 1 — reference analysis, feature matrix, architecture.
- [x] Phase 2 — agent, Explorer, Inspector, Signals, Host Metrics, Overview.
- [x] Phase 2 demo-node check — user confirmed topic discovery and live messages worked (2026-10-13).
- [x] Phase 3 — configurable Motion feedback/reference plots; camera, LiDAR, IMU, battery, odometry, Twist, merged TF hierarchy and diagnostic message viewers; read-only parameters; Settings, saved layouts and ROS 2 Package Explorer.
- [x] Phase 3 automated checks — Python regression suite, frontend domain checks, TypeScript/production build.
- [x] Phase 3 Humble smoke check — real rclpy/DDS with synthetic publishers on localhost, isolated domain 187; namespaced parameters and late static TF included.
- [x] Phase 3 browser checks — Motion values, six sensor viewers, Explorer parameters, layout save/restore, browser console, responsive header.
- [x] Phase 3 TF completion — `/tf` and `/tf_static` merge into one bounded hierarchy with roots, disconnected groups, stale transforms, multiple-parent, cycle, self-parent and quaternion diagnostics; search, graph navigation and transform inspection are included.
- [ ] Hardware/release acceptance — test the completed Phase 3 feature set on the user's robot, Jazzy, Raspberry Pi and Jetson before making compatibility or performance claims.
- [x] Phase 4 — Bag Studio: restricted bag library, SQLite3 and optional MCAP reads, decoded messages, timeline seek/play/rate/step, numeric plotting, CSV export, recording and timing-gap analysis.
- [x] Phase 4 Humble smoke check — a native `rosbag2_py` SQLite3 fixture was discovered, decoded, analysed and exported. MCAP remains dependent on an installed ROS storage plugin and was unavailable on this host.
- [x] Phase 5 implementation — bounded live ROS log/diagnostic capture, evidence-backed live and bag findings, persistent numeric expectation profiles, ±time-window correlation, incident navigation and JSON reports.
- [ ] Phase 5 verification — regression tests and browser acceptance for capture, profiles, correlation and incident navigation.
- [ ] Phase 6 — optional Test Tools, installer, Pi/Jetson performance and final release checks.

## Current limits

- No original DWM files were changed; runtime code uses discovered topics and user field mappings.
- Sensor previews are sampled (default 2 Hz, maximum 5 Hz). Camera output is at most 640×480 JPEG; raw RGB/BGR/RGBA/BGRA/mono8 and compressed JPEG/PNG are supported. Depth encodings are reported as unsupported.
- TF retains up to 2,000 observed relationships across watched TF topics; preview messages retain at most 256 transforms. It is a current observation model, not a historical TF2 lookup buffer, so rate limiting may omit short-lived transitions.
- Motion keeps 60 seconds / 1,200 samples per widget; up to 16 widgets. Units are labels, without conversion or synchronization of separate topics. Sensor page allows eight viewers.
- Bag playback is local to Bag Studio and never republishes into the ROS graph. It reads bounded message windows as the timeline advances.
- Saved layouts store workspace configuration, not live data, credentials, window geometry or dock sizes. Server connection configuration still requires editing its configuration file and restarting.
- No Pi/Jetson performance or Jazzy compatibility claim is made.

## 2026-10-21 Phase 5 implementation

- Live mode now samples `/rosout` and `/diagnostics` when those topics are present and keeps bounded in-memory buffers (5,000 log entries; 2,000 diagnostic status entries). Buffers reset with the backend process; they are not an archival log store.
- Added saved numeric min/max expectation profiles for live latest-sample checks and bounded recorded-bag scans.
- Findings carry source/topic/timestamp metadata where available. Correlation collects nearby live logs, diagnostic statuses, topic status and host samples, or nearby bag messages across up to 200 topics. The UI can seek a bag to a finding and open its topic in Inspector.
- JSON export includes findings and expectation profiles. Runtime and browser verification remain pending; no Phase 5 checks have been run in this session.

## 2026-10-14 bounded implementation session

- Shared offline selection and persistent timeline now feed recorded snapshots to Inspector, Signals, Motion and sensor previews. Numeric schemas come from the bag's message types; latest-at-cursor queries support backward seek.
- Real Humble SQLite LaserScan smoke check passes: previews, recording/header clock distinction, numeric schema and backward seek. UI browser acceptance is still pending.
- Diagnostics page runs bag findings or observed live topic/TF checks and exports JSON evidence reports.
- Added read-only dependency check and repeatable recorded-scan verification scripts.
- Phase 6 remains partial: installer, gated Test Tools, sustained Pi/Jetson performance and Jazzy/MCAP acceptance are still needed.
- Offline playback currently samples latest-at-cursor messages; it is not lossless streaming of every recorded message. Unified offline TF currently uses the latest message from each recorded TF topic and may omit edges emitted only in earlier messages.
