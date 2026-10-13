"""Per-topic monitor shared by all sessions. on_message runs on the ROS thread and must stay cheap."""
from __future__ import annotations
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from .fields import describe, get_path
from .stats import TopicStats


@dataclass
class Watch:
    hz: float = 10.0
    payload: bool = False
    fields: tuple[str, ...] = ()
    last_emit: float = 0.0

    @property
    def wants_data(self) -> bool:
        return self.payload or bool(self.fields)


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

    def set_watch(self, key: Any, watch: Watch) -> None:
        with self._lock:
            old = self.watchers.get(key)
            if old:
                watch.last_emit = old.last_emit
            self.watchers[key] = watch

    def remove(self, key: Any) -> bool:
        with self._lock:
            self.watchers.pop(key, None)
            return not self.watchers

    def keys(self) -> list[Any]:
        with self._lock:
            return list(self.watchers)

    def on_message(self, t: float, size: int | None, get_msg) -> None:
        self.stats.record(t, size)
        with self._lock:
            due = [(k, w) for k, w in self.watchers.items() if w.wants_data and t - w.last_emit >= 1.0 / max(w.hz, 0.1)]
        if not due:
            return
        try:
            msg = get_msg()
        except Exception as e:  # deserialization problem: report, keep stats running
            self.decode_errors += 1
            self.error = f"{type(e).__name__}: {e}"
            return
        wall = time.time_ns()
        for key, w in due:
            w.last_emit = t
            ev: dict = {"ch": "sample", "topic": self.topic, "t_ns": wall, "size": size}
            if w.fields:
                ev["values"] = {p: get_path(msg, p) for p in w.fields}
            if w.payload:
                ev["payload"] = describe(msg)
            try:
                self.loop.call_soon_threadsafe(key.push, ev)
            except RuntimeError:  # event loop closed during shutdown
                return
