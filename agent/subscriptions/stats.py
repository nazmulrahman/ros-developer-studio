"""Arrival-window topic statistics. Measurement window is configurable (default 5 s) and documented in the UI."""
from __future__ import annotations
import statistics, time
from collections import deque
from threading import Lock


class TopicStats:
    """Thread-safe: record() is called from the ROS thread, snapshot() from the asyncio thread."""

    def __init__(self, window_s: float = 5.0, max_samples: int = 20000):
        self.window_s, self.max_samples = window_s, max_samples
        self._t: deque[float] = deque()
        self._s: deque[int] = deque()
        self._lock = Lock()
        self.count = 0
        self.started = time.monotonic()
        self.last_t: float | None = None
        self.last_wall_ns: int | None = None
        self.last_size: int | None = None

    def record(self, t: float, size: int | None, wall_ns: int | None = None) -> None:
        with self._lock:
            self.count += 1
            self.last_t, self.last_size = t, size
            self.last_wall_ns = wall_ns if wall_ns is not None else time.time_ns()
            self._t.append(t)
            self._s.append(size or 0)
            while len(self._t) > self.max_samples:
                self._t.popleft(); self._s.popleft()
            self._trim(t)

    def _trim(self, now: float) -> None:
        cut = now - self.window_s
        while self._t and self._t[0] < cut:
            self._t.popleft(); self._s.popleft()

    def snapshot(self, now: float | None = None) -> dict:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._trim(now)
            ts, ss = list(self._t), list(self._s)
            count, last_t, last_size, last_wall = self.count, self.last_t, self.last_size, self.last_wall_ns
        hz = period_ms = jitter_ms = bandwidth_bps = None
        if len(ts) >= 2 and ts[-1] > ts[0]:
            span = ts[-1] - ts[0]
            hz = (len(ts) - 1) / span
            period_ms = span / (len(ts) - 1) * 1000.0
            jitter_ms = statistics.pstdev([b - a for a, b in zip(ts, ts[1:])]) * 1000.0
            bandwidth_bps = (sum(ss) - ss[0]) * 8.0 / span
        elapsed = now - self.started
        return {
            "window_s": self.window_s, "samples_in_window": len(ts),
            "hz": hz, "period_ms": period_ms, "jitter_ms": jitter_ms, "bandwidth_bps": bandwidth_bps,
            "avg_hz": (count / elapsed) if elapsed > 0 and count else None,
            "count": count, "last_size_bytes": last_size, "last_recv_ns": last_wall,
            "since_last_s": (now - last_t) if last_t is not None else None,
            "monitored_for_s": elapsed,
        }


def classify(topic_exists: bool, publishers: int, snap: dict, min_stall_s: float = 2.0, stall_factor: float = 3.0) -> tuple[str, str]:
    """Return (status, evidence). A topic is never 'receiving' just because it exists."""
    if not topic_exists:
        return "topic_missing", "Topic is no longer in the ROS graph."
    if publishers == 0:
        return "no_publisher", "Topic exists but has no publishers."
    if snap["count"] == 0:
        return "publisher_no_data", f"{publishers} publisher(s) present; 0 messages received in {snap['monitored_for_s']:.1f}s."
    avg_period = snap["monitored_for_s"] / snap["count"]
    period = (snap["period_ms"] / 1000.0) if snap["period_ms"] else avg_period
    limit = max(min_stall_s, stall_factor * period)
    if snap["since_last_s"] is not None and snap["since_last_s"] > limit:
        return "stalled", f"Last message {snap['since_last_s']:.1f}s ago (expected within ~{limit:.1f}s)."
    return "receiving", "Messages arriving."
