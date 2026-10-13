"""Shared topic monitor. Decode off the ROS executor, with at most one pending job per topic."""
from __future__ import annotations
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Any
from .fields import describe, get_path
from .stats import TopicStats
from .visual import preview, stamp

_WORKERS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sensor-preview")
_SOURCE = "live:" + socket.gethostname()

@dataclass
class Watch:
    hz: float = 10.0
    payload: bool = False
    fields: tuple[str, ...] = ()
    visual: bool = False
    last_emit: float = 0.0
    last_visual_emit: float = 0.0

    @property
    def wants_data(self) -> bool:
        return self.payload or bool(self.fields) or self.visual

class Monitor:
    def __init__(self, topic: str, window_s: float, loop):
        self.topic, self.loop = topic, loop
        self.stats = TopicStats(window_s)
        self.watchers: dict[Any, Watch] = {}
        self.handle = None
        self.types: list[str] = []
        self.error: str | None = None
        self.decode_errors = 0
        self._lock = Lock()
        self._pending = False

    def set_watch(self, key: Any, watch: Watch) -> None:
        with self._lock:
            old = self.watchers.get(key)
            if old:
                watch.last_emit = old.last_emit
                watch.last_visual_emit = old.last_visual_emit
            self.watchers[key] = watch

    def remove(self, key: Any) -> bool:
        with self._lock:
            self.watchers.pop(key, None)
            return not self.watchers

    def keys(self) -> list[Any]:
        with self._lock: return list(self.watchers)

    def on_message(self, t: float, size: int | None, get_msg) -> None:
        self.stats.record(t, size)
        wall = time.time_ns()
        with self._lock:
            if self._pending: return
            due = [(k, w) for k, w in self.watchers.items() if w.wants_data and
                   t - w.last_emit >= 1.0 / max(0.1, min(w.hz, 5.0) if w.visual and not (w.fields or w.payload) else w.hz)]
            if not due: return
            self._pending = True
            for _, w in due: w.last_emit = t
            visual_due = {id(w) for _, w in due if w.visual and t - w.last_visual_emit >= 0.2}
            for _, w in due:
                if id(w) in visual_due: w.last_visual_emit = t
        _WORKERS.submit(self._decode, due, visual_due, wall, size, get_msg)

    def _decode(self, due, visual_due, wall, size, get_msg):
        try:
            msg = get_msg()
            type_name = self.types[0] if self.types else ""
            visual = preview(msg, type_name) if visual_due else None
            payload = describe(msg) if any(w.payload for _, w in due) else None
            for key, w in due:
                ev = {"ch": "sample", "topic": self.topic, "t_ns": wall, "size": size,
                      "source_mode": "live", "source_id": _SOURCE, "type": type_name,
                      "stamps": {"receive_ns": str(wall), "header_ns": str(stamp(msg)) if stamp(msg) is not None else None,
                                 "record_ns": None}}
                if w.fields: ev["values"] = {p: get_path(msg, p) for p in w.fields}
                if w.payload: ev["payload"] = payload
                if id(w) in visual_due: ev["visual"] = visual
                self.loop.call_soon_threadsafe(self._deliver, key, w, ev)
            self.error = None
        except Exception as e:
            self.decode_errors += 1
            self.error = f"{type(e).__name__}: {e}"
        finally:
            with self._lock: self._pending = False

    def _deliver(self, key, watch, ev):
        with self._lock:
            current = self.watchers.get(key)
        if current is watch: key.push(ev)
