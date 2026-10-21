"""Browser WebSocket. Client -> {op: watch|unwatch|host|ping}. Server -> {ch: status|sample|stats|host|graph|ros_status|watch_error}."""
import asyncio, json
from urllib.parse import urlsplit
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..core.auth import ws_authorized
from ..core.hub import Client

router = APIRouter()


def _origin_ok(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    return origin is None or urlsplit(origin).netloc == ws.headers.get("host")


@router.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    if not ws_authorized(ws) or not _origin_ok(ws):
        await ws.close(code=1008, reason="Unauthorized")
        return
    hub = ws.app.state.hub
    client = Client(ws)
    hub.add_client(client)

    async def sender():
        while True:
            ev = await client.q.get()
            await ws.send_text(json.dumps(ev, separators=(",", ":")))

    task = asyncio.create_task(sender())
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            op = msg.get("op")
            if op == "watch":
                await hub.watch(client, str(msg["topic"]), float(msg.get("hz") or 10), bool(msg.get("payload")),
                                [str(f) for f in msg.get("fields") or []], bool(msg.get("visual")))
            elif op == "unwatch":
                await hub.unwatch(client, str(msg["topic"]))
            elif op == "host":
                await hub.set_host(client, msg.get("interval_s"))
    except (WebSocketDisconnect, ValueError, KeyError):
        pass
    finally:
        task.cancel()
        await hub.drop_client(client)
