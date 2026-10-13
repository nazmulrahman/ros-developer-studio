"""Process-wide session state (single robot / single session in V1)."""
from dataclasses import dataclass, field
from .config import Settings, load_settings
from .models import Mode


@dataclass
class AppState:
    settings: Settings = field(default_factory=load_settings)
    mode: Mode = Mode.live
    agent_connected: bool = False      # becomes real in Phase 2
    test_tools_enabled: bool = False   # always False at start


state = AppState()
