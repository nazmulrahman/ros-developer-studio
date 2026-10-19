# Test report

## Phase 2 original report
Command: `python -m pytest` — 36 tests, all passing in the build sandbox (Linux, Python 3.12).

**What the tests exercise:** the real agent server and real backend over real WebSockets, with a controlled `FakeRos` behind the same `RosBackend` interface that `RclpyBackend` implements (`tests/fakes.py`). Host metrics use real `psutil`.

**What they do NOT verify:** `RclpyBackend` itself (no ROS 2 installation was available), real DDS discovery/QoS behaviour, Jetson telemetry, and the React UI in a browser (only `tsc` + `vite build`).

| Case | Test |
|---|---|
| No agent | `test_status_when_agent_not_running` |
| Empty graph ≠ disconnected | `test_empty_graph_is_not_a_disconnected_agent` |
| Graph/topic/node details, 404 | `test_graph_topic_node_details` |
| Unsupported message type | `test_unsupported_message_type_still_inspectable` |
| QoS conflict reporting | `test_qos_conflict_reported`, `test_qos_conflicts` |
| Streaming values/payload, throttling | `test_live_stream_values_payload_and_throttle` |
| Unsubscribe on unwatch / viewer close; shared subscription | `test_unsubscribe_*`, `test_two_viewers_share_one_ros_subscription` (caught and fixed a real race) |
| No publisher / no data / receiving | `test_no_publisher_vs_no_data_vs_receiving` |
| Topic disappearing | `test_topic_disappearing` |
| High frequency (20 000 msg burst) | `test_high_frequency_topic` |
| Discovery error | `test_discovery_error_is_reported_without_dropping_agent` |
| Agent restart + watch resync | `test_agent_restart_resubscribes_and_reports_disconnect` |
| Missing GPU interface | `test_gpu_probe_failures_*`, `test_host_sample_real_measurements` |
| Auth | `test_app_diagnostics_and_auth`, `test_scaffold.py` |
| Stats math, field extraction | `tests/test_units.py` |

Not covered: browser/backend restart behaviour of the UI (reconnect logic is untested), no-ROS-nodes on a real graph, performance on Raspberry Pi/Jetson.

**Smoke run (real processes, no ROS):** agent `--no-ros` + backend: status connected / `ros.available=false` with reason, `ros_unavailable` on graph, host metrics REST + WebSocket stream OK; backend RSS ≈ 48 MiB, agent ≈ 26 MiB idle (one measurement, 1-core VM).

## Phase 3 verification — 2026-10-13

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q`: **47 passed**; regression suite includes bounded camera conversion, LiDAR invalid values/decimation, nonblocking preview processing, exact timestamps, opt-in visual fanout, late TF viewers, parameter failure mapping, authenticated layout CRUD, preference validation, and corrupt-store protection. Existing Phase 2 tests remain included.
- `cd frontend && npm test && npm run build`: domain checks for quaternion validation/conversion, buffer bounds, invalid numeric values and saved configuration validation; strict TypeScript and Vite build.
- `.venv/bin/python -m scripts.verify_phase3_ros`: **real ROS 2 Humble**, Python 3.10, CycloneDDS, loopback, isolated domain 187. Synthetic Image/LaserScan/Imu/BatteryState/Odometry/Twist/TFMessage publishers feed the real agent and backend. Verified namespaced parameter reads, separate header/receive clocks and retained static transforms published before subscription. This caught a static-TF reliability issue and the corrected run passed.
- Browser exercised against that synthetic ROS fixture: mapped feedback displayed 0.400 m/s; camera image decoded, scan rendered 360 rays, battery displayed 75%, IMU orientation/acceleration rendered, odometry trace rendered and TF frame relationship appeared. Parameter `fixture_label` was visible in Explorer. Saved a layout, removed its Motion widget, then restored the layout and saw the widget return. No browser errors/warnings during these checks. Narrow-window header overflow was corrected.

These are synthetic integration checks, not hardware acceptance. The user separately confirmed Phase 2 discovery and messages in their demo-node run. Jazzy, Pi/Jetson, sustained resource measurements, camera depth encodings and Phase 4 offline bags are **not verified**. Raw camera and JPEG/PNG error/resize handling have unit coverage; the live smoke fixture uses RGB8.

## Phase 3 completion — unified TF and Package Explorer

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q`: **55 passed**. The suite now includes merged static/dynamic TF topology, roots, disconnected groups, stale edges, invalid rotations, multiple parents, cycles, bounded retention, Package Explorer safety, folder selection and persisted workspace roots.
- `cd frontend && npm test && npm run build`: passed. TF canvas and Package Explorer remain split into on-demand production chunks.
- `.venv/bin/python -m scripts.verify_phase3_ros`: passed on real ROS 2 Humble in isolated domain 187. `/tf_static` published before subscription and live `/tf` merged into `test_world → test_base → test_camera`; the authenticated `/api/live/tf` result matched.
- Browser acceptance showed three frames, two transforms, one root/group, no findings, working frame search, and no browser warnings or errors.

This completes Phase 3 functionality. Robot/Jazzy and Pi/Jetson checks remain release acceptance because those environments were not available locally.

## Phase 4 verification — 2026-10-13

- The Python suite covers restricted-root enforcement, SQLite3 metadata, topic/message queries, bounded reads, timing-gap analysis, CSV export, authentication and recorder status.
- A bag written by the installed ROS 2 Humble `rosbag2_py.SequentialWriter` was discovered and its three CDR-encoded `std_msgs/msg/Float64` messages decoded to `1.0`, `2.5` and `7.0`. Gap detection and CSV export passed against the same bag.
- Frontend domain checks, strict TypeScript and the production build pass with the Bag Studio route and recording controls.
- This host lists SQLite3 but no MCAP storage plugin. MCAP uses `rosbag2_py` and is supported when that plugin is installed, but it was not runtime-verified here. Recording is covered at the API/status boundary; no live robot topics were recorded during automated checks.

The smoke script sets its domain/localhost/log/preferences environment before importing ROS and cleans up its publishers, agent and backend on exit. `--serve` keeps it running for browser checks until interrupted. Do not treat this synthetic fixture as robot telemetry.
