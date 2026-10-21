from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from ..core.auth import require_auth
from ..core.models import BagMetadata, BagOpenRequest, RecordStartRequest
from ..bags.studio import BagError, MAX_MESSAGES

router = APIRouter(prefix="/api", tags=["bags"], dependencies=[Depends(require_auth)])


def library(request: Request): return request.app.state.bags
def fail(exc: Exception): raise HTTPException(422, str(exc)) from exc


class ExportRequest(BaseModel):
    topic: str
    start_ns: int | None = None
    end_ns: int | None = None
    limit: int = Field(10_000, ge=1, le=10_000)


@router.get("/bags")
def list_bags(request: Request):
    try: return library(request).list()
    except BagError as exc: fail(exc)


@router.post("/bags/open", response_model=BagMetadata)
def open_bag(req: BagOpenRequest, request: Request):
    try: return library(request).summary(req.path)
    except BagError as exc: fail(exc)


@router.get("/bags/{bag_id}/metadata", response_model=BagMetadata)
def bag_metadata(bag_id: str, request: Request):
    try: return library(request).summary(library(request).get(bag_id))
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)


@router.get("/bags/{bag_id}/topics")
def bag_topics(bag_id: str, request: Request):
    try: return library(request).summary(library(request).get(bag_id))["topics"]
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)


@router.get("/bags/{bag_id}/messages")
def bag_messages(request: Request, bag_id: str, topic: str, start_ns: int | None = None, end_ns: int | None = None, limit: int = Query(100, ge=1, le=1000)):
    try: return library(request).messages(bag_id, topic, start_ns, end_ns, limit)
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)


@router.post("/bags/{bag_id}/export")
def bag_export(bag_id: str, req: ExportRequest, request: Request):
    try:
        content = library(request).export_csv(bag_id, req.topic, req.start_ns, req.end_ns, req.limit)
        return Response(content, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="bag-export.csv"'})
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)


@router.get("/bags/{bag_id}/analysis")
def bag_analysis(bag_id: str, request: Request):
    try: return library(request).analysis(bag_id)
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)


@router.get("/bags/{bag_id}/findings")
def bag_findings(bag_id: str, request: Request):
    try:
        rows = library(request).findings(bag_id)
        lib = library(request)
        for profile in request.app.state.diagnostic_profiles.read():
            try: samples = lib.messages(bag_id, profile["topic"], None, None, MAX_MESSAGES)
            except Exception: continue
            for sample in samples:
                value = sample.get("payload")
                for part in profile["field"].split("."):
                    value = value.get(part) if isinstance(value, dict) else None
                if not isinstance(value, (int, float)) or isinstance(value, bool): continue
                if profile.get("minimum") is not None and value < profile["minimum"] or profile.get("maximum") is not None and value > profile["maximum"]:
                    rows.append({"severity":"warning","component":profile["name"],"evidence":f"Recorded {profile['topic']}.{profile['field']} = {value}; expected within {profile.get('minimum', '-∞')}..{profile.get('maximum', '∞')}.",
                        "possible_causes":["The measured value is outside the user-defined expectation"],"suggested_checks":["Inspect neighboring recorded messages and confirm the expectation matches this robot configuration"],
                        "timestamp_ns":int(sample["record_ns"]),"topic":profile["topic"],"source_id":f"bag:{bag_id}"})
                    break
        return rows
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)


@router.get("/bags/{bag_id}/correlate")
def bag_correlate(bag_id: str, request: Request, timestamp_ns: int = Query(..., ge=0), window_s: float = Query(10, ge=0.1, le=300)):
    lib = library(request); radius = int(window_s * 1e9); start = max(0, timestamp_ns-radius); end = timestamp_ns+radius
    try:
        meta = lib.summary(lib.get(bag_id)); events = []
        selected = meta["topics"][:200]
        for topic in selected:
            for row in lib.messages(bag_id, topic["name"], start, end, 100):
                payload = row.get("payload")
                event = {"timestamp_ns":int(row["record_ns"]),"topic":row["topic"],"type":row["type"],"payload":payload,"decode_error":row.get("error")}
                if row["topic"] == "/rosout" and isinstance(payload, dict):
                    event["kind"] = "log"; event["level"] = payload.get("level"); event["name"] = payload.get("name"); event["message"] = payload.get("msg")
                elif row["topic"] == "/diagnostics" and isinstance(payload, dict): event["kind"] = "diagnostic"
                else: event["kind"] = "sample"
                events.append(event)
        return {"timestamp_ns":timestamp_ns,"window_s":window_s,"events":sorted(events,key=lambda x:x["timestamp_ns"]),
                "logs":[],"diagnostics":[],"topics":[],"host":[],"truncated":len(meta["topics"])>len(selected)}
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)


@router.get("/record/status")
def record_status(request: Request): return request.app.state.recorder.status()


@router.post("/record/start")
def record_start(req: RecordStartRequest, request: Request):
    try: return request.app.state.recorder.start(req.name, req.topics, req.all_topics)
    except BagError as exc: fail(exc)


@router.post("/record/stop")
def record_stop(request: Request):
    try: return request.app.state.recorder.stop()
    except BagError as exc: fail(exc)

@router.get("/bags/{bag_id}/snapshot")
def bag_snapshot(request: Request, bag_id: str, topic: str, cursor_ns: int):
    try: return library(request).snapshot(bag_id, topic, cursor_ns)
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)

@router.get("/bags/{bag_id}/topic")
def bag_topic_detail(request: Request, bag_id: str, name: str):
    try: return library(request).topic_detail(bag_id, name)
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)

@router.get("/bags/{bag_id}/tf")
def bag_tf(request: Request, bag_id: str, cursor_ns: int):
    from ..core.tf_tree import TfTree
    try:
        lib = library(request); meta = lib.summary(lib.get(bag_id)); tree = TfTree()
        for topic in meta["topics"]:
            if topic["type"] != "tf2_msgs/msg/TFMessage": continue
            sample = lib.snapshot(bag_id, topic["name"], cursor_ns)
            if sample:
                sample["stamps"]["receive_ns"] = sample["stamps"]["record_ns"]
                tree.ingest(sample)
        return tree.snapshot(now_ns=cursor_ns)
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc
    except BagError as exc: fail(exc)
