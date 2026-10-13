from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..core.auth import require_auth
from ..core.workspace_roots import browsable, browse_locations, directory_rows
from ..package_explorer.analyzer import WorkspaceError, read_source, resolve_allowed, scan_workspace

router = APIRouter(prefix="/api/package-explorer", tags=["package-explorer"], dependencies=[Depends(require_auth)])
_locks: dict[str, asyncio.Lock] = {}


class WorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)


class WorkspaceLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(pattern=r"^[a-f0-9]{24}$")
    mode: str = Field(default="dependencies", pattern=r"^(dependencies|architecture|launch|live|comparison)$")
    viewport: dict[str, float] = Field(default_factory=dict)
    positions: dict[str, dict[str, float]] = Field(default_factory=dict)
    groups: list[dict[str, Any]] = Field(default_factory=list)


def _roots(request: Request) -> list[str]:
    return request.app.state.workspace_roots.roots()


def _resolve(path: str, request: Request) -> Path:
    try:
        return resolve_allowed(path, _roots(request))
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except WorkspaceError as exc:
        raise HTTPException(422, str(exc)) from exc


def _layout_path(request: Request, workspace_id: str) -> Path:
    base = Path(os.environ.get("STUDIO_PACKAGE_LAYOUTS", "config/package_layouts"))
    return base / f"{workspace_id}.json"


@router.get("/roots")
def roots(request: Request):
    rows = []
    for raw in _roots(request):
        path = Path(raw).expanduser()
        rows.append({"path": str(path), "available": path.is_dir()})
    return rows


@router.get("/browse")
def browse(request: Request, path: str | None = Query(default=None)):
    try:
        current = browsable(path)
        locations = browse_locations()
        parent = current.parent if any(base == current.parent or base in current.parent.parents for base in locations) else None
        return {
            "path": str(current),
            "parent": str(parent) if parent else None,
            "locations": [{"name": p.name or str(p), "path": str(p)} for p in locations],
            "directories": directory_rows(current),
        }
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/roots")
async def add_root(req: WorkspaceRequest, request: Request):
    try:
        selected = browsable(req.path)
        result = await asyncio.to_thread(scan_workspace, selected)
        count = result["summary"]["packages"]
        if count == 0:
            raise HTTPException(422, "No ROS packages were found below this folder")
        saved = request.app.state.workspace_roots.add(selected)
        return {"path": saved, "available": True, "packages": count}
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/scan")
async def scan(req: WorkspaceRequest, request: Request):
    root = _resolve(req.path, request)
    lock = _locks.setdefault(str(root), asyncio.Lock())
    if lock.locked():
        raise HTTPException(409, "This workspace is already being scanned")
    async with lock:
        try:
            return await asyncio.to_thread(scan_workspace, root)
        except Exception as exc:
            if isinstance(exc, HTTPException): raise
            raise HTTPException(422, f"Workspace scan failed: {type(exc).__name__}: {exc}") from exc


@router.get("/file")
async def source_file(request: Request, workspace: str = Query(...), path: str = Query(...)):
    root = _resolve(workspace, request)
    try:
        return await asyncio.to_thread(read_source, root, path)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (WorkspaceError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/layouts/{workspace_id}")
def get_layout(workspace_id: str, request: Request):
    if not all(c in "0123456789abcdef" for c in workspace_id) or len(workspace_id) != 24:
        raise HTTPException(422, "Invalid workspace identity")
    path = _layout_path(request, workspace_id)
    if not path.is_file(): return None
    try: return json.loads(path.read_text())
    except (OSError, ValueError) as exc: raise HTTPException(500, f"Cannot read saved package layout: {exc}")


@router.put("/layouts/{workspace_id}")
def save_layout(workspace_id: str, layout: WorkspaceLayout, request: Request):
    if workspace_id != layout.workspace_id:
        raise HTTPException(422, "Workspace identity mismatch")
    if len(layout.positions) > 5000 or len(layout.groups) > 200:
        raise HTTPException(413, "Layout exceeds the persistence limits")
    path = _layout_path(request, workspace_id)
    encoded = json.dumps(layout.model_dump(), separators=(",", ":"), allow_nan=False)
    if len(encoded.encode()) > 2 * 1024 * 1024:
        raise HTTPException(413, "Layout exceeds 2 MiB")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(encoded)
        os.replace(tmp, path)
    except OSError as exc: raise HTTPException(500, f"Cannot save package layout: {exc}")
    return layout
