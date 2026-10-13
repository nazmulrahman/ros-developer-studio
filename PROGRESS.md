# Progress checklist

- [x] Phase 1 — reference analysis, feature matrix, architecture.
- [x] Phase 2 — agent, Explorer, Inspector, Signals, Host Metrics, Overview.
- [x] Phase 2 demo-node check — user confirmed topic discovery and live messages worked (2026-10-13).
- [x] Phase 3 working increment — configurable Motion feedback/reference plots; camera, LiDAR, IMU, battery, odometry, Twist, TF frame relationships and diagnostic message viewers; read-only parameters; Settings and saved layouts.
- [x] Phase 3 automated checks — Python regression suite, frontend domain checks, TypeScript/production build.
- [x] Phase 3 Humble smoke check — real rclpy/DDS with synthetic publishers on localhost, isolated domain 187; namespaced parameters and late static TF included.
- [x] Phase 3 browser checks — Motion values, six sensor viewers, Explorer parameters, layout save/restore, browser console, responsive header.
- [ ] Phase 3 remaining acceptance — test on the user's robot and Jazzy; combined TF hierarchy/lookup and full transform diagnostics remain incomplete. Current TF view is a bounded per-topic relationship view, explicitly labelled as partial.
- [ ] Phase 4 — Bag Studio (direct offline reads, recording, timeline, export).
- [ ] Phase 5 — diagnostic findings, logs and reports.
- [ ] Phase 6 — optional Test Tools, installer, Pi/Jetson performance and final release checks.

## Current limits

- No original DWM files were changed; runtime code uses discovered topics and user field mappings.
- Sensor previews are sampled (default 2 Hz, maximum 5 Hz). Camera output is at most 640×480 JPEG; raw RGB/BGR/RGBA/BGRA/mono8 and compressed JPEG/PNG are supported. Depth encodings are reported as unsupported.
- TF retains up to 500 observed relationships per viewer; preview messages retain at most 256 transforms. Rate limiting may omit transitions. This is not a complete TF2 buffer; `/api/live/tf` remains unimplemented.
- Motion keeps 60 seconds / 1,200 samples per widget; up to 16 widgets. Units are labels, without conversion or synchronization of separate topics. Sensor page allows eight viewers.
- Renderers accept source-labelled samples but bag loading/playback is still Phase 4.
- Saved layouts store workspace configuration, not live data, credentials, window geometry or dock sizes. Server connection configuration still requires editing its configuration file and restarting.
- No Pi/Jetson performance or Jazzy compatibility claim is made.
