# ROS Developer Studio

Universal ROS 2 (Humble/Jazzy) monitoring and analysis tool. Read-only by default. Independent of any robot package.

**Status:** Phases 1–4 are implemented; Phase 5 diagnostics now includes bounded ROS log capture, evidence findings, saved numeric expectations, incident-window correlation and report export. Phase 5 runtime/browser verification and Phase 6/release work remain. Bag Studio supports configured SQLite3/MCAP recordings, sampled playback, decoded messages, plots, CSV, timing analysis and recording. Humble SQLite3 verification passes; MCAP requires its ROS storage plugin. See `PROGRESS.md`, `docs/TESTING.md`, and `docs/BAG_STUDIO.md`.

The product is organized around an investigation loop—observe, detect, correlate, explain and verify—rather than passive dashboards. See `docs/DIAGNOSTIC_STRATEGY.md` for the finding contract and shared live/offline direction.

## Install
Needs Python ≥ 3.10 and Node ≥ 18. **Use a virtual environment** (Ubuntu 22.04 ships pydantic 1.x, which is too old):
```bash
python3 -m venv --system-site-packages .venv      # keeps ROS 2's rclpy importable
source .venv/bin/activate
pip install -r requirements.txt
(cd frontend && npm install && npm run build)
```
Windows PowerShell: `py -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt; cd frontend; npm install; npm run build; cd ..` (Windows has no ROS here, so use `--no-ros`).

## Run (two processes on the robot host)
```bash
scripts/run_agent.sh            # sources ROS (and $WORKSPACE for custom messages), starts the agent on 127.0.0.1:8770
python3 -m backend.main         # prints the URL and a one-time token
```
Open the printed URL, paste the token in the top bar. No ROS yet? `python -m agent.main --no-ros` shows Host Metrics and a clear "ROS environment unavailable" state.
For development UI: `cd frontend && npm run dev` → http://127.0.0.1:5173.
Reaching it from another PC: `python3 -m backend.main --host 0.0.0.0` (token auth only, no TLS — use a trusted LAN or SSH tunnel). The agent port stays on loopback.

## Test
`pip install 'pytest>=8' httpx && python -m pytest` (unit and fake-ROS integration suite).
`cd frontend && npm test && npm run build` (domain checks, type check and production build).
For isolated real-Humble verification, source ROS and run `.venv/bin/python -m scripts.verify_phase3_ros`. This explicitly publishes synthetic fixtures on localhost in domain 187; it never uses the robot's ROS domain. See `docs/TESTING.md`.

## Behaviour notes
- Nothing is subscribed until you open a topic in the Inspector, add a Signals series, or configure a Motion/sensor viewer; it is released when you leave or close the page.
- Frequency = arrivals at the agent over a 5 s window (`--window`). Ordinary topic inspection uses BEST_EFFORT/VOLATILE. TF uses retained delivery when all discovered publishers offer TRANSIENT_LOCAL, and RELIABLE when all offer it.
- Signals buffers (10 min, 12 000 points/series) reset when you leave the page; series definitions are remembered.

## Phase 3 workflow
- **Motion:** add a label and unit, select a discovered topic and numeric field, and optionally map a command/reference field. Add separate widgets for any number of motors up to the 16-widget display limit. This only reads feedback.
- **Visualizations:** select supported sensor topics and add viewers. Camera previews are resized and rate limited on the agent. Missing/unsupported data shows an explanation; zero is never substituted for missing data.
- **Explorer → Nodes:** select a node to read its parameters in Details. Unavailable parameter services time out with a visible error.
- **Settings:** adjust preview/Motion rates and stale-data threshold; save or restore workspace layouts. Defaults reopen with the workspaces. Backend JSON persistence uses `config/preferences.json` (override with `STUDIO_PREFERENCES`). No credentials are stored in layouts.
- **Package Explorer:** use **Add workspace** to browse and approve a folder on the backend computer, or preconfigure roots with `[workspaces].roots`; then inspect packages, files, dependency evidence, launch declarations, or the connected live graph. See `docs/PACKAGE_EXPLORER.md` for modes, safety rules, and limits.

## Bag Studio workflow
- Configure one or more allowed library roots in `[bags].directories` and the recording destination in `[bags].record_dir`. Both may point outside the Studio project. Restart the backend after changing them.
- Open **Bag Studio**, choose a discovered bag, select a topic and use the timeline, playback speed or step controls. Load a window to inspect decoded values, select a numeric field to plot it, or export the topic as CSV.
- Use the recording bar to record selected topic names or all topics. Recording invokes `ros2 bag record`, so start Studio in a sourced ROS environment. Stop recording from the same bar to finalize the bag.
- Bag files stay inside the configured roots. Symlinks cannot escape them. Playback reads files directly and does not publish recorded messages.

Camera processing requires Pillow (included in requirements). Without it, other viewers still work and the camera reports its missing dependency. TF shows a bounded observed hierarchy rather than a historical TF2 lookup buffer. MCAP reading requires the ROS 2 MCAP storage plugin for the installed distribution; bags whose message packages are unavailable remain inspectable at metadata/raw-message level.

## Installation and recorded-data checks

After sourcing ROS and activating the virtual environment:
```bash
python -m scripts.check_dependencies
python -m scripts.verify_bag_snapshot
```
Open a bag in Bag Studio, then switch to Visualizations and add its `/scan` viewer. The persistent recording toolbar controls the shared cursor. Diagnostics runs evidence checks and exports a JSON report. Recorded samples use recording time and retain header time separately; no receive timestamp is invented.
