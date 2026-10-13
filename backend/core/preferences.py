"""Atomic, bounded user preferences. Does not store credentials or enable robot writes."""
import json
import os
import threading
import uuid
from pathlib import Path
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_hz: float = Field(2, ge=0.5, le=5)
    motion_hz: float = Field(10, ge=1, le=50)
    stale_after_s: float = Field(3, ge=1, le=60)

class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    config: dict

class PreferenceStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def _read(self):
        if not self.path.exists(): return {"preferences": Preferences().model_dump(), "layouts": []}
        try:
            data = json.loads(self.path.read_text())
            Preferences.model_validate(data["preferences"])
            if not isinstance(data["layouts"], list): raise ValueError("Invalid layouts")
            return data
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise HTTPException(500, f"Cannot read saved preferences: {e}")

    def read(self):
        with self.lock: return self._read()

    def change(self, mutate):
        with self.lock:
            data = self._read()
            result = mutate(data)
            encoded = json.dumps(data, allow_nan=False)
            if len(encoded.encode()) > 512 * 1024: raise HTTPException(413, "Saved layouts exceed 512 KiB")
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_name(self.path.name + ".tmp")
                tmp.write_text(encoded)
                os.replace(tmp, self.path)
            except OSError as e: raise HTTPException(500, f"Cannot save preferences: {e}")
            return result

    def save_layout(self, layout, layout_id=None):
        if set(layout.config) - {"signals", "motion", "visualizations"}:
            raise HTTPException(422, "Layout can contain only signals, motion and visualizations")
        def mutate(data):
            item = {"id": layout_id or uuid.uuid4().hex, **layout.model_dump()}
            if layout_id:
                index = next((i for i, x in enumerate(data["layouts"]) if x["id"] == layout_id), None)
                if index is None: raise HTTPException(404, "Layout not found")
                data["layouts"][index] = item
            else:
                if len(data["layouts"]) >= 32: raise HTTPException(409, "Maximum 32 saved layouts")
                data["layouts"].append(item)
            return item
        return self.change(mutate)
