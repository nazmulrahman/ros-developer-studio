"""Small persistent store for explicit, user-authored diagnostic expectations."""
from __future__ import annotations

import json, os, threading, uuid
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Expectation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    topic: str = Field(pattern=r"^/[A-Za-z0-9_/]+$")
    field: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.]+$")
    minimum: float | None = None
    maximum: float | None = None

    @field_validator("maximum")
    @classmethod
    def valid_bounds(cls, value, info):
        low = info.data.get("minimum")
        if low is None and value is None: raise ValueError("Set a minimum, a maximum, or both")
        if low is not None and value is not None and low > value: raise ValueError("Minimum must not exceed maximum")
        return value


class ProfileStore:
    def __init__(self, path: str):
        self.path = Path(path); self.lock = threading.Lock()

    def read(self):
        with self.lock:
            if not self.path.exists(): return []
            data = json.loads(self.path.read_text())
            if not isinstance(data, list) or len(data) > 100: raise ValueError("Invalid diagnostic profile store")
            return data

    def save(self, item: Expectation):
        with self.lock:
            rows = []
            if self.path.exists(): rows = json.loads(self.path.read_text())
            if len(rows) >= 20: raise ValueError("Maximum 20 diagnostic expectations")
            saved = {"id": uuid.uuid4().hex, **item.model_dump()}; rows.append(saved)
            self._write(rows); return saved

    def delete(self, profile_id: str):
        with self.lock:
            rows = json.loads(self.path.read_text()) if self.path.exists() else []
            kept = [row for row in rows if row.get("id") != profile_id]
            if len(kept) == len(rows): return False
            self._write(kept); return True

    def _write(self, rows):
        encoded = json.dumps(rows, allow_nan=False)
        if len(encoded.encode()) > 256 * 1024: raise ValueError("Diagnostic profiles exceed 256 KiB")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp"); tmp.write_text(encoded); os.replace(tmp, self.path)
