"""Restricted ROS 2 bag library, reader, analyser and recorder controller."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import signal
import sqlite3
import statistics
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Iterable

import yaml

from ..package_explorer.analyzer import resolve_allowed

MAX_MESSAGES = 10_000
MAX_ANALYSIS_MESSAGES = 2_000_000


class BagError(ValueError): pass


def _bag_id(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:24]


def _storage(path: Path, metadata: dict | None = None) -> str:
    value = ((metadata or {}).get("rosbag2_bagfile_information") or {}).get("storage_identifier")
    if value: return str(value)
    if path.suffix == ".mcap" or any(path.glob("*.mcap")): return "mcap"
    if path.suffix == ".db3" or any(path.glob("*.db3")): return "sqlite3"
    raise BagError("No SQLite3 or MCAP bag data was found")


def _metadata(path: Path) -> dict:
    candidate = path / "metadata.yaml" if path.is_dir() else path.parent / "metadata.yaml"
    if not candidate.is_file(): return {}
    try: return yaml.safe_load(candidate.read_text()) or {}
    except (OSError, yaml.YAMLError) as exc: raise BagError(f"Cannot read metadata.yaml: {exc}") from exc


def _db_files(path: Path) -> list[Path]:
    rows = sorted(path.glob("*.db3")) if path.is_dir() else [path]
    if not rows: raise BagError("No SQLite3 .db3 files were found")
    return rows


def _sqlite_topics(path: Path) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], int] = {}
    for db in _db_files(path):
        try:
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                rows = conn.execute("SELECT t.name,t.type,COUNT(m.id) FROM topics t LEFT JOIN messages m ON m.topic_id=t.id GROUP BY t.id").fetchall()
        except sqlite3.Error as exc: raise BagError(f"Cannot read {db.name}: {exc}") from exc
        for name, type_name, count in rows: merged[(name, type_name)] = merged.get((name, type_name), 0) + int(count)
    return [{"name": n, "type": t, "count": c} for (n, t), c in sorted(merged.items())]


def _sqlite_bounds(path: Path) -> tuple[int | None, int | None, int]:
    start = end = None; count = 0
    for db in _db_files(path):
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            lo, hi, n = conn.execute("SELECT MIN(timestamp),MAX(timestamp),COUNT(*) FROM messages").fetchone()
        if lo is not None: start = int(lo) if start is None else min(start, int(lo))
        if hi is not None: end = int(hi) if end is None else max(end, int(hi))
        count += int(n)
    return start, end, count


def _describe_message(raw: bytes, type_name: str) -> tuple[dict | None, str | None]:
    try:
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
        from agent.subscriptions.fields import describe
        return describe(deserialize_message(raw, get_message(type_name)), max_items=512), None
    except Exception as exc:
        return None, f"Deserialization unavailable: {type(exc).__name__}: {exc}"


class BagLibrary:
    def __init__(self, roots: list[str]):
        self.roots = [str(Path(x).expanduser().resolve()) for x in roots]
        self.opened: dict[str, Path] = {}

    def resolve(self, raw: str) -> Path:
        try: return resolve_allowed(raw, self.roots)
        except (PermissionError, ValueError) as exc: raise BagError(str(exc)) from exc

    def list(self) -> list[dict[str, Any]]:
        found: dict[str, Path] = {}
        for root_text in self.roots:
            root = Path(root_text)
            if not root.is_dir(): continue
            for current, dirs, files in os.walk(root):
                rel_depth = len(Path(current).relative_to(root).parts)
                dirs[:] = [d for d in dirs if not d.startswith(".") and not Path(current, d).is_symlink() and rel_depth < 4]
                names = set(files)
                if "metadata.yaml" in names or any(name.endswith((".db3", ".mcap")) for name in names):
                    bag = Path(current); found[str(bag.resolve())] = bag; dirs[:] = []
        return [self.summary(path) for path in sorted(found.values())]

    def summary(self, raw: str | Path) -> dict[str, Any]:
        path = self.resolve(str(raw)); metadata = _metadata(path); storage = _storage(path, metadata)
        warnings: list[str] = []
        info = metadata.get("rosbag2_bagfile_information", {})
        topics = []
        for row in info.get("topics_with_message_count", []) or []:
            meta = row.get("topic_metadata", {}); topics.append({"name": meta.get("name"), "type": meta.get("type"), "count": int(row.get("message_count", 0))})
        if storage == "sqlite3":
            db_topics = _sqlite_topics(path); topics = db_topics or topics
            start, end, count = _sqlite_bounds(path)
        else:
            start_block = info.get("starting_time", {}); start = start_block.get("nanoseconds_since_epoch")
            duration = (info.get("duration") or {}).get("nanoseconds")
            end = int(start) + int(duration) if start is not None and duration is not None else None
            count = int(info.get("message_count", sum(x["count"] for x in topics)))
            if not topics: warnings.append("MCAP metadata is incomplete; rosbag2_py is required to inspect messages")
        bag_id = _bag_id(path); self.opened[bag_id] = path
        return {"bag_id": bag_id, "path": str(path), "storage": storage, "duration_ns": None if start is None or end is None else int(end) - int(start),
                "start_ns": start, "end_ns": end, "message_count": count, "topics": topics, "warnings": warnings}

    def get(self, bag_id: str) -> Path:
        path = self.opened.get(bag_id)
        if not path: raise KeyError("Bag is not open")
        return path

    def messages(self, bag_id: str, topic: str, start_ns: int | None, end_ns: int | None, limit: int) -> list[dict[str, Any]]:
        path = self.get(bag_id); meta = self.summary(path); type_name = next((x["type"] for x in meta["topics"] if x["name"] == topic), None)
        if not type_name: raise BagError("Topic is not present in this bag")
        if meta["storage"] != "sqlite3": return self._rosbag2_messages(path, topic, type_name, start_ns, end_ns, limit)
        result = []
        for db in _db_files(path):
            query = "SELECT m.timestamp,m.data FROM messages m JOIN topics t ON t.id=m.topic_id WHERE t.name=?"
            args: list[Any] = [topic]
            if start_ns is not None: query += " AND m.timestamp>=?"; args.append(start_ns)
            if end_ns is not None: query += " AND m.timestamp<=?"; args.append(end_ns)
            query += " ORDER BY m.timestamp LIMIT ?"; args.append(limit)
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn: rows = conn.execute(query, args).fetchall()
            for stamp, raw in rows:
                payload, error = _describe_message(raw, type_name)
                result.append({"record_ns": str(stamp), "topic": topic, "type": type_name, "size": len(raw), "payload": payload, "error": error})
        return sorted(result, key=lambda x: int(x["record_ns"]))[:limit]

    def _rosbag2_messages(self, path: Path, topic: str, type_name: str, start_ns: int | None, end_ns: int | None, limit: int):
        try:
            import rosbag2_py
            reader = rosbag2_py.SequentialReader(); reader.open(rosbag2_py.StorageOptions(uri=str(path), storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
            reader.set_filter(rosbag2_py.StorageFilter(topics=[topic])); rows = []
            while reader.has_next() and len(rows) < limit:
                name, raw, stamp = reader.read_next()
                if start_ns is not None and stamp < start_ns: continue
                if end_ns is not None and stamp > end_ns: break
                payload, error = _describe_message(raw, type_name); rows.append({"record_ns": str(stamp), "topic": name, "type": type_name, "size": len(raw), "payload": payload, "error": error})
            return rows
        except Exception as exc: raise BagError(f"MCAP reading unavailable: {type(exc).__name__}: {exc}") from exc

    def snapshot(self, bag_id: str, topic: str, cursor_ns: int) -> dict | None:
        """Latest recorded sample at/before the shared cursor, with native previews."""
        meta = self.summary(self.get(bag_id))
        type_name = next((t["type"] for t in meta["topics"] if t["name"] == topic), None)
        if not type_name: raise BagError("Topic is not in this recording")
        candidates = []
        if meta["storage"] == "sqlite3":
            for db in _db_files(self.get(bag_id)):
                with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                    row = conn.execute("SELECT m.timestamp,m.data FROM messages m JOIN topics t ON t.id=m.topic_id WHERE t.name=? AND m.timestamp<=? ORDER BY m.timestamp DESC LIMIT 1", (topic, cursor_ns)).fetchone()
                if row: candidates.append(row)
        else:
            try:
                import rosbag2_py
                reader = rosbag2_py.SequentialReader()
                reader.open(rosbag2_py.StorageOptions(uri=str(self.get(bag_id)), storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
                reader.set_filter(rosbag2_py.StorageFilter(topics=[topic]))
                while reader.has_next():
                    _, raw, timestamp = reader.read_next()
                    if timestamp > cursor_ns: break
                    candidates[:] = [(timestamp, raw)]
            except Exception as exc: raise BagError(f"MCAP snapshot unavailable: {exc}") from exc
        if not candidates: return None
        timestamp, raw = max(candidates, key=lambda x: x[0])
        payload, error = _describe_message(raw, type_name)
        visual = {"error": error} if error else {}
        header = None; values = {}
        try:
            from rclpy.serialization import deserialize_message
            from rosidl_runtime_py.utilities import get_message
            from agent.subscriptions.visual import preview, stamp
            from agent.subscriptions.fields import numeric_fields, get_path
            message = deserialize_message(raw, get_message(type_name))
            visual = preview(message, type_name); header = stamp(message)
            values = {f["path"]: get_path(message, f["path"]) for f in numeric_fields(get_message, type_name) if not f["needs_index"]}
        except Exception:
            pass
        return {"ch": "sample", "topic": topic, "type": type_name, "source_mode": "bag", "source_id": f"bag:{bag_id}", "t_ns": timestamp, "size": len(raw), "payload": payload, "visual": visual, "values": values, "stamps": {"record_ns": str(timestamp), "receive_ns": None, "header_ns": str(header) if header is not None else None}}

    def topic_detail(self, bag_id: str, topic: str) -> dict:
        meta = self.summary(self.get(bag_id)); row = next((t for t in meta["topics"] if t["name"] == topic), None)
        if not row: raise BagError("Topic is not in this recording")
        fields = []; error = None
        try:
            from rosidl_runtime_py.utilities import get_message
            from agent.subscriptions.fields import numeric_fields
            fields = numeric_fields(get_message, row["type"])
        except Exception as exc: error = str(exc)
        return {"name": topic, "types": [row["type"]], "publishers": [], "subscribers": [], "qos_conflicts": [], "fields": fields, "fields_error": error, "monitored": False}

    def timestamps(self, bag_id: str, topic: str) -> list[int]:
        path = self.get(bag_id); meta = self.summary(path)
        if meta["storage"] != "sqlite3":
            return [int(x["record_ns"]) for x in self.messages(bag_id, topic, None, None, MAX_ANALYSIS_MESSAGES)]
        values: list[int] = []
        for db in _db_files(path):
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                values.extend(int(x[0]) for x in conn.execute("SELECT m.timestamp FROM messages m JOIN topics t ON t.id=m.topic_id WHERE t.name=? ORDER BY m.id LIMIT ?", (topic, MAX_ANALYSIS_MESSAGES)))
        return values

    def analysis(self, bag_id: str) -> dict[str, Any]:
        meta = self.summary(self.get(bag_id)); rows = []
        for topic in meta["topics"]:
            stamps = self.timestamps(bag_id, topic["name"]); ordered = sorted(stamps); gaps = [b-a for a,b in zip(ordered, ordered[1:]) if b >= a]
            median = statistics.median(gaps) if gaps else None
            # Use the lower median as the normal cadence so a single long pause
            # cannot inflate its own detection threshold on short recordings.
            baseline = statistics.median_low(gaps) if gaps else 0
            threshold = max(baseline * 5, 1_000_000_000)
            rows.append({**topic, "first_ns": str(min(stamps)) if stamps else None, "last_ns": str(max(stamps)) if stamps else None,
                         "median_period_ns": median, "max_gap_ns": max(gaps) if gaps else None,
                         "gap_count": sum(g > threshold for g in gaps), "non_monotonic": sum(b < a for a,b in zip(stamps, stamps[1:])),
                         "truncated": len(stamps) >= MAX_ANALYSIS_MESSAGES})
        return {"bag_id": bag_id, "topics": rows}

    def findings(self, bag_id: str) -> list[dict[str, Any]]:
        """Produce conservative, evidence-backed findings without robot-specific limits."""
        meta = self.summary(self.get(bag_id)); timing = self.analysis(bag_id); findings: list[dict[str, Any]] = []

        def add(severity: str, component: str, evidence: str, causes: list[str], checks: list[str]):
            findings.append({"severity": severity, "component": component, "evidence": evidence,
                             "possible_causes": causes, "suggested_checks": checks})

        for row in timing["topics"]:
            name = row["name"]
            if row["count"] == 0:
                add("warning", name, "The bag metadata contains this topic but it has zero recorded messages.",
                    ["The publisher was inactive", "Recording started or stopped outside the event", "A topic filter excluded its data"],
                    ["Compare the recording interval with the expected publisher lifetime", "Check the recorder topic selection"])
            if row["non_monotonic"]:
                add("error", name, f"{row['non_monotonic']} recorded timestamp reversal(s) were found.",
                    ["System clock adjustment", "Messages from split storage files are out of order", "Recorder or storage corruption"],
                    ["Inspect timestamps around each reversal", "Check NTP/PTP and system clock logs", "Run ros2 bag info and storage integrity checks"])
            if row["gap_count"]:
                add("warning", name, f"{row['gap_count']} unusually long gap(s); maximum {row['max_gap_ns'] / 1e9:.3f} s versus median period {(row['median_period_ns'] or 0) / 1e9:.3f} s.",
                    ["Publisher stalled or restarted", "DDS delivery or recorder could not keep up", "CPU, disk, or network saturation"],
                    ["Inspect other topics at the same time to separate publisher and host-wide stalls", "Compare host metrics and ROS logs", "Check offered QoS and recorder lost-message reports"])
            if row["truncated"]:
                add("info", name, f"Timing analysis reached its {MAX_ANALYSIS_MESSAGES:,}-message safety limit.",
                    ["The recording is large"], ["Analyse a narrower time range if later anomalies are suspected"])

            samples = self.messages(bag_id, name, None, None, min(50, max(1, row["count"]))) if row["count"] else []
            failures = [sample for sample in samples if sample["payload"] is None]
            if failures:
                add("warning", name, f"{len(failures)} of {len(samples)} sampled messages could not be decoded; first error: {failures[0]['error']}",
                    ["The message package is not installed", "The workspace defining a custom type was not sourced", "The recorded type differs from the installed definition"],
                    ["Source the recording's ROS distribution and workspace before starting Studio", "Confirm the topic type in metadata.yaml"])
                continue
            for sample in samples:
                payload = sample["payload"] or {}; type_name = sample["type"]
                if type_name == "sensor_msgs/msg/LaserScan":
                    values = payload.get("ranges", []); values = values.get("items", []) if isinstance(values, dict) else values
                    lo, hi = payload.get("range_min"), payload.get("range_max")
                    invalid = sum(not isinstance(v, (int, float)) or not math.isfinite(v) or (isinstance(lo, (int, float)) and v < lo) or (isinstance(hi, (int, float)) and v > hi) for v in values)
                    if values and invalid == len(values):
                        add("error", name, f"At record timestamp {sample['record_ns']}, all {len(values)} inspected scan ranges are invalid or outside the declared limits.",
                            ["LiDAR is not returning measurements", "Range limits or driver output are incorrect", "Sensor obstruction or communication failure"],
                            ["Inspect adjacent scans", "Compare range_min/range_max with the sensor specification", "Check the LiDAR driver and hardware logs"]); break
                if type_name == "sensor_msgs/msg/BatteryState":
                    percentage = payload.get("percentage")
                    if isinstance(percentage, (int, float)) and math.isfinite(percentage) and not 0 <= percentage <= 1:
                        add("error", name, f"Battery percentage {percentage} at record timestamp {sample['record_ns']} is outside the ROS BatteryState range 0..1.",
                            ["Driver published percent instead of a fraction", "Battery conversion or calibration is wrong"],
                            ["Check the battery driver's unit conversion", "Compare voltage and percentage with a trusted measurement"]); break
                quaternion = None
                if type_name == "sensor_msgs/msg/Imu" and (payload.get("orientation_covariance") or [0])[0] != -1: quaternion = payload.get("orientation")
                elif type_name == "nav_msgs/msg/Odometry": quaternion = (((payload.get("pose") or {}).get("pose") or {}).get("orientation"))
                if isinstance(quaternion, dict):
                    parts = [quaternion.get(k) for k in ("x", "y", "z", "w")]
                    if all(isinstance(v, (int, float)) for v in parts):
                        norm = math.sqrt(sum(float(v) ** 2 for v in parts))
                        if norm < 1e-8 or abs(norm - 1) > .05:
                            add("error", name, f"Quaternion norm is {norm:.4f} at record timestamp {sample['record_ns']}; expected approximately 1.",
                                ["Orientation was not normalized", "Sensor fusion output is invalid or uninitialized"],
                                ["Inspect covariance and neighboring messages", "Check IMU calibration and localization/fusion node logs"]); break
                if type_name == "diagnostic_msgs/msg/DiagnosticArray":
                    statuses = payload.get("status", []); statuses = statuses.get("items", []) if isinstance(statuses, dict) else statuses
                    for status in statuses:
                        if isinstance(status, dict) and status.get("level") in (1, 2, 3):
                            level = int(status["level"]); component = str(status.get("name") or name); message = str(status.get("message") or "No diagnostic message")
                            add("error" if level >= 2 else "warning", component, f"Recorded diagnostic level {level}: {message} (timestamp {sample['record_ns']}).",
                                ["The reporting ROS component detected a fault"], ["Inspect the diagnostic key/value fields and component logs at this timestamp"])
        order = {"error": 0, "warning": 1, "info": 2}
        return sorted(findings, key=lambda item: (order[item["severity"]], item["component"]))

    def export_csv(self, bag_id: str, topic: str, start_ns: int | None, end_ns: int | None, limit: int = MAX_MESSAGES) -> str:
        rows = self.messages(bag_id, topic, start_ns, end_ns, min(limit, MAX_MESSAGES)); output = io.StringIO(); writer = csv.writer(output)
        writer.writerow(["record_ns", "topic", "type", "size_bytes", "payload_json", "error"])
        for row in rows: writer.writerow([row["record_ns"], row["topic"], row["type"], row["size"], json.dumps(row["payload"], separators=(",", ":")) if row["payload"] is not None else "", row["error"] or ""])
        return output.getvalue()


class Recorder:
    def __init__(self, root: str):
        self.root = Path(root).expanduser().resolve(); self.process: subprocess.Popen | None = None; self.path: Path | None = None; self.started_ns: int | None = None; self.lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        with self.lock:
            if self.process and self.process.poll() is not None: self.process = None
            size = sum(p.stat().st_size for p in self.path.rglob("*") if p.is_file()) if self.path and self.path.exists() else 0
            return {"recording": self.process is not None, "path": str(self.path) if self.path else None, "started_ns": str(self.started_ns) if self.started_ns else None, "size_bytes": size}

    def start(self, name: str | None, topics: list[str], all_topics: bool) -> dict[str, Any]:
        with self.lock:
            if self.process and self.process.poll() is None: raise BagError("A recording is already active")
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name or time.strftime("bag-%Y%m%d-%H%M%S")).strip(".-")
            if not safe: raise BagError("Recording name is invalid")
            if not all_topics and not topics: raise BagError("Select at least one topic or all topics")
            if any(not re.fullmatch(r"/[A-Za-z0-9_/]+", topic) for topic in topics): raise BagError("A topic name is invalid")
            self.root.mkdir(parents=True, exist_ok=True); target = self.root / safe
            if target.exists(): raise BagError("A bag with this name already exists")
            cmd = ["ros2", "bag", "record", "-o", str(target), *( ["-a"] if all_topics else topics)]
            try: self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError as exc: raise BagError(f"Cannot start ros2 bag record: {exc}") from exc
            self.path, self.started_ns = target, time.time_ns(); return self.status_unlocked()

    def status_unlocked(self):
        return {"recording": self.process is not None and self.process.poll() is None, "path": str(self.path) if self.path else None, "started_ns": str(self.started_ns) if self.started_ns else None, "size_bytes": 0}

    def stop(self) -> dict[str, Any]:
        with self.lock:
            if not self.process or self.process.poll() is not None: raise BagError("No recording is active")
            os.killpg(self.process.pid, signal.SIGINT)
            try: self.process.wait(timeout=10)
            except subprocess.TimeoutExpired: self.process.terminate(); self.process.wait(timeout=3)
            self.process = None
        return self.status()
