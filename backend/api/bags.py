from fastapi import APIRouter, Depends
from ..core.auth import require_auth
from ..core.models import BagMetadata, BagOpenRequest, RecordStartRequest
from .common import not_implemented

router = APIRouter(prefix="/api", tags=["bags"], dependencies=[Depends(require_auth)])


@router.get("/bags")
def list_bags(): not_implemented(4, "bags in configured directories only")

@router.post("/bags/open", response_model=BagMetadata)
def open_bag(req: BagOpenRequest): not_implemented(4, "open via rosbag2_py (sqlite3/mcap), no ROS graph")

@router.get("/bags/{bag_id}/metadata", response_model=BagMetadata)
def bag_metadata(bag_id: str): not_implemented(4, "bag metadata")

@router.get("/bags/{bag_id}/topics")
def bag_topics(bag_id: str): not_implemented(4, "recorded topics, types, counts")

@router.get("/bags/{bag_id}/messages")
def bag_messages(bag_id: str, topic: str, start_ns: int | None = None, end_ns: int | None = None, limit: int = 100):
    not_implemented(4, "message inspection")

@router.post("/bags/{bag_id}/export")
def bag_export(bag_id: str): not_implemented(4, "export selected data")

@router.get("/bags/{bag_id}/analysis")
def bag_analysis(bag_id: str): not_implemented(4, "gaps, discontinuities, recorded intervals")

@router.get("/record/status")
def record_status(): not_implemented(4, "recording status")

@router.post("/record/start")
def record_start(req: RecordStartRequest): not_implemented(4, "start recording")

@router.post("/record/stop")
def record_stop(): not_implemented(4, "stop recording")
