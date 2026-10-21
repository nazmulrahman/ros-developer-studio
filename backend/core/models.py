"""Shared data contracts. See docs/ARCHITECTURE.md §4-5. Used by live and bag sources alike."""
from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class Mode(str, Enum):
    live = "live"
    offline = "offline"


class Stamps(BaseModel):
    """Three distinct clocks; never merged."""
    header_ns: int | None = None
    receive_ns: int | None = None
    record_ns: int | None = None


class Sample(BaseModel):
    source_mode: Literal["live", "bag"]
    source_id: str
    topic: str
    type: str
    stamps: Stamps = Stamps()
    payload: dict[str, Any] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class TopicStatus(str, Enum):
    no_publisher = "no_publisher"
    publisher_no_data = "publisher_no_data"
    qos_incompatible = "qos_incompatible"
    receiving = "receiving"
    stalled = "stalled"
    topic_missing = "topic_missing"
    unknown = "unknown"


class QoS(BaseModel):
    reliability: str | None = None
    durability: str | None = None
    history: str | None = None
    depth: int | None = None


class Endpoint(BaseModel):
    node: str
    namespace: str = "/"
    qos: QoS | None = None


class TopicInfo(BaseModel):
    name: str
    types: list[str]
    publishers: list[Endpoint] = []
    subscribers: list[Endpoint] = []
    status: TopicStatus = TopicStatus.unknown


class TopicStats(BaseModel):
    name: str
    window_s: float
    hz: float | None = None
    period_ms: float | None = None
    bandwidth_bps: float | None = None
    message_size_bytes: int | None = None
    count_total: int = 0
    dropped: int = 0
    status: TopicStatus = TopicStatus.unknown


class Graph(BaseModel):
    nodes: list[str] = []
    topics: list[TopicInfo] = []
    services: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []


class SubscribeRequest(BaseModel):
    topic: str
    max_rate_hz: float | None = Field(None, gt=0, description="Server-side throttle")
    fields: list[str] | None = Field(None, description="Dotted field paths to keep; None = full message")
    acknowledge_high_bandwidth: bool = False


class SeriesRequest(BaseModel):
    source_id: str
    series: list[dict[str, str]] = Field(description="[{topic, field, label?}]")
    start_ns: int | None = None
    end_ns: int | None = None
    max_points: int = Field(5000, ge=10, le=100000)


class SeriesResponse(BaseModel):
    t_ns: list[int]
    series: dict[str, list[float | None]]


class BagOpenRequest(BaseModel):
    path: str


class BagMetadata(BaseModel):
    bag_id: str
    path: str
    storage: str | None = None
    duration_ns: int | None = None
    start_ns: int | None = None
    end_ns: int | None = None
    message_count: int | None = None
    topics: list[dict[str, Any]] = []
    warnings: list[str] = []


class RecordStartRequest(BaseModel):
    name: str | None = None
    topics: list[str] = []
    all_topics: bool = False


class Finding(BaseModel):
    severity: Literal["info", "warning", "error"]
    component: str
    evidence: str
    possible_causes: list[str] = []
    suggested_checks: list[str] = []
    timestamp_ns: int | None = None
    topic: str | None = None
    source_id: str | None = None


class SessionInfo(BaseModel):
    mode: Mode
    version: str
    agent_connected: bool
    capabilities: dict[str, bool]
    test_tools_enabled: bool = False


class ModeRequest(BaseModel):
    mode: Mode


class PlayerCommand(BaseModel):
    op: Literal["play", "pause", "seek", "rate", "step"]
    value: float | None = None


class TestToolsEnable(BaseModel):
    confirm_text: str
    allow_motion: bool = False


class PublishRequest(BaseModel):
    topic: str
    type: str
    message: dict[str, Any]


class ServiceCallRequest(BaseModel):
    service: str
    type: str
    request: dict[str, Any] = {}


class VelocityTestRequest(BaseModel):
    topic: str
    type: str = "geometry_msgs/msg/Twist"
    message: dict[str, Any]
    duration_s: float = Field(gt=0, le=2.0)
