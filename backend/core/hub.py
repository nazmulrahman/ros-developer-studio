"""LiveHub: owns the agent connection, merges browser watches into one agent subscription per topic, fans out events."""
from __future__ import annotations
import asyncio, json, logging, time
from dataclasses import dataclass, field

from ..data_sources.live import AgentClient, AgentError, AgentUnavailable
from .config import Settings
from .models import Mode

log = logging.getLogger("hub")


@dataclass
class ClientWatch:
    hz: float = 10.0
    payload: bool = False
    fields: tuple[str, ...] = ()
    last_emit: float = 0.0


class Client:
    def __init__(self, ws):
        self.ws = ws
        self.q: asyncio.Queue = asyncio.Queue(maxsize=400)
        self.dropped = 0
        self.watches: dict[str, ClientWatch] = {}
        self.host_interval: float | None = None

    def push(self, ev: dict):
        if self.q.full():
            try:
                self.q.get_nowait()
                self.dropped += 1
            except asyncio.QueueEmpty:
                pass
        self.q.put_nowait(ev)


class LiveHub:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mode = Mode.live
        self.clients: set[Client] = set()
        self.agent: AgentClient | None = None
        self.desired: dict[str, dict] = {}
        self.host_desired: float | None = None
        self.dropped_total = 0

    # ---------- lifecycle
    async def start(self):
        if self.mode == Mode.live and self.agent is None:
            self.agent = AgentClient(self.settings.agent_url, self.settings.agent_token, self._on_event, self._on_state)
            await self.agent.start()

    async def stop(self):
        if self.agent:
            await self.agent.stop()
            self.agent = None

    async def set_mode(self, mode: Mode):
        self.mode = mode
        if mode == Mode.live:
            await self.start()
        else:
            await self.stop()
            self.desired.clear()
        self._broadcast(self.status_event())

    # ---------- status
    def status(self) -> dict:
        a = self.agent
        info = a.info if a and a.state == "connected" else None
        ros = None
        if info:
            r = info["ros"]
            ros = {"available": r["available"], "distro": r.get("distro"), "domain_id": r.get("domain_id"), "rmw": r.get("rmw"),
                   "error": r.get("error"), "discovery": r.get("discovery"), "discovery_error": r.get("discovery_error")}
        return {"mode": self.mode.value,
                "agent": {"state": a.state if a else "disabled", "url": a.public_url if a else None,
                          "last_error": a.last_error if a else None, "version": info.get("version") if info else None},
                "ros": ros, "host": info.get("host") if info else None}

    def status_event(self) -> dict:
        return {"ch": "status", **self.status()}

    # ---------- agent callbacks
    async def _on_state(self, state: str):
        if state == "connected":
            await self._resync()
        self._broadcast(self.status_event())
        if state == "connected":
            self._broadcast({"ch": "graph"})

    async def _resync(self):
        for topic, args in list(self.desired.items()):
            await self._agent_call("sub.set", args, topic)
        if self.host_desired:
            await self._agent_call("host.watch", {"interval_s": self.host_desired})

    async def _on_event(self, ev: dict):
        ch = ev["ch"]
        if ch == "sample":
            now = time.monotonic()
            for c in list(self.clients):
                w = c.watches.get(ev["topic"])
                if not w or not (w.payload or w.fields) or now - w.last_emit < 1.0 / max(w.hz, 0.1):
                    continue
                w.last_emit = now
                out = {"ch": "sample", "topic": ev["topic"], "t_ns": ev["t_ns"], "size": ev["size"]}
                if w.payload and "payload" in ev:
                    out["payload"] = ev["payload"]
                if w.fields and "values" in ev:
                    out["values"] = {k: ev["values"].get(k) for k in w.fields}
                c.push(out)
        elif ch == "stats":
            for c in list(self.clients):
                if ev["topic"] in c.watches:
                    c.push(ev)
        elif ch == "host":
            for c in list(self.clients):
                if c.host_interval:
                    c.push(ev)
        else:  # graph, ros_status, host_error
            if ch == "ros_status":
                if self.agent and self.agent.info:
                    self.agent.info["ros"]["discovery"] = ev.get("discovery")
                    self.agent.info["ros"]["discovery_error"] = ev.get("error")
                self._broadcast(self.status_event())
            self._broadcast(ev)

    def _broadcast(self, ev: dict):
        for c in list(self.clients):
            c.push(ev)

    # ---------- browser clients
    def add_client(self, c: Client):
        self.clients.add(c)
        c.push(self.status_event())

    async def drop_client(self, c: Client):
        self.clients.discard(c)
        self.dropped_total += c.dropped
        for topic in list(c.watches):
            c.watches.pop(topic, None)
            await self._recompute(topic)
        await self._recompute_host()

    async def watch(self, c: Client, topic: str, hz: float, payload: bool, fields: list[str]):
        c.watches[topic] = ClientWatch(hz=max(0.1, min(hz or 10.0, 100.0)), payload=payload, fields=tuple(fields))
        err = await self._recompute(topic)
        if err:
            c.push({"ch": "watch_error", "topic": topic, **err})
            c.watches.pop(topic, None)

    async def unwatch(self, c: Client, topic: str):
        if c.watches.pop(topic, None):
            await self._recompute(topic)

    async def set_host(self, c: Client, interval: float | None):
        c.host_interval = None if not interval else max(0.5, float(interval))
        await self._recompute_host()

    async def _recompute(self, topic: str) -> dict | None:
        specs = [c.watches[topic] for c in self.clients if topic in c.watches]
        if not specs:
            self.desired.pop(topic, None)
            await self._agent_call("sub.stop", {"topic": topic})
            return None
        data = [s for s in specs if s.payload or s.fields]
        args = {"topic": topic, "hz": max((s.hz for s in data), default=1.0), "payload": any(s.payload for s in specs),
                "fields": sorted({f for s in specs for f in s.fields})}
        self.desired[topic] = args
        return await self._agent_call("sub.set", args, topic)

    async def _recompute_host(self):
        ivs = [c.host_interval for c in self.clients if c.host_interval]
        self.host_desired = min(ivs) if ivs else None
        await self._agent_call("host.watch", {"interval_s": self.host_desired})

    async def _agent_call(self, op: str, args: dict, topic: str | None = None) -> dict | None:
        if not self.agent:
            return None
        try:
            await self.agent.request(op, args)
        except AgentUnavailable:
            return None  # remembered in desired; resent on reconnect
        except AgentError as e:
            if topic:
                self.desired.pop(topic, None)
            return {"code": e.code, "message": e.message}
        return None

    # ---------- REST helper
    async def call(self, op: str, args: dict | None = None):
        if not self.agent:
            raise AgentUnavailable("Live mode is not active")
        return await self.agent.request(op, args)
