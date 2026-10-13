"""Gated developer test tools. Disabled by default; nothing here may run unless explicitly enabled."""
from fastapi import APIRouter, Depends
from ..core.auth import require_auth
from ..core.models import PublishRequest, ServiceCallRequest, TestToolsEnable, VelocityTestRequest
from ..core.state import state
from .common import not_implemented

router = APIRouter(prefix="/api/testtools", tags=["testtools"], dependencies=[Depends(require_auth)])


@router.get("/state")
def tt_state():
    return {"enabled": state.test_tools_enabled, "allowed_by_config": state.settings.test_tools_allowed}

@router.post("/enable")
def enable(req: TestToolsEnable): not_implemented(6, "explicit enable with confirmation")

@router.post("/disable")
def disable(): not_implemented(6, "disable")

@router.post("/publish")
def publish(req: PublishRequest): not_implemented(6, "single publish")

@router.post("/service")
def call_service(req: ServiceCallRequest): not_implemented(6, "single service call")

@router.post("/velocity")
def velocity(req: VelocityTestRequest): not_implemented(6, "timed velocity test with auto-zero")
