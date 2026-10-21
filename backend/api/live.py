from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ..core.auth import require_auth
from ..core.models import Graph, SeriesRequest, SeriesResponse, SubscribeRequest, TopicInfo, TopicStats
from ..data_sources.live import AgentError, AgentUnavailable

router = APIRouter(prefix="/api", tags=["live"], dependencies=[Depends(require_auth)])
_STATUS = {"topic_not_found": 404, "node_not_found": 404, "unsupported_type": 422, "ros_unavailable": 503, "parameter_timeout": 504}


async def agent_call(request: Request, op: str, args: dict | None = None):
    try:
        return await request.app.state.hub.call(op, args)
    except AgentUnavailable as e:
        raise HTTPException(503, {"error": "agent_unavailable", "message": str(e)})
    except AgentError as e:
        raise HTTPException(_STATUS.get(e.code, 502), {"error": e.code, "message": e.message})


@router.get("/live/status")
async def live_status(request: Request):
    """Agent connection, ROS environment (distro, domain id, discovery state) and monitored host."""
    return request.app.state.hub.status()


@router.get("/live/graph")
async def live_graph(request: Request):
    """Nodes, topics (with message types and publisher/subscriber counts), services, actions."""
    return await agent_call(request, "graph.snapshot")


@router.get("/live/topic")
async def live_topic(request: Request, name: str = Query(..., description="Topic name, e.g. /scan")):
    """Types, publisher/subscriber endpoints with QoS, QoS conflicts, numeric field schema."""
    return await agent_call(request, "topic.info", {"name": name})


@router.get("/live/topic/stats")
async def live_topic_stats(request: Request, name: str):
    """Current statistics if the topic is being monitored (opened in a viewer); otherwise {monitored:false}."""
    r = await agent_call(request, "topic.stats", {"topic": name})
    return r if r else {"monitored": False, "status": "unknown"}


@router.get("/live/node")
async def live_node(request: Request, name: str = Query(..., description="Full node name, e.g. /ns/node")):
    return await agent_call(request, "node.info", {"name": name})


@router.get("/live/subscriptions")
async def list_subscriptions(request: Request):
    return await agent_call(request, "sub.list")


@router.get("/live/services")
async def live_services(request: Request):
    return (await agent_call(request, "graph.snapshot"))["services"]


@router.get("/live/actions")
async def live_actions(request: Request):
    return (await agent_call(request, "graph.snapshot"))["actions"]


@router.get("/live/parameters")
async def node_parameters(request: Request, name: str = Query(..., pattern=r"^/[A-Za-z0-9_/]+$")):
    return await agent_call(request, "node.parameters", {"name": name})

@router.get("/live/nodes/{node:path}/parameters")
async def node_parameters_path(request: Request, node: str):
    return await agent_call(request, "node.parameters", {"name": "/" + node.lstrip("/")})

@router.get("/live/tf")
def live_tf(request: Request):
    """Merged current TF hierarchy observed from watched TFMessage topics."""
    stale_after = request.app.state.preferences.read()["preferences"]["stale_after_s"]
    return request.app.state.hub.tf_tree.snapshot(stale_after_s=stale_after)

@router.get("/live/logs")
def live_logs(request: Request, level: int | None = Query(None, ge=0, le=50), limit: int = Query(500, ge=1, le=2000),
              since_ns: int | None = None, until_ns: int | None = None, search: str | None = Query(None, max_length=200)):
    rows = list(request.app.state.hub.logs)
    if level is not None: rows = [r for r in rows if r["level"] == level]
    if since_ns is not None: rows = [r for r in rows if r["timestamp_ns"] is not None and r["timestamp_ns"] >= since_ns]
    if until_ns is not None: rows = [r for r in rows if r["timestamp_ns"] is not None and r["timestamp_ns"] <= until_ns]
    if search: rows = [r for r in rows if search.casefold() in (r["name"] + " " + r["message"]).casefold()]
    return {"rows": rows[-limit:], "capacity": 5000, "capturing": "/rosout" in request.app.state.hub._diagnostic_topics}

@router.post("/series/query", response_model=SeriesResponse)
def series_query(req: SeriesRequest): not_implemented(4, "server-side series query for bags (live plots are client-side in this phase)")

@router.post("/series/export")
def series_export(req: SeriesRequest): not_implemented(4, "server-side export for bags (live CSV export is client-side)")
