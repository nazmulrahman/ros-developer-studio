from __future__ import annotations

import ast
import hashlib
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SKIP_DIRS = {".git", ".venv", "__pycache__", "build", "install", "log", "node_modules"}
SOURCE_EXTENSIONS = {".py", ".cpp", ".cc", ".cxx", ".c", ".hpp", ".hh", ".h"}
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".rviz"}
ROBOT_EXTENSIONS = {".urdf", ".xacro", ".sdf"}
VIEWABLE_EXTENSIONS = SOURCE_EXTENSIONS | CONFIG_EXTENSIONS | ROBOT_EXTENSIONS | {".xml", ".cmake", ".launch"}
MAX_PACKAGES = 1000
MAX_FILES_PER_PACKAGE = 3000
MAX_FILE_BYTES = 2 * 1024 * 1024
DEPENDENCY_TAGS = {
    "depend", "build_depend", "build_export_depend", "buildtool_depend", "exec_depend",
    "run_depend", "test_depend", "doc_depend", "group_depend", "member_of_group",
}


class WorkspaceError(ValueError):
    pass


def resolve_allowed(path: str, roots: Iterable[str]) -> Path:
    try:
        target = Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise WorkspaceError(f"Workspace path is unavailable: {exc}") from exc
    if not target.is_dir():
        raise WorkspaceError("Workspace path is not a directory")
    allowed = []
    for raw in roots:
        try:
            allowed.append(Path(raw).expanduser().resolve(strict=True))
        except OSError:
            continue
    if not any(target == root or root in target.parents for root in allowed):
        raise PermissionError("Workspace is outside the configured workspace roots")
    return target


def workspace_id(root: Path) -> str:
    return hashlib.sha256(os.fsencode(str(root))).hexdigest()[:24]


def _walk(root: Path):
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not Path(current, d).is_symlink())
        yield Path(current), files


def discover_package_xml(root: Path) -> list[Path]:
    found: list[Path] = []
    for current, files in _walk(root):
        if "package.xml" in files:
            found.append(current / "package.xml")
            if len(found) >= MAX_PACKAGES:
                break
    return found


def _text(node: ET.Element | None) -> str | None:
    return (node.text or "").strip() if node is not None and (node.text or "").strip() else None


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _file_kind(path: Path) -> str:
    name, suffix = path.name.lower(), path.suffix.lower()
    if "launch" in path.parts or name.endswith((".launch.py", ".launch.xml", ".launch.yaml", ".launch.yml")):
        return "launch"
    if suffix in CONFIG_EXTENSIONS or "config" in path.parts:
        return "config"
    if suffix in ROBOT_EXTENSIONS:
        return "robot_description"
    if suffix in SOURCE_EXTENSIONS:
        return "source"
    if name in {"package.xml", "cmakelists.txt", "setup.py", "setup.cfg"}:
        return "metadata"
    return "other"


def _package_files(package_root: Path, workspace_root: Path) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    truncated = False
    for current, files in _walk(package_root):
        for name in sorted(files):
            path = current / name
            if path.is_symlink() or not path.is_file():
                continue
            kind = _file_kind(path)
            if kind == "other" and path.suffix.lower() not in VIEWABLE_EXTENSIONS:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            rows.append({"path": _relative(path, workspace_root), "name": name, "kind": kind, "size": size})
            if len(rows) >= MAX_FILES_PER_PACKAGE:
                truncated = True
                return rows, truncated
    return rows, truncated


def _constant_string(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def analyze_python_launch(path: Path, rel: str) -> dict[str, Any]:
    result: dict[str, Any] = {"path": rel, "format": "python", "nodes": [], "includes": [], "arguments": [], "warnings": []}
    try:
        tree = ast.parse(path.read_text(errors="replace"), filename=rel)
    except (OSError, SyntaxError) as exc:
        result["warnings"].append(f"Could not parse statically: {exc}")
        return result
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = _call_name(node.func)
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        if call in {"Node", "LifecycleNode", "ComposableNode"}:
            row = {key: _constant_string(kwargs.get(key)) for key in ("package", "executable", "name", "namespace")}
            row["line"] = getattr(node, "lineno", None)
            row["evidence"] = "literal arguments in Python launch AST"
            if not row["package"] or not row["executable"]:
                row["dynamic"] = True
            result["nodes"].append(row)
        elif call == "IncludeLaunchDescription":
            result["includes"].append({"value": _constant_string(node.args[0]) if node.args else None,
                                       "line": getattr(node, "lineno", None), "dynamic": True})
        elif call == "DeclareLaunchArgument":
            result["arguments"].append({"name": _constant_string(node.args[0]) if node.args else None,
                                         "default": _constant_string(kwargs.get("default_value")),
                                         "line": getattr(node, "lineno", None)})
    if any(x.get("dynamic") for x in result["nodes"] + result["includes"]):
        result["warnings"].append("Dynamic Python expressions were not executed and may be unresolved.")
    return result


def analyze_xml_launch(path: Path, rel: str) -> dict[str, Any]:
    result: dict[str, Any] = {"path": rel, "format": "xml", "nodes": [], "includes": [], "arguments": [], "warnings": []}
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        result["warnings"].append(f"Could not parse statically: {exc}")
        return result
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag == "node":
            result["nodes"].append({"package": elem.get("pkg"), "executable": elem.get("exec"),
                                    "name": elem.get("name"), "namespace": elem.get("namespace"),
                                    "evidence": "XML launch element"})
        elif tag == "include":
            result["includes"].append({"value": elem.get("file"), "dynamic": "$" in (elem.get("file") or "")})
        elif tag == "arg":
            result["arguments"].append({"name": elem.get("name"), "default": elem.get("default")})
    return result


def analyze_launch(path: Path, workspace_root: Path) -> dict[str, Any]:
    rel = _relative(path, workspace_root)
    if path.name.endswith(".py"):
        return analyze_python_launch(path, rel)
    if path.name.endswith((".xml", ".launch")):
        return analyze_xml_launch(path, rel)
    return {"path": rel, "format": "yaml", "nodes": [], "includes": [], "arguments": [],
            "warnings": ["YAML launch file listed; deep static parsing is not implemented."]}


def _executables(package_root: Path, build_type: str) -> list[str]:
    values: set[str] = set()
    if build_type == "ament_python":
        for setup in (package_root / "setup.py", package_root / "setup.cfg"):
            if not setup.is_file():
                continue
            text = setup.read_text(errors="replace")[:500_000]
            for match in re.finditer(r"(?m)^\s*['\"]([\w.-]+)\s*=\s*[\w.]+:[\w.]+['\"]", text):
                values.add(match.group(1))
    cmake = package_root / "CMakeLists.txt"
    if cmake.is_file():
        text = cmake.read_text(errors="replace")[:500_000]
        values.update(re.findall(r"\badd_executable\s*\(\s*([\w.-]+)", text, re.I))
    return sorted(values)


def parse_package(package_xml: Path, workspace_root: Path) -> dict[str, Any]:
    package_root = package_xml.parent
    base = {"path": _relative(package_root, workspace_root), "metadata_path": _relative(package_xml, workspace_root),
            "warnings": [], "dependencies": [], "files": [], "launch": []}
    try:
        xml_root = ET.parse(package_xml).getroot()
    except (OSError, ET.ParseError) as exc:
        return {**base, "id": base["path"], "name": package_root.name, "version": None, "description": None,
                "maintainers": [], "licenses": [], "build_type": "unknown", "type": "unknown",
                "warnings": [f"Malformed package.xml: {exc}"]}
    name = _text(xml_root.find("name")) or package_root.name
    export = xml_root.find("export")
    build_type = _text(export.find("build_type")) if export is not None else None
    build_type = build_type or ("ament_python" if (package_root / "setup.py").exists() else "ament_cmake" if (package_root / "CMakeLists.txt").exists() else "unknown")
    dependencies = []
    for elem in xml_root:
        tag = elem.tag.rsplit("}", 1)[-1]
        value = _text(elem)
        if tag in DEPENDENCY_TAGS and value:
            dependencies.append({"name": value, "kind": tag, "evidence": base["metadata_path"]})
    files, truncated = _package_files(package_root, workspace_root)
    launch = [analyze_launch(workspace_root / row["path"], workspace_root) for row in files if row["kind"] == "launch"]
    warnings = []
    if truncated:
        warnings.append(f"File list truncated at {MAX_FILES_PER_PACKAGE} entries.")
    if _text(xml_root.find("version")) is None:
        warnings.append("package.xml has no version.")
    if not xml_root.findall("maintainer"):
        warnings.append("package.xml has no maintainer.")
    return {**base, "id": name, "name": name, "version": _text(xml_root.find("version")),
            "description": _text(xml_root.find("description")),
            "maintainers": [_text(x) for x in xml_root.findall("maintainer") if _text(x)],
            "licenses": [_text(x) for x in xml_root.findall("license") if _text(x)],
            "build_type": build_type, "type": build_type, "dependencies": dependencies,
            "files": files, "launch": launch, "executables": _executables(package_root, build_type), "warnings": warnings}


def _cycles(packages: list[dict[str, Any]]) -> list[list[str]]:
    names = {p["name"] for p in packages}
    graph = {p["name"]: {d["name"] for d in p["dependencies"] if d["name"] in names} for p in packages}
    found: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    seen: set[str] = set()
    def visit(name: str):
        if name in visiting:
            cycle = visiting[visiting.index(name):]
            rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))]
            found.add(min(rotations))
            return
        if name in seen:
            return
        visiting.append(name)
        for child in graph[name]:
            visit(child)
        visiting.pop(); seen.add(name)
    for name in graph:
        visit(name)
    return [list(x) for x in sorted(found)]


def scan_workspace(root: Path) -> dict[str, Any]:
    packages = [parse_package(path, root) for path in discover_package_xml(root)]
    names = {p["name"] for p in packages}
    reverse: dict[str, list[str]] = {name: [] for name in names}
    edges, external = [], set()
    for package in packages:
        unique = set()
        for dep in package["dependencies"]:
            key = (package["name"], dep["name"], dep["kind"])
            if key in unique:
                continue
            unique.add(key)
            workspace = dep["name"] in names
            edges.append({"id": hashlib.sha1("\0".join(key).encode()).hexdigest()[:16], "source": package["name"],
                          "target": dep["name"], "kind": dep["kind"], "workspace": workspace,
                          "resolved": workspace, "evidence": dep["evidence"]})
            if workspace:
                reverse[dep["name"]].append(package["name"])
            else:
                external.add(dep["name"])
    for package in packages:
        package["reverse_dependencies"] = sorted(set(reverse[package["name"]]))
    cycles = _cycles(packages)
    build_types = Counter(p["build_type"] for p in packages)
    return {"workspace_id": workspace_id(root), "path": str(root), "name": root.name,
            "packages": packages, "edges": edges, "external_dependencies": sorted(external),
            "summary": {"packages": len(packages), "package_types": dict(build_types), "declared_dependencies": len(edges),
                        "external_dependencies": len(external), "launch_files": sum(len(p["launch"]) for p in packages),
                        "config_files": sum(sum(f["kind"] == "config" for f in p["files"]) for p in packages),
                        "cycles": cycles, "warnings": sum(len(p["warnings"]) + sum(len(x["warnings"]) for x in p["launch"]) for p in packages)},
            "warnings": ([f"Package scan stopped after {MAX_PACKAGES} package manifests."] if len(packages) >= MAX_PACKAGES else [])}


def read_source(root: Path, relative_path: str) -> dict[str, Any]:
    candidate = (root / relative_path).resolve(strict=True)
    if candidate != root and root not in candidate.parents:
        raise PermissionError("File path escapes the workspace")
    if not candidate.is_file() or candidate.is_symlink():
        raise WorkspaceError("File is unavailable")
    size = candidate.stat().st_size
    if size > MAX_FILE_BYTES:
        raise WorkspaceError(f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB viewer limit")
    data = candidate.read_bytes()
    if b"\0" in data:
        raise WorkspaceError("Binary files cannot be opened in the source viewer")
    text = data.decode("utf-8", errors="replace")
    language = {".py": "python", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".h": "cpp",
                ".xml": "xml", ".xacro": "xml", ".urdf": "xml", ".yaml": "yaml", ".yml": "yaml",
                ".json": "json", ".cmake": "cmake"}.get(candidate.suffix.lower(), "text")
    if candidate.name == "CMakeLists.txt": language = "cmake"
    return {"path": relative_path, "language": language, "size": size, "content": text}
