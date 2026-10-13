"""Agent WebSocket server (loopback). One ROS subscription per topic, shared by all sessions (refcounted)."""
from __future__ import annotations
import asyncio, json, os, secrets, time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

import psutil
import websockets

from .host_metrics.collector import HostCollector
from .ros_graph.backend import RosBackend, RosUnavailable, TopicNotFound, UnsupportedType
from .subscriptions.monitor import Monitor, Watch
from .subscriptions.stats import classify

VERSION = "0.1.0"


class OpError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class Session:
    def __init__(self, ws):
        self.ws = ws
        self.q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.dropped = 0
        self.host_interval: float | None = None

    def push(self, ev: dict) -> None:  # called on the event loop thread
        if self.q.full():
            try:
                self.q.get_nowait()
                self.dropped += 1
            except asyncio.QueueEmpty:
                pass
        self.q.put_nowait(ev)


def _path(ws) -> str:
    p = getattr(ws, "path", None)
    return p if isinstance(p, str) else ws.request.path


class AgentServer:
    def __init__(self, ros: RosBackend, host: HostCollector, window_s: float = 5.0, graph_interval_s: float = 2.0,
                 token: str | None = None):
        self.ros, self.host, self.window_s, self.graph_interval_s, self.token = ros, host, window_s, graph_interval_s, token
        self.monitors: dict[str, Monitor] = {}
        self.sessions: set[Session] = set()
        self.discovery = {"state": "active" if ros.info()["available"] else "unavailable", "error": None}
        self._tasks: set[asyncio.Task] = set()
        self._started = time.monotonic()
        self._proc = psutil.Process()
        self._proc.cpu_percent(None)
        self._sig = None
        self._locks: dict[str, asyncio.Lock] = {}

    # ---------- lifecycle
    async def serve(self, host: str, port: int):
        self.loop = asyncio.get_running_loop()
        for coro in (self._stats_loop(), self._graph_loop(), self._host_loop()):
            t = asyncio.create_task(coro)
            self._tasks.add(t)
        return await websockets.serve(self.handler, host, port, max_size=1 << 20)

    async def aclose(self):
        for t in list(self._tasks):
            t.cancel()
        for topic in list(self.monitors):
            self._destroy(topic)

    # ---------- connection handling
    async def handler(self, ws):
        q = parse_qs(urlsplit(_path(ws)).query)
        if self.token and not secrets.compare_digest(q.get("token", [""])[0], self.token):
            await ws.close(1008, "unauthorized")
            return
        s = Session(ws)
        self.sessions.add(s)
        sender = asyncio.create_task(self._sender(s))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                t = asyncio.create_task(self._run_op(s, msg))
                self._tasks.add(t)
                t.add_done_callback(self._tasks.discard)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            sender.cancel()
            self.sessions.discard(s)
            for topic in list(self.monitors):
                self._unwatch(s, topic)

    async def _sender(self, s: Session):
        try:
            while True:
                ev = await s.q.get()
                await s.ws.send(json.dumps(ev, separators=(",", ":")))
        except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
            pass

    async def _run_op(self, s: Session, msg: dict):
        rid = msg.get("id")
        try:
            fn = getattr(self, "op_" + str(msg.get("op", "")).replace(".", "_"), None)
            if fn is None:
                raise OpError("unknown_op", f"Unknown op {msg.get('op')!r}")
            result = await fn(s, msg.get("args") or {})
            reply = {"id": rid, "ok": True, "result": result}
        except OpError as e:
            reply = {"id": rid, "ok": False, "error": {"code": e.code, "message": e.message}}
        except RosUnavailable as e:
            reply = {"id": rid, "ok": False, "error": {"code": "ros_unavailable", "message": str(e)}}
        except TopicNotFound as e:
            reply = {"id": rid, "ok": False, "error": {"code": "topic_not_found", "message": str(e)}}
        except UnsupportedType as e:
            reply = {"id": rid, "ok": False, "error": {"code": "unsupported_type", "message": str(e)}}
        except Exception as e:
            self.discovery = {"state": "error", "error": f"{type(e).__name__}: {e}"}
            reply = {"id": rid, "ok": False, "error": {"code": "internal", "message": f"{type(e).__name__}: {e}"}}
        try:
            await s.ws.send(json.dumps(reply, separators=(",", ":")))
        except websockets.exceptions.ConnectionClosed:
            pass

    # ---------- ops
    async def op_hello(self, s, a):
        return {"version": VERSION, "pid": os.getpid(), "ros": {**self.ros.info(), "discovery": self.discovery["state"],
                "discovery_error": self.discovery["error"]}, "host": self.host.info, "window_s": self.window_s,
                "graph_interval_s": self.graph_interval_s}

    def _self_topics(self) -> set[str]:
        return set(self.monitors)

    async def op_graph_snapshot(self, s, a):
        g = await asyncio.to_thread(self.ros.graph, self._self_topics())
        self.discovery = {"state": "active", "error": None}
        return g

    async def op_topic_info(self, s, a):
        name = a.get("name", "")
        info = await asyncio.to_thread(self.ros.topic_info, name)
        if info is None:
            raise OpError("topic_not_found", f"Topic {name} is not in the ROS graph")
        try:
            info["fields"] = await asyncio.to_thread(self.ros.fields_for, info["types"][0])
            info["fields_error"] = None
        except (UnsupportedType, Exception) as e:
            info["fields"], info["fields_error"] = [], str(e)
        info["monitored"] = name in self.monitors
        return info

    async def op_node_info(self, s, a):
        info = await asyncio.to_thread(self.ros.node_info, a.get("name", ""))
        if info is None:
            raise OpError("node_not_found", f"Node {a.get('name')} is not in the ROS graph")
        return info

    async def op_node_parameters(self, s, a):
        try:
            return await asyncio.to_thread(self.ros.parameters, a.get("name", ""))
        except TimeoutError as e:
            raise OpError("parameter_timeout", str(e))

    async def op_sub_set(self, s, a):
        topic = a.get("topic", "")
        hz = float(a.get("hz") or 10.0)
        w = Watch(hz=max(0.1, min(hz, 100.0)), payload=bool(a.get("payload")), fields=tuple(a.get("fields") or ()), visual=bool(a.get("visual")))
        async with self._locks.setdefault(topic, asyncio.Lock()):   # one ROS subscription per topic, even under concurrent viewers
            mon = self.monitors.get(topic)
            if mon is None:
                mon = Monitor(topic, self.window_s, self.loop)
                info = await asyncio.to_thread(self.ros.topic_info, topic)
                mon.types = list(info["types"]) if info else []
                mon.set_watch(s, w)  # register before subscribing so no early message is lost
                mon.handle = await asyncio.to_thread(self.ros.subscribe, topic, mon.on_message)
                mon.types = list(getattr(mon.handle, "types_", []))
                self.monitors[topic] = mon
            else:
                mon.set_watch(s, w)
        return {"topic": topic, "types": mon.types}

    def _unwatch(self, s, topic: str):
        mon = self.monitors.get(topic)
        if mon and mon.remove(s):
            self._destroy(topic)

    def _destroy(self, topic: str):
        mon = self.monitors.pop(topic, None)
        if mon and mon.handle:
            try:
                mon.handle.close()
            except Exception:
                pass

    async def op_sub_stop(self, s, a):
        self._unwatch(s, a.get("topic", ""))
        return {}

    async def op_sub_list(self, s, a):
        return [{"topic": t, "watchers": len(m.keys()), "count": m.stats.count} for t, m in self.monitors.items()]

    def _stats_event(self, mon: Monitor) -> dict:
        exists, pubs, subs = self.ros.topic_presence(mon.topic, True)
        snap = mon.stats.snapshot()
        status, evidence = classify(exists, pubs, snap)
        return {"ch": "stats", "topic": mon.topic, "stats": snap, "status": status, "evidence": evidence,
                "publishers": pubs, "subscribers": subs, "error": mon.error, "types": mon.types}

    async def op_topic_stats(self, s, a):
        mon = self.monitors.get(a.get("topic", ""))
        return None if mon is None else await asyncio.to_thread(self._stats_event, mon)

    async def op_host_watch(self, s, a):
        iv = a.get("interval_s")
        s.host_interval = None if iv is None else max(0.5, float(iv))
        return {}

    async def op_host_sample(self, s, a):
        return await asyncio.to_thread(self.host.sample)

    async def op_diag(self, s, a):
        mi = self._proc.memory_info()
        return {"pid": os.getpid(), "rss_bytes": mi.rss, "cpu_percent": self._proc.cpu_percent(None),
                "threads": self._proc.num_threads(), "uptime_s": time.monotonic() - self._started,
                "monitored_topics": len(self.monitors), "sessions": len(self.sessions),
                "dropped_events": sum(x.dropped for x in self.sessions),
                "decode_errors": sum(m.decode_errors for m in self.monitors.values())}

    # ---------- background loops
    def _broadcast(self, ev: dict, only=None):
        for s in list(only if only is not None else self.sessions):
            s.push(ev)

    async def _stats_loop(self):
        while True:
            await asyncio.sleep(1.0)
            mons = list(self.monitors.values())
            if not mons:
                continue
            try:
                events = await asyncio.to_thread(lambda: [self._stats_event(m) for m in mons])
            except Exception as e:
                self.discovery = {"state": "error", "error": f"{type(e).__name__}: {e}"}
                continue
            for mon, ev in zip(mons, events):
                self._broadcast(ev, mon.keys())

    async def _graph_loop(self):
        while True:
            await asyncio.sleep(self.graph_interval_s)
            if not self.ros.info()["available"]:
                continue
            try:
                sig = await asyncio.to_thread(self.ros.signature)
                if self.discovery["state"] != "active":
                    self.discovery = {"state": "active", "error": None}
                    self._broadcast({"ch": "ros_status", "discovery": "active", "error": None})
                if sig != self._sig:
                    self._sig = sig
                    self._broadcast({"ch": "graph"})
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                if self.discovery["error"] != err:
                    self.discovery = {"state": "error", "error": err}
                    self._broadcast({"ch": "ros_status", "discovery": "error", "error": err})

    async def _host_loop(self):
        while True:
            ivs = [s.host_interval for s in self.sessions if s.host_interval]
            if not ivs:
                await asyncio.sleep(0.5)
                continue
            try:
                snap = await asyncio.to_thread(self.host.sample)
                snap["ch"] = "host"
                self._broadcast(snap, [s for s in self.sessions if s.host_interval])
            except Exception as e:
                self._broadcast({"ch": "host_error", "error": f"{type(e).__name__}: {e}"})
            await asyncio.sleep(min(ivs))
