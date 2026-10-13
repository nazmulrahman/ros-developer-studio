"""ROS Developer Studio backend. Run: python -m backend.main"""
from __future__ import annotations
import argparse, logging, sys
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from .api import app_diag, bags, core_routes, diagnostics_layouts, host, live, testtools, ws
from .core.hub import LiveHub
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
                  description="Live analysis endpoints are implemented (phase 2). Endpoints returning 501 are planned for later phases.")
    app.state.hub = hub
    for r in (core_routes.router, live.router, host.router, app_diag.router, bags.router,
              diagnostics_layouts.router, testtools.router, ws.router):
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
