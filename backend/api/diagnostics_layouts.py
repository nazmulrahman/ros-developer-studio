from fastapi import APIRouter, Depends
from ..core.auth import require_auth
from ..core.models import Finding
from .common import not_implemented

router = APIRouter(prefix="/api", tags=["diagnostics", "layouts"], dependencies=[Depends(require_auth)])


@router.get("/diagnostics/findings", response_model=list[Finding])
def findings(source: str = "live"): not_implemented(5, "rule-based findings with evidence")

@router.get("/layouts")
def layouts(): not_implemented(3, "saved layouts")

@router.post("/layouts")
def create_layout(): not_implemented(3, "save layout")

@router.put("/layouts/{layout_id}")
def update_layout(layout_id: str): not_implemented(3, "update layout")

@router.delete("/layouts/{layout_id}")
def delete_layout(layout_id: str): not_implemented(3, "delete layout")
