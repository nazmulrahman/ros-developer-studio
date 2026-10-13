# ROS Developer Studio

Universal ROS 2 (Humble/Jazzy) monitoring and analysis tool. Read-only by default. Independent of any robot package.

**Status (phase 2):** Live analysis works against a controlled fake and has *not yet been run against real ROS 2*. Implemented: agent link, ROS Explorer, Topic Inspector (Hz/bandwidth/QoS/status), Signals plots, Host Metrics, Overview. Other pages are labelled "Not available yet". See `PROGRESS.md`, `docs/TESTING.md`, `docs/API.md`, `docs/FEATURE_MATRIX.md`.

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
`pip install pytest httpx && python -m pytest` (36 tests; fake ROS, see `docs/TESTING.md`).

## Behaviour notes
- Nothing is subscribed until you open a topic in the Inspector or add a series in Signals; it is released when you leave or close the page.
- Frequency = arrivals at the agent over a 5 s window (`--window`). Inspector subscribes BEST_EFFORT/VOLATILE, which matches any publisher QoS.
- Signals buffers (10 min, 12 000 points/series) reset when you leave the page; series definitions are remembered.
