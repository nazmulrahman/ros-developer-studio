"""Bounded, source-labelled TF frame model merged across /tf-style topics."""
from __future__ import annotations

import math
import time
from collections import OrderedDict
from typing import Any


def _items(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return value["items"]
    return []


class TfTree:
    def __init__(self, limit: int = 2000):
        self.limit = limit
        self.edges: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def clear(self) -> None:
        self.edges.clear()

    def ingest(self, event: dict[str, Any]) -> bool:
        data = event.get("visual", {}).get("data", {})
        topic = str(event.get("topic", ""))
        receive_ns = int(event.get("stamps", {}).get("receive_ns") or event.get("t_ns") or time.time_ns())
        changed = False
        for transform in _items(data.get("transforms")):
            header = transform.get("header", {}) if isinstance(transform, dict) else {}
            parent, child = header.get("frame_id"), transform.get("child_frame_id") if isinstance(transform, dict) else None
            if not isinstance(parent, str) or not isinstance(child, str) or not parent.strip() or not child.strip():
                continue
            parent, child = parent.strip(), child.strip()
            stamp = header.get("stamp", {})
            stamp_ns = None
            if isinstance(stamp, dict) and isinstance(stamp.get("sec"), int) and isinstance(stamp.get("nanosec"), int):
                stamp_ns = stamp["sec"] * 1_000_000_000 + stamp["nanosec"]
            key = f"{parent}\0{child}"
            edge = {"id": key, "parent": parent, "child": child, "topic": topic,
                    "static": topic.rstrip("/").endswith("tf_static") or "static" in topic.lower(),
                    "stamp_ns": str(stamp_ns) if stamp_ns is not None else None,
                    "receive_ns": str(receive_ns), "transform": transform.get("transform", {})}
            self.edges.pop(key, None)
            self.edges[key] = edge
            changed = True
        while len(self.edges) > self.limit:
            self.edges.popitem(last=False)
        return changed

    def snapshot(self, now_ns: int | None = None, stale_after_s: float = 3.0) -> dict[str, Any]:
        now_ns = now_ns or time.time_ns()
        edges = list(self.edges.values())
        frames = sorted({str(e[k]) for e in edges for k in ("parent", "child")})
        parents: dict[str, set[str]] = {}; all_children: set[str] = set()
        adjacency: dict[str, set[str]] = {frame: set() for frame in frames}
        directed: dict[str, list[str]] = {frame: [] for frame in frames}
        diagnostics: list[dict[str, str]] = []
        for edge in edges:
            all_children.add(edge["child"])
            adjacency[edge["parent"]].add(edge["child"]); adjacency[edge["child"]].add(edge["parent"])
            directed[edge["parent"]].append(edge["child"])
            edge["age_s"] = max(0.0, (now_ns - int(edge["receive_ns"])) / 1e9)
            edge["stale"] = not edge["static"] and edge["age_s"] > stale_after_s
            if edge["static"] or not edge["stale"]:
                parents.setdefault(edge["child"], set()).add(edge["parent"])
            transform = edge.get("transform", {})
            q = transform.get("rotation", {}) if isinstance(transform, dict) else {}
            values = [q.get(k) for k in ("x", "y", "z", "w")] if isinstance(q, dict) else []
            valid = len(values) == 4 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in values)
            edge["valid_rotation"] = valid and math.sqrt(sum(float(x) ** 2 for x in values)) > 1e-8
            if edge["stale"]:
                diagnostics.append({"severity": "warn", "code": "stale", "message": f"Dynamic transform {edge['parent']} → {edge['child']} is stale"})
            if not edge["valid_rotation"]:
                diagnostics.append({"severity": "error", "code": "rotation", "message": f"Transform {edge['parent']} → {edge['child']} has an invalid quaternion"})
            if edge["parent"] == edge["child"]:
                diagnostics.append({"severity": "error", "code": "self", "message": f"Frame {edge['child']} is its own parent"})
        for child, values in parents.items():
            if len(values) > 1:
                diagnostics.append({"severity": "error", "code": "multiple_parents", "message": f"Frame {child} has multiple observed parents: {', '.join(sorted(values))}"})
        visiting: set[str] = set(); visited: set[str] = set(); cycles: set[tuple[str, ...]] = set()
        def walk(node: str, trail: list[str]) -> None:
            if node in visiting:
                cycle = trail[trail.index(node):] + [node] if node in trail else [node, node]
                cycles.add(tuple(cycle)); return
            if node in visited: return
            visiting.add(node)
            for child in directed.get(node, []): walk(child, trail + [node])
            visiting.remove(node); visited.add(node)
        for frame in frames: walk(frame, [])
        for cycle in sorted(cycles):
            diagnostics.append({"severity": "error", "code": "cycle", "message": "TF cycle: " + " → ".join(cycle)})
        components: list[list[str]] = []; remaining = set(frames)
        while remaining:
            todo = [min(remaining)]; component: set[str] = set()
            while todo:
                node = todo.pop()
                if node in component: continue
                component.add(node); todo.extend(adjacency[node] - component)
            remaining -= component; components.append(sorted(component))
        components.sort(key=lambda x: (-len(x), x))
        roots = sorted(frame for frame in frames if frame not in all_children)
        if len(components) > 1:
            diagnostics.append({"severity": "warn", "code": "disconnected", "message": f"TF contains {len(components)} disconnected frame groups"})
        return {"frames": frames, "edges": edges, "roots": roots, "components": components,
                "diagnostics": diagnostics, "updated_ns": str(now_ns), "limit": self.limit}
