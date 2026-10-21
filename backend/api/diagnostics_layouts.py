from fastapi import APIRouter, Depends, HTTPException, Request, Query
from ..core.preferences import Layout
from ..core.auth import require_auth
from ..core.models import Finding
from ..diagnostics.profiles import Expectation
from ..bags.studio import MAX_MESSAGES

router = APIRouter(prefix="/api", tags=["diagnostics", "layouts"], dependencies=[Depends(require_auth)])


@router.get("/diagnostics/findings", response_model=list[Finding])
def findings(request: Request, source: str = "live"):
    hub = request.app.state.hub; rows = []
    def add(severity, component, evidence, causes, checks):
        rows.append(dict(severity=severity, component=component, evidence=evidence, possible_causes=causes, suggested_checks=checks))
    for topic, event in hub.topic_evidence.items():
        # These topics are event-driven. A quiet interval is not evidence of a stalled publisher.
        if topic in ("/rosout", "/diagnostics"):
            continue
        status = event.get("status")
        if status in ("stalled", "publisher_no_data", "no_publisher", "qos_incompatible", "topic_missing"):
            add("error" if status == "qos_incompatible" else "warning", topic, str(event.get("evidence") or status),
                ["Publisher inactive or stalled", "Communication or QoS mismatch", "Host resource pressure"],
                ["Inspect publisher endpoints and offered QoS", "Compare ROS logs and host metrics at the same time", "Check whether the topic is expected to publish continuously"])
            rows[-1].update(timestamp_ns=event.get("t_ns"), topic=topic, source_id="live")
    for row in hub.tf_tree.snapshot()["diagnostics"]:
        add("error" if row["severity"] == "error" else "warning", "TF", row["message"],
            ["Transform broadcaster configuration or timing problem"], ["Inspect the affected frames and source topic in the unified TF viewer"])
    if not hub.agent or hub.agent.state != "connected":
        add("warning", "Agent", "Live agent is unavailable; live checks have incomplete evidence.", ["Agent stopped or connection unavailable"], ["Check the agent process and connection settings"])
    for profile in request.app.state.diagnostic_profiles.read():
        sample = hub.latest_samples.get(profile["topic"]); value = (sample.get("values") or {}).get(profile["field"]) if sample else None
        if not isinstance(value, (int, float)) or isinstance(value, bool): continue
        if profile.get("minimum") is not None and value < profile["minimum"] or profile.get("maximum") is not None and value > profile["maximum"]:
            rows.append({"severity":"warning", "component":profile["name"], "evidence":f"Observed {profile['topic']}.{profile['field']} = {value}; expected within {profile.get('minimum', '-∞')}..{profile.get('maximum', '∞')}.",
                "possible_causes":["The measured value is outside the user-defined expectation"], "suggested_checks":["Inspect neighboring samples and confirm the expectation matches this robot configuration"],
                "timestamp_ns":sample.get("stamps",{}).get("receive_ns") if sample else None,"topic":profile["topic"],"source_id":"live"})
    return rows


@router.get("/diagnostics/profiles")
def profiles(request: Request): return request.app.state.diagnostic_profiles.read()


@router.post("/diagnostics/profiles")
async def create_profile(profile: Expectation, request: Request):
    try:
        saved = request.app.state.diagnostic_profiles.save(profile)
        request.app.state.hub.expectation_topics.add(saved["topic"])
        await request.app.state.hub._ensure_diagnostic_watches()
        return saved
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.delete("/diagnostics/profiles/{profile_id}")
async def delete_profile(profile_id: str, request: Request):
    store = request.app.state.diagnostic_profiles
    profile = next((item for item in store.read() if item["id"] == profile_id), None)
    if not store.delete(profile_id): raise HTTPException(404, "Diagnostic expectation not found")
    if profile:
        topic = profile["topic"]
        still_used = any(item["topic"] == topic for item in store.read())
        if not still_used:
            request.app.state.hub.expectation_topics.discard(topic)
            request.app.state.hub.latest_samples.pop(topic, None)
            request.app.state.hub.expectation_fields.pop(topic, None)
        else:
            fields = {item["field"] for item in store.read() if item["topic"] == topic}
            request.app.state.hub.expectation_fields[topic] = fields
            await request.app.state.hub._agent_call("sub.set", {"topic":topic,"hz":10,"payload":False,"fields":sorted(fields),"visual":False}, topic)
        if not still_used and topic not in ("/rosout", "/diagnostics"):
            request.app.state.hub._diagnostic_topics.discard(topic)
            await request.app.state.hub._agent_call("sub.stop", {"topic": topic})
    return {"deleted": profile_id}


@router.get("/diagnostics/correlate")
def correlate(request: Request, timestamp_ns: int = Query(..., ge=0), window_s: float = Query(10, ge=0.1, le=300)):
    hub = request.app.state.hub; radius = int(window_s * 1e9)
    def near(row): return row.get("timestamp_ns") is not None and abs(int(row["timestamp_ns"]) - timestamp_ns) <= radius
    logs = [r for r in hub.logs if near(r)]
    diagnostics = [r for r in hub.diagnostic_events if near(r)]
    topics = [{"topic":name, **row} for name,row in hub.topic_evidence.items() if near(row)]
    host = [{"timestamp_ns": int(row["t_ns"]), "cpu": row.get("cpu"), "memory": row.get("memory"), "disk": row.get("disk")}
            for row in hub.host_samples if abs(int(row.get("t_ns", 0)) - timestamp_ns) <= radius]
    return {"timestamp_ns":timestamp_ns,"window_s":window_s,"logs":logs,"diagnostics":diagnostics,"topics":topics,"host":host}

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
