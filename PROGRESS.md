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
- [ ] Phase 4 — Bag Studio (direct offline reads, recording, timeline, export).
- [ ] Phase 5 — diagnostic findings, logs and reports.
- [ ] Phase 6 — optional Test Tools, installer, Pi/Jetson performance and final release checks.

## Current limits

- No original DWM files were changed; runtime code uses discovered topics and user field mappings.
- Sensor previews are sampled (default 2 Hz, maximum 5 Hz). Camera output is at most 640×480 JPEG; raw RGB/BGR/RGBA/BGRA/mono8 and compressed JPEG/PNG are supported. Depth encodings are reported as unsupported.
- TF retains up to 2,000 observed relationships across watched TF topics; preview messages retain at most 256 transforms. It is a current observation model, not a historical TF2 lookup buffer, so rate limiting may omit short-lived transitions.
- Motion keeps 60 seconds / 1,200 samples per widget; up to 16 widgets. Units are labels, without conversion or synchronization of separate topics. Sensor page allows eight viewers.
- Renderers accept source-labelled samples but bag loading/playback is still Phase 4.
- Saved layouts store workspace configuration, not live data, credentials, window geometry or dock sizes. Server connection configuration still requires editing its configuration file and restarting.
- No Pi/Jetson performance or Jazzy compatibility claim is made.
