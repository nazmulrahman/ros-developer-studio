from fastapi import APIRouter, Depends, HTTPException, Request
from ..core.preferences import Layout
from ..core.auth import require_auth
from ..core.models import Finding
from .common import not_implemented

router = APIRouter(prefix="/api", tags=["diagnostics", "layouts"], dependencies=[Depends(require_auth)])


@router.get("/diagnostics/findings", response_model=list[Finding])
def findings(request: Request, source: str = "live"):
    hub = request.app.state.hub; rows = []
    def add(severity, component, evidence, causes, checks):
        rows.append(dict(severity=severity, component=component, evidence=evidence, possible_causes=causes, suggested_checks=checks))
    for topic, event in hub.topic_evidence.items():
        status = event.get("status")
        if status in ("stalled", "publisher_no_data", "no_publisher", "qos_incompatible", "topic_missing"):
            add("error" if status == "qos_incompatible" else "warning", topic, str(event.get("evidence") or status),
                ["Publisher inactive or stalled", "Communication or QoS mismatch", "Host resource pressure"],
                ["Inspect publisher endpoints and offered QoS", "Compare ROS logs and host metrics at the same time", "Check whether the topic is expected to publish continuously"])
    for row in hub.tf_tree.snapshot()["diagnostics"]:
        add("error" if row["severity"] == "error" else "warning", "TF", row["message"],
            ["Transform broadcaster configuration or timing problem"], ["Inspect the affected frames and source topic in the unified TF viewer"])
    if not hub.agent or hub.agent.state != "connected":
        add("warning", "Agent", "Live agent is unavailable; live checks have incomplete evidence.", ["Agent stopped or connection unavailable"], ["Check the agent process and connection settings"])
    return rows

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
