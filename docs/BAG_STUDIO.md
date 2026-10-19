# Bag Studio

Bag Studio reads ROS 2 recordings directly. It does not run `ros2 bag play` and does not publish recorded data into the active ROS graph.

## Configuration

```toml
[bags]
directories = ["~/ros_bags", "/media/data/team_bags"]
record_dir = "~/ros_bags"
```

Only bags below `directories` can be listed or opened. Paths are expanded and resolved before checking the allowed roots, which also prevents a symlink from escaping a root. `record_dir` is the destination for new recordings. Restart the backend after editing the file. For temporary deployments, `STUDIO_BAG_DIRS` accepts paths separated by the operating system path separator and `STUDIO_RECORD_DIR` overrides the recording destination.

## Reading and playback

SQLite3 bags are queried read-only. Split `.db3` files are combined. MCAP bags use `rosbag2_py` and require the distribution's MCAP storage plugin. `metadata.yaml` supplies MCAP topics and bounds; message packages must be installed and the relevant ROS/workspace environment sourced to decode payloads. If a type cannot be loaded, the timestamp and byte size remain visible with a decode error.

The timeline requests bounded message windows from disk. Play advances the cursor at 0.25×–4×, pause freezes it, step advances one percent of the recording, and dragging seeks. These controls affect Studio only.

Timing analysis reports the median period, maximum gap, gaps larger than five normal periods with a one-second floor, timestamp reversals and whether the two-million-message analysis cap was reached. CSV export is capped at 10,000 messages per request.

## Recording

Recording starts `ros2 bag record` without a shell. Names are sanitized, topic names are validated, output is confined to `record_dir`, and only one recording can run at a time. Stop sends SIGINT so rosbag can finalize its metadata and storage. The backend must run in a sourced ROS 2 environment and have write access to `record_dir`.
