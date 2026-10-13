"""Persist user-approved Package Explorer roots and provide safe directory browsing."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path


class WorkspaceRootStore:
    def __init__(self, path: str, configured: list[str]):
        self.path = Path(path)
        self.configured = configured
        self.lock = threading.Lock()

    def _saved(self) -> list[str]:
        if not self.path.is_file():
            return []
        data = json.loads(self.path.read_text())
        if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
            raise ValueError("Workspace root settings must be a list of paths")
        return data[:100]

    def roots(self) -> list[str]:
        with self.lock:
            rows = [str(Path(x).expanduser().resolve()) for x in [*self.configured, *self._saved()]]
            return list(dict.fromkeys(rows))

    def add(self, path: Path) -> str:
        resolved = str(path.resolve())
        with self.lock:
            saved = self._saved()
            configured = {str(Path(x).expanduser().resolve()) for x in self.configured}
            if resolved not in configured and resolved not in saved:
                if len(saved) >= 100:
                    raise ValueError("Maximum 100 added workspace roots")
                saved.append(resolved)
                encoded = json.dumps(saved, indent=2)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(self.path.suffix + ".tmp")
                tmp.write_text(encoded)
                os.replace(tmp, self.path)
        return resolved


def browse_locations() -> list[Path]:
    home = Path.home().resolve()
    candidates = [home, Path("/media") / home.name, Path("/mnt"), Path("/opt")]
    return [path.resolve() for path in candidates if path.is_dir()]


def browsable(path: str | None) -> Path:
    locations = browse_locations()
    target = Path(path).expanduser().resolve() if path else locations[0]
    if not any(target == base or base in target.parents for base in locations):
        raise PermissionError("Folder browsing is limited to the home, media, mount, and optional-software directories")
    if not target.is_dir():
        raise ValueError("Folder does not exist or is not a directory")
    return target


def directory_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    try:
        children = sorted(path.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        raise ValueError(f"Cannot read folder: {exc}") from exc
    for child in children:
        if child.name.startswith(".") or child.is_symlink():
            continue
        try:
            if child.is_dir():
                rows.append({"name": child.name, "path": str(child.resolve()), "package": (child / "package.xml").is_file()})
        except OSError:
            continue
        if len(rows) >= 1000:
            break
    return rows
