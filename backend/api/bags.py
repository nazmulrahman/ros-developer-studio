from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from ..core.auth import require_auth
from ..core.models import BagMetadata, BagOpenRequest, RecordStartRequest
from ..bags.studio import BagError

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
    try: return library(request).findings(bag_id)
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
