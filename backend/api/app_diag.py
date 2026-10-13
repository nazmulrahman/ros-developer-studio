import os, time
import psutil
from fastapi import APIRouter, Depends, Request
from ..core.auth import require_auth
from ..data_sources.live import AgentError, AgentUnavailable

router = APIRouter(prefix="/api", tags=["diagnostics"], dependencies=[Depends(require_auth)])
_proc = psutil.Process()
_proc.cpu_percent(None)
_started = time.monotonic()


@router.get("/app/diagnostics")
async def app_diagnostics(request: Request):
    """Resource use of this application itself (backend and agent) so overhead stays measurable."""
    hub = request.app.state.hub
    agent = None
    try:
        agent = await hub.call("diag")
    except (AgentUnavailable, AgentError):
        pass
    return {"backend": {"pid": os.getpid(), "rss_bytes": _proc.memory_info().rss, "cpu_percent": _proc.cpu_percent(None),
                        "uptime_s": time.monotonic() - _started, "browser_clients": len(hub.clients),
                        "dropped_events": hub.dropped_total + sum(c.dropped for c in hub.clients)},
            "agent": agent}
