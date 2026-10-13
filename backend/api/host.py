from fastapi import APIRouter, Depends, Request
from ..core.auth import require_auth
from .common import not_implemented
from .live import agent_call

router = APIRouter(prefix="/api/host", tags=["host"], dependencies=[Depends(require_auth)])


@router.get("/metrics")
async def metrics(request: Request):
    """One sample of the machine running the agent (not the browser's machine). Unsupported metrics are null."""
    return await agent_call(request, "host.sample")


@router.get("/processes")
def processes(): not_implemented(5, "process CPU/memory table")
