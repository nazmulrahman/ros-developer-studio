# ROS Developer Studio

Universal ROS 2 (Humble/Jazzy) monitoring and analysis tool. Read-only by default. Independent of any robot package.

**Status:** Phase 2's demo-node run is confirmed by the user. Phase 3 functionality is complete: Motion field mappings, sensor previews, unified TF hierarchy and diagnostics, read-only parameters, Settings, saved layouts, and ROS 2 Package Explorer. Humble synthetic ROS and browser acceptance pass; robot/Jazzy and Pi/Jetson release acceptance remain. Phases 4–6 remain unfinished. See `PROGRESS.md`, `docs/TESTING.md`, and `docs/PACKAGE_EXPLORER.md`.

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

Camera processing requires Pillow (included in requirements). Without it, other viewers still work and the camera reports its missing dependency. TF currently shows sampled per-topic relationships, not a complete transform graph. Sensor rendering is reusable for bags, but offline playback is not yet implemented.
