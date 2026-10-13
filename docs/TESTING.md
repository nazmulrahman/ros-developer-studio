# Test report (phase 2)
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
