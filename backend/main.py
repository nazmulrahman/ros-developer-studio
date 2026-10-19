"""ROS Developer Studio backend. Run: python -m backend.main"""
from __future__ import annotations
import argparse, logging, sys, os
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from .api import app_diag, bags, core_routes, diagnostics_layouts, host, live, package_explorer, testtools, ws
from .core.hub import LiveHub
from .core.preferences import PreferenceStore
from .core.workspace_roots import WorkspaceRootStore
from .bags.studio import BagLibrary, Recorder
from .core import auth
from .core.state import state


def create_app() -> FastAPI:
    hub = LiveHub(state.settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.hub = hub
        await hub.start()
        yield
        await hub.stop()

    app = FastAPI(title="ROS Developer Studio", version=core_routes.VERSION, lifespan=lifespan,
                  description="Live analysis, sensor previews, parameters, layouts and offline Bag Studio are implemented (phases 2–4).")
    app.state.hub = hub
    app.state.preferences = PreferenceStore(os.environ.get("STUDIO_PREFERENCES", "config/preferences.json"))
    app.state.settings = state.settings
    app.state.workspace_roots = WorkspaceRootStore(
        os.environ.get("STUDIO_WORKSPACE_ROOTS_FILE", "config/workspace_roots.json"),
        state.settings.workspace_roots,
    )
    app.state.bags = BagLibrary(state.settings.bag_dirs)
    app.state.recorder = Recorder(state.settings.record_dir)
    for r in (core_routes.router, live.router, host.router, app_diag.router, bags.router,
              diagnostics_layouts.router, package_explorer.router, testtools.router, ws.router):
        app.include_router(r)
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
    return app


app = create_app()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default=state.settings.host)
    p.add_argument("--port", type=int, default=state.settings.port)
    p.add_argument("--token", help="Fixed token (otherwise random per start)")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.token:
        auth.set_token(a.token)
    if a.host not in ("127.0.0.1", "localhost", "::1"):
        logging.warning("Binding to %s exposes the API to the network. Token auth is required; TLS is not provided.", a.host)
    print(f"ROS Developer Studio on http://{a.host}:{a.port}/  token: {auth.TOKEN}", flush=True)
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    sys.exit(main())
