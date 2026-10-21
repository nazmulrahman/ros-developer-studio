import sqlite3
from unittest.mock import Mock
from pathlib import Path

from fastapi.testclient import TestClient

from backend.bags.studio import BagError, BagLibrary, Recorder
from backend.core import auth
from backend.core.state import state
from backend.main import create_app


def make_bag(root: Path):
    bag = root / "run_01"; bag.mkdir(parents=True)
    db = bag / "run_01_0.db3"
    with sqlite3.connect(db) as conn:
        conn.executescript("CREATE TABLE topics(id INTEGER PRIMARY KEY,name TEXT,type TEXT,serialization_format TEXT,offered_qos_profiles TEXT); CREATE TABLE messages(id INTEGER PRIMARY KEY,topic_id INTEGER,timestamp INTEGER,data BLOB);")
        conn.execute("INSERT INTO topics VALUES(1,'/speed','std_msgs/msg/Float64','cdr','')")
        for i, stamp in enumerate((1_000_000_000, 1_100_000_000, 3_500_000_000), 1):
            conn.execute("INSERT INTO messages VALUES(?,?,?,?)", (i, 1, stamp, b"raw" + bytes([i])))
    return bag


def test_sqlite_bag_metadata_messages_analysis_and_export(tmp_path):
    bag = make_bag(tmp_path); library = BagLibrary([str(tmp_path)])
    listed = library.list(); assert len(listed) == 1
    meta = library.summary(bag); assert meta["storage"] == "sqlite3" and meta["message_count"] == 3
    assert meta["topics"] == [{"name": "/speed", "type": "std_msgs/msg/Float64", "count": 3}]
    rows = library.messages(meta["bag_id"], "/speed", 1_050_000_000, None, 10)
    assert [x["record_ns"] for x in rows] == ["1100000000", "3500000000"] and rows[0]["size"] == 4
    analysis = library.analysis(meta["bag_id"])["topics"][0]
    assert analysis["max_gap_ns"] == 2_400_000_000 and analysis["gap_count"] == 1
    findings = library.findings(meta["bag_id"])
    assert any(x["severity"] == "warning" and "gap" in x["evidence"] for x in findings)
    assert any("could not be decoded" in x["evidence"] for x in findings)
    assert "record_ns,topic,type,size_bytes" in library.export_csv(meta["bag_id"], "/speed", None, None)
    try: library.summary(tmp_path.parent)
    except BagError: pass
    else: raise AssertionError("path outside configured bag root was accepted")


def test_bag_api_is_authenticated_and_bounded(tmp_path):
    bag = make_bag(tmp_path); old_dirs, old_record = state.settings.bag_dirs, state.settings.record_dir
    state.settings.bag_dirs, state.settings.record_dir = [str(tmp_path)], str(tmp_path)
    auth.set_token("bag-token"); headers = {"Authorization": "Bearer bag-token"}
    try:
        with TestClient(create_app()) as client:
            assert client.get("/api/bags").status_code == 401
            rows = client.get("/api/bags", headers=headers).json(); assert len(rows) == 1
            opened = client.post("/api/bags/open", headers=headers, json={"path": str(bag)}).json(); bag_id = opened["bag_id"]
            assert client.get(f"/api/bags/{bag_id}/topics", headers=headers).json()[0]["count"] == 3
            assert len(client.get(f"/api/bags/{bag_id}/messages", headers=headers, params={"topic": "/speed", "limit": 2}).json()) == 2
            assert client.get(f"/api/bags/{bag_id}/analysis", headers=headers).status_code == 200
            assert client.get(f"/api/bags/{bag_id}/findings", headers=headers).status_code == 200
            exported = client.post(f"/api/bags/{bag_id}/export", headers=headers, json={"topic": "/speed"})
            assert exported.status_code == 200 and exported.headers["content-type"].startswith("text/csv")
            assert client.get("/api/record/status", headers=headers).json()["recording"] is False
    finally:
        state.settings.bag_dirs, state.settings.record_dir = old_dirs, old_record


def test_recorder_validates_and_starts_without_a_shell(tmp_path, monkeypatch):
    try: Recorder(str(tmp_path)).start("bad", ["../../unsafe"], False)
    except BagError: pass
    else: raise AssertionError("invalid topic accepted")
    process = Mock(pid=4242); process.poll.return_value = None
    launch = Mock(return_value=process); monkeypatch.setattr("backend.bags.studio.subprocess.Popen", launch)
    recorder = Recorder(str(tmp_path)); status = recorder.start("demo run", ["/camera/image"], False)
    assert status["recording"] is True and status["path"].endswith("demo-run")
    command = launch.call_args.args[0]
    assert command == ["ros2", "bag", "record", "-o", str(tmp_path / "demo-run"), "/camera/image"]
    assert launch.call_args.kwargs["start_new_session"] is True
