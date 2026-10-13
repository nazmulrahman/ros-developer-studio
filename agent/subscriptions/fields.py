"""Generic ROS message introspection. Works on rclpy messages and on plain dicts (tests)."""
from __future__ import annotations
import itertools, math, re
from collections.abc import Mapping
from typing import Any, Callable

NUMERIC = {"float", "double", "long double", "int8", "uint8", "int16", "uint16", "int32", "uint32",
           "int64", "uint64", "bool", "byte", "char", "octet"}
_TOKEN = re.compile(r"([A-Za-z_]\w*)|\[(\d+)\]")


def _split(t: str) -> tuple[str, str, int | None]:
    if t.startswith("sequence<"):
        return "seq", t[9:-1].split(",")[0].strip(), None
    if t.endswith("]"):
        base, _, n = t.rpartition("[")
        return "array", base, int(n[:-1]) if n[:-1].isdigit() else None
    return "scalar", t, None


def _norm(t: str) -> str:
    return f"{t.split('/')[0]}/msg/{t.split('/')[1]}" if t.count("/") == 1 else t


def numeric_fields(resolve: Callable[[str], Any], type_name: str, max_depth: int = 6,
                   max_fixed: int = 32, limit: int = 500) -> list[dict]:
    """Enumerate numeric leaf paths from the type schema. Paths containing '[]' need a user-supplied index."""
    out: list[dict] = []

    def walk(tn: str, prefix: str, depth: int) -> None:
        for name, ft in resolve(tn).get_fields_and_field_types().items():
            if len(out) >= limit:
                return
            kind, base, size = _split(ft)
            p = f"{prefix}{name}"
            if base in NUMERIC:
                if kind == "scalar":
                    out.append({"path": p, "type": base, "needs_index": False})
                elif kind == "array" and size and size <= max_fixed:
                    out.extend({"path": f"{p}[{i}]", "type": base, "needs_index": False} for i in range(size))
                else:
                    out.append({"path": f"{p}[]", "type": base, "needs_index": True})
            elif base.startswith(("string", "wstring")) or "/" not in base or depth >= max_depth:
                continue
            elif kind == "scalar":
                walk(_norm(base), p + ".", depth + 1)
            elif kind == "array" and size and size <= 4:
                for i in range(size):
                    walk(_norm(base), f"{p}[{i}].", depth + 1)
            else:
                walk(_norm(base), p + "[].", depth + 1)

    walk(type_name, "", 0)
    return out


def _child(o: Any, key: Any) -> Any:
    if isinstance(key, int):
        return o[key]
    return o[key] if isinstance(o, Mapping) else getattr(o, key)


def get_path(msg: Any, path: str) -> float | None:
    """Extract a numeric value by dotted path with [i] indexes. Returns None if missing/non-numeric/non-finite."""
    try:
        o = msg
        for name, idx in _TOKEN.findall(path):
            o = _child(o, int(idx) if idx else name)
        if hasattr(o, "item") and not hasattr(o, "__len__"):
            o = o.item()
        if isinstance(o, bool):
            return 1.0 if o else 0.0
        if isinstance(o, (int, float)):
            v = float(o)
            return v if math.isfinite(v) else None
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        pass
    return None


def describe(o: Any, max_items: int = 64, max_depth: int = 10, _d: int = 0) -> Any:
    """JSON-safe structured view. Long arrays and byte blobs are summarised, never fully converted."""
    if _d > max_depth:
        return "…"
    if hasattr(o, "get_fields_and_field_types"):
        return {n: describe(getattr(o, n), max_items, max_depth, _d + 1) for n in o.get_fields_and_field_types()}
    if isinstance(o, Mapping):
        return {str(k): describe(v, max_items, max_depth, _d + 1) for k, v in o.items()}
    if isinstance(o, (bytes, bytearray)):
        return {"__bytes__": len(o)}
    if isinstance(o, str):
        return o if len(o) <= 2000 else o[:2000] + "…"
    if isinstance(o, bool):
        return o
    if hasattr(o, "item") and not hasattr(o, "__len__"):
        o = o.item()
    if isinstance(o, int):
        return o
    if isinstance(o, float):
        return o if math.isfinite(o) else ("NaN" if math.isnan(o) else ("Infinity" if o > 0 else "-Infinity"))
    if hasattr(o, "__len__") and hasattr(o, "__iter__"):
        n = len(o)
        items = [describe(x, max_items, max_depth, _d + 1) for x in itertools.islice(o, max_items)]
        return {"__truncated__": n, "shown": max_items, "items": items} if n > max_items else items
    return str(o)
