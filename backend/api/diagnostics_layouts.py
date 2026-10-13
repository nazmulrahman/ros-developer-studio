from fastapi import APIRouter, Depends, HTTPException, Request
from ..core.preferences import Layout
from ..core.auth import require_auth
from ..core.models import Finding
from .common import not_implemented

router = APIRouter(prefix="/api", tags=["diagnostics", "layouts"], dependencies=[Depends(require_auth)])


@router.get("/diagnostics/findings", response_model=list[Finding])
def findings(source: str = "live"): not_implemented(5, "rule-based findings with evidence")

@router.get("/layouts")
def layouts(request: Request): return request.app.state.preferences.read()["layouts"]

@router.post("/layouts")
def create_layout(layout: Layout, request: Request): return request.app.state.preferences.save_layout(layout)

@router.put("/layouts/{layout_id}")
def update_layout(layout_id: str, layout: Layout, request: Request):
    return request.app.state.preferences.save_layout(layout, layout_id)

@router.delete("/layouts/{layout_id}")
def delete_layout(layout_id: str, request: Request):
    def mutate(data):
        existing = data["layouts"]
        data["layouts"] = [x for x in existing if x["id"] != layout_id]
        if len(existing) == len(data["layouts"]): raise HTTPException(404, "Layout not found")
        return {"deleted": layout_id}
    return request.app.state.preferences.change(mutate)
