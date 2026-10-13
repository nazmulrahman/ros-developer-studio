import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core import auth
from backend.core.state import state
from backend.main import create_app
from backend.package_explorer.analyzer import WorkspaceError, read_source, resolve_allowed, scan_workspace
import backend.api.package_explorer as package_api
import backend.core.workspace_roots as workspace_roots


def package(root: Path, name: str, *, build="ament_cmake", dependencies=(), nested="src", malformed=False):
    folder = root / nested / name
    folder.mkdir(parents=True)
    if malformed:
        (folder / "package.xml").write_text("<package><name>broken")
    else:
        deps = "".join(f"<depend>{d}</depend>" for d in dependencies)
        (folder / "package.xml").write_text(
            f'<package format="3"><name>{name}</name><version>1.2.3</version><description>{name} package</description>'
            f'<maintainer email="dev@example.test">Developer</maintainer><license>Apache-2.0</license>{deps}'
            f'<export><build_type>{build}</build_type></export></package>'
        )
    if build == "ament_cmake":
        (folder / "CMakeLists.txt").write_text(f"add_executable({name}_node src/main.cpp)\n")
        (folder / "src").mkdir(); (folder / "src" / "main.cpp").write_text("int main() { return 0; }\n")
    else:
        (folder / "setup.py").write_text(f"entry_points={{'console_scripts': ['{name}_node = {name}.main:main']}}\n")
    return folder


def test_empty_and_nested_mixed_workspace(tmp_path):
    empty = scan_workspace(tmp_path)
    assert empty["summary"]["packages"] == 0 and empty["edges"] == []
    package(tmp_path, "driver", build="ament_cmake", dependencies=["rclcpp", "common"], nested="deep/src")
    package(tmp_path, "common", build="ament_python", dependencies=["rclpy"], nested="modules")
    result = scan_workspace(tmp_path)
    assert {p["name"] for p in result["packages"]} == {"driver", "common"}
    assert result["summary"]["package_types"] == {"ament_cmake": 1, "ament_python": 1}
    driver = next(p for p in result["packages"] if p["name"] == "driver")
    assert driver["executables"] == ["driver_node"]
    assert driver["reverse_dependencies"] == []
    assert next(p for p in result["packages"] if p["name"] == "common")["reverse_dependencies"] == ["driver"]
    external = next(e for e in result["edges"] if e["target"] == "rclcpp")
    assert external["workspace"] is False and external["evidence"].endswith("package.xml")


def test_cycles_missing_dependencies_and_malformed_metadata(tmp_path):
    package(tmp_path, "a", dependencies=["b", "not_in_workspace"])
    package(tmp_path, "b", dependencies=["a"])
    package(tmp_path, "broken", malformed=True)
    result = scan_workspace(tmp_path)
    assert result["summary"]["cycles"] == [["a", "b"]]
    assert "not_in_workspace" in result["external_dependencies"]
    broken = next(p for p in result["packages"] if p["name"] == "broken")
    assert "Malformed package.xml" in broken["warnings"][0]


def test_launch_static_analysis_never_executes_python(tmp_path):
    folder = package(tmp_path, "bringup")
    launch = folder / "launch"; launch.mkdir()
    (launch / "system.launch.py").write_text('''
from launch_ros.actions import Node
raise RuntimeError("must never execute")
def generate_launch_description():
    return [Node(package="demo_nodes_cpp", executable="talker", name="speaker"),
            Node(package=get_package(), executable="dynamic"),
            DeclareLaunchArgument("mode", default_value="safe")]
''')
    (launch / "extra.launch.xml").write_text('<launch><node pkg="demo" exec="listener" name="listener"/><include file="$(find-pkg-share demo)/x.launch.xml"/></launch>')
    result = scan_workspace(tmp_path)
    analyses = next(p for p in result["packages"] if p["name"] == "bringup")["launch"]
    py = next(x for x in analyses if x["format"] == "python")
    assert py["nodes"][0]["name"] == "speaker" and py["nodes"][1]["dynamic"] is True
    assert "not executed" in py["warnings"][0]
    xml = next(x for x in analyses if x["format"] == "xml")
    assert xml["nodes"][0]["executable"] == "listener" and xml["includes"][0]["dynamic"] is True


def test_source_read_limits_and_workspace_escape(tmp_path):
    root = tmp_path / "ws"; root.mkdir(); outside = tmp_path / "secret.txt"; outside.write_text("secret")
    source = root / "src.py"; source.write_text("print('safe')\n")
    assert read_source(root, "src.py")["language"] == "python"
    with pytest.raises(PermissionError): read_source(root, "../secret.txt")
    binary = root / "blob.bin"; binary.write_bytes(b"x\0y")
    with pytest.raises(WorkspaceError): read_source(root, "blob.bin")
    link = root / "link.py"; link.symlink_to(outside)
    with pytest.raises(PermissionError): read_source(root, "link.py")
    with pytest.raises(PermissionError): resolve_allowed(str(tmp_path), [str(root)])


def test_rescan_has_stable_workspace_and_edge_ids(tmp_path):
    package(tmp_path, "a", dependencies=["b"]); package(tmp_path, "b")
    first, second = scan_workspace(tmp_path), scan_workspace(tmp_path)
    assert first["workspace_id"] == second["workspace_id"]
    assert [e["id"] for e in first["edges"]] == [e["id"] for e in second["edges"]]


def test_authenticated_scan_source_and_layout_api(tmp_path, monkeypatch):
    package(tmp_path, "one")
    monkeypatch.setenv("STUDIO_PACKAGE_LAYOUTS", str(tmp_path / ".layouts"))
    old = state.settings.workspace_roots
    state.settings.workspace_roots = [str(tmp_path)]
    auth.set_token("package-token")
    try:
        with TestClient(create_app()) as client:
            headers = {"Authorization": "Bearer package-token"}
            assert client.post("/api/package-explorer/scan", json={"path": str(tmp_path)}).status_code == 401
            scan = client.post("/api/package-explorer/scan", headers=headers, json={"path": str(tmp_path)}).json()
            assert scan["summary"]["packages"] == 1
            source = client.get("/api/package-explorer/file", headers=headers, params={"workspace": str(tmp_path), "path": "src/one/package.xml"})
            assert source.status_code == 200 and "<name>one</name>" in source.json()["content"]
            wid = scan["workspace_id"]
            layout = {"workspace_id": wid, "mode": "architecture", "viewport": {"x": 1, "y": 2, "zoom": 0.8},
                      "positions": {"one": {"x": 22, "y": 33}}, "groups": [{"id": "g", "name": "Core", "members": ["one"], "collapsed": False}]}
            assert client.put(f"/api/package-explorer/layouts/{wid}", headers=headers, json=layout).status_code == 200
            assert client.get(f"/api/package-explorer/layouts/{wid}", headers=headers).json()["positions"]["one"]["x"] == 22
            assert client.put(f"/api/package-explorer/layouts/{'0' * 24}", headers=headers, json=layout).status_code == 422
    finally:
        state.settings.workspace_roots = old


def test_folder_browser_adds_and_persists_workspace_root(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    workspace = home / "robot_ws"; package(workspace, "robot")
    saved = tmp_path / "workspace_roots.json"
    monkeypatch.setenv("STUDIO_WORKSPACE_ROOTS_FILE", str(saved))
    monkeypatch.setattr(workspace_roots, "browse_locations", lambda: [home])
    monkeypatch.setattr(package_api, "browse_locations", lambda: [home])
    old = state.settings.workspace_roots
    state.settings.workspace_roots = []
    auth.set_token("folder-token")
    try:
        headers = {"Authorization": "Bearer folder-token"}
        with TestClient(create_app()) as client:
            listing = client.get("/api/package-explorer/browse", headers=headers, params={"path": str(home)})
            assert listing.status_code == 200
            assert listing.json()["directories"][0]["path"] == str(workspace)
            added = client.post("/api/package-explorer/roots", headers=headers, json={"path": str(workspace)})
            assert added.status_code == 200 and added.json()["packages"] == 1
            assert client.get("/api/package-explorer/roots", headers=headers).json() == [{"path": str(workspace), "available": True}]
        with TestClient(create_app()) as restarted:
            assert restarted.get("/api/package-explorer/roots", headers=headers).json()[0]["path"] == str(workspace)
        assert json.loads(saved.read_text()) == [str(workspace)]
    finally:
        state.settings.workspace_roots = old
