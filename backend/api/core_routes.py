from fastapi import APIRouter, Depends, Request
from ..core.auth import require_auth
from ..core.models import Mode, ModeRequest, SessionInfo
from ..core.state import state
from .common import not_implemented

VERSION = "0.0.1"
router = APIRouter(prefix="/api", tags=["core"])


@router.get("/health")
def health():
    """Unauthenticated liveness probe. Reveals nothing about the robot."""
    return {"status": "ok", "version": VERSION}


@router.get("/session", response_model=SessionInfo, dependencies=[Depends(require_auth)])
def session(request: Request):
    hub = request.app.state.hub
    agent_ok = bool(hub.agent and hub.agent.state == "connected")
    ros = (hub.status().get("ros") or {}).get("available", False)
    return SessionInfo(
        mode=hub.mode, version=VERSION, agent_connected=agent_ok,
        capabilities={"live": agent_ok and bool(ros), "host_metrics": agent_ok, "offline_bags": False, "recording": False, "test_tools": False},
        test_tools_enabled=state.test_tools_enabled)


@router.post("/session/mode", response_model=SessionInfo, dependencies=[Depends(require_auth)])
async def set_mode(req: ModeRequest, request: Request):
    """Switching to offline stops the live source; live starts it (offline bag source arrives in phase 4)."""
    await request.app.state.hub.set_mode(req.mode)
    return session(request)


@router.get("/settings", dependencies=[Depends(require_auth)])
def get_settings():
    s = state.settings
    return {"host": s.host, "port": s.port, "agent_url": s.agent_url, "bag_dirs": s.bag_dirs,
            "stats_window_s": s.stats_window_s, "test_tools_allowed": s.test_tools_allowed}


@router.put("/settings", dependencies=[Depends(require_auth)])
def put_settings():
    not_implemented(3, "persisted settings")
