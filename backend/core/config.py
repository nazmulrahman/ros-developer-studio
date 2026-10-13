"""Configuration: defaults < config/studio.toml. Read-only safe defaults."""
from __future__ import annotations
import os

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8800
    agent_url: str = "ws://127.0.0.1:8770"
    agent_token: str | None = None
    bag_dirs: list[str] = field(default_factory=lambda: ["~/ros_bags"])
    record_dir: str = "~/ros_bags"
    topic_buffer_messages: int = 2000
    topic_buffer_bytes: int = 32 * 1024 * 1024
    stats_window_s: float = 5.0
    test_tools_allowed: bool = False


def load_settings(path: str | None = None) -> Settings:
    s = Settings()
    p = Path(path or os.environ.get("STUDIO_CONFIG", "config/studio.toml"))
    if p.is_file():
        with p.open("rb") as f:
            raw = tomllib.load(f)
        srv, ag, bg, lim, tt = (raw.get(k, {}) for k in ("server", "agent", "bags", "limits", "test_tools"))
        s.host, s.port = srv.get("host", s.host), srv.get("port", s.port)
        s.agent_url = ag.get("url", s.agent_url)
        s.agent_token = ag.get("token", s.agent_token)
        s.bag_dirs = bg.get("directories", s.bag_dirs)
        s.record_dir = bg.get("record_dir", s.record_dir)
        s.topic_buffer_messages = lim.get("topic_buffer_messages", s.topic_buffer_messages)
        s.topic_buffer_bytes = lim.get("topic_buffer_bytes", s.topic_buffer_bytes)
        s.stats_window_s = lim.get("stats_window_s", s.stats_window_s)
        s.test_tools_allowed = bool(tt.get("enabled", False))
    return s
