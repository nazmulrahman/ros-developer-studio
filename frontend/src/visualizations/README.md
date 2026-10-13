# Sensor renderers

`SensorView` consumes `NormalizedSample` from `model.ts`. It has no ROS discovery, networking or live-only hooks. Future bag playback can feed the same component. `VisualizationsPage` owns live subscriptions, freshness, pause, and saved viewer definitions.

The agent's `subscriptions/visual.py` builds bounded previews from standard ROS message types. Decode and image conversion run in two workers with at most one pending job per topic. Numeric statistics still count all received messages. Images are capped at 640×480 / 5 Hz; scans at 2,048 selected rays. Unsupported encodings and malformed images yield explicit preview errors.

The current TF component shows bounded observed relationships for one topic, with timestamps and multiple-parent hints. It does not implement TF2 lookup, cross-topic reconciliation or a complete historical tree. Odometry traces reset on frame change and keep the most recent 1,000 displayed poses.
