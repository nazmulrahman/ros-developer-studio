import asyncio
import base64
import io
import json
import threading
import time
import pytest
from agent.subscriptions.visual import preview, stamp
from agent.subscriptions.monitor import Monitor, Watch
from backend.core.preferences import PreferenceStore, Preferences, Layout
from backend.core.tf_tree import TfTree
from fastapi import HTTPException


def test_raw_camera_bgr_with_row_padding():
    from PIL import Image
    msg = {"width": 2, "height": 1, "step": 8, "encoding": "bgr8", "data": bytes([0, 0, 255, 0, 0, 255, 0, 0])}
    v = preview(msg, "sensor_msgs/msg/Image")
    assert v["kind"] == "image" and v["original"] == [2, 1]
    im = Image.open(io.BytesIO(base64.b64decode(v["base64"])))
    r, g, b = im.getpixel((0, 0))
    assert r > 240 and g < 15 and b < 15


def test_camera_limits_and_unsupported_encodings():
    from PIL import Image
    data = io.BytesIO(); Image.new("RGB", (1920, 1080)).save(data, format="PNG")
    v = preview({"data": data.getvalue()}, "sensor_msgs/msg/CompressedImage")
    assert v["width"] <= 640 and v["height"] <= 480
    assert "error" in preview({"data": b"not an image"}, "sensor_msgs/msg/CompressedImage")
    assert "Unsupported raw encoding" in preview({"encoding": "16UC1", "data": b""}, "sensor_msgs/msg/Image")["error"]
    assert "Invalid image" in preview({"encoding": "rgb8", "width": 3, "height": 2, "step": 9, "data": b"x"}, "sensor_msgs/msg/Image")["error"]


def test_lidar_decimation_and_invalid_range_filter():
    v = preview({"ranges": [1.0] * 10000, "range_min": 0.1, "range_max": 10, "angle_increment": 0.01}, "sensor_msgs/msg/LaserScan")
    assert len(v["points"]) <= 2048 and v["total"] == 10000
    v = preview({"ranges": [float("nan"), float("inf"), -1, 0, 1, 20], "range_min": 0.1, "range_max": 10}, "sensor_msgs/msg/LaserScan")
    assert v["points"] == [[1.0, 0.0]]
    json.dumps(v, allow_nan=False)
    assert "error" in preview({"ranges": [1.0], "range_max": 10, "angle_min": float("nan")}, "sensor_msgs/msg/LaserScan")


def test_stamps_preserve_header_time_and_missing_values():
    assert stamp({"header": {"stamp": {"sec": 123, "nanosec": 987}}}) == 123000000987
    assert stamp({}) is None


def test_slow_preview_does_not_block_statistics_or_queue_more_work():
    async def check():
        mon = Monitor("/image", 5, asyncio.get_running_loop()); mon.types = ["sensor_msgs/msg/Imu"]
        received = []
        # SimpleNamespace is not hashable; a tiny session stands in for the server.
        class Client:
            def push(self, ev): received.append(ev)
        client = Client(); mon.set_watch(client, Watch(visual=True))
        entered, release = threading.Event(), threading.Event()
        def slow(): entered.set(); release.wait(2); return {"header": {"stamp": {"sec": 1, "nanosec": 9}}}
        mon.on_message(10, 123, slow)
        assert entered.wait(1)
        for i in range(500): mon.on_message(11 + i, 123, slow)
        assert mon.stats.count == 501
        release.set()
        for _ in range(100):
            if received: break
            await asyncio.sleep(0.01)
        assert len(received) == 1
        assert received[0]["stamps"]["header_ns"] == "1000000009"
        assert received[0]["stamps"]["record_ns"] is None
    asyncio.run(check())


def test_preferences_survive_restart_and_reject_unknown_controls(tmp_path):
    path = tmp_path / "prefs.json"; store = PreferenceStore(path)
    entry = store.save_layout(Layout(name="Bench", config={"motion": []}))
    assert PreferenceStore(path).read()["layouts"][0] == entry
    store.save_layout(Layout(name="Changed", config={"visualizations": []}), entry["id"])
    assert store.read()["layouts"][0]["name"] == "Changed"
    with pytest.raises(HTTPException): store.save_layout(Layout(name="Bad", config={"token": "secret"}))
    with pytest.raises(ValueError): Preferences(preview_hz=100)
    with pytest.raises(ValueError): Preferences(test_tools_allowed=True)


def test_corrupt_preferences_are_not_overwritten(tmp_path):
    path = tmp_path / "prefs.json"; path.write_text("broken")
    with pytest.raises(HTTPException): PreferenceStore(path).save_layout(Layout(name="New", config={}))
    assert path.read_text() == "broken"


def test_visual_stream_is_opt_in_and_shared_with_numeric_fields(stack):
    stack.ros.add_topic("/motion")
    visual, numeric = stack.ws(), stack.ws()
    visual.send(op="watch", topic="/motion", hz=2, visual=True)
    numeric.send(op="watch", topic="/motion", hz=10, fields=["linear.x"])
    time.sleep(0.5)
    stack.ros.publish("/motion", {"linear": {"x": 1.5}, "angular": {"z": 0.2}})
    ev = visual.wait(lambda x: x["ch"] == "sample")
    assert ev["visual"]["data"]["linear"]["x"] == 1.5
    assert ev["type"] == "geometry_msgs/msg/Twist" and ev["source_mode"] == "live"
    n = numeric.wait(lambda x: x["ch"] == "sample")
    assert n["values"]["linear.x"] == 1.5 and "visual" not in n
    assert len(stack.ros.callbacks["/motion"]) == 1
    visual.close(); numeric.close()


def test_layout_and_preferences_api_are_authenticated_and_persisted(tmp_path, monkeypatch):
    from backend.main import create_app
    from backend.core import auth
    from fastapi.testclient import TestClient
    monkeypatch.setenv("STUDIO_PREFERENCES", str(tmp_path / "preferences.json"))
    auth.set_token("test-preferences")
    headers = {"Authorization": "Bearer test-preferences"}
    with TestClient(create_app()) as client:
        assert client.get("/api/layouts").status_code == 401
        assert client.put("/api/settings", headers=headers, json={"preview_hz": 99}).status_code == 422
        assert client.put("/api/settings", headers=headers, json={"test_tools_allowed": True}).status_code == 422
        assert client.put("/api/settings", headers=headers, json={"preview_hz": 3}).status_code == 200
        item = client.post("/api/layouts", headers=headers, json={"name": "Bench", "config": {"motion": []}}).json()
        assert client.get("/api/settings", headers=headers).json()["preferences"]["preview_hz"] == 3
        assert client.get("/api/layouts", headers=headers).json()[0]["id"] == item["id"]
        assert client.delete("/api/layouts/" + item["id"], headers=headers).status_code == 200
        assert client.get("/api/layouts", headers=headers).json() == []
        assert client.delete("/api/layouts/" + item["id"], headers=headers).status_code == 404


def test_tf_tree_merges_topics_and_reports_structural_problems():
    tree = TfTree()
    def event(topic, rows, received="10000000000"):
        return {"topic": topic, "t_ns": int(received), "stamps": {"receive_ns": received},
                "visual": {"data": {"transforms": rows}}}
    def transform(parent, child, quaternion=None):
        return {"header": {"frame_id": parent, "stamp": {"sec": 9, "nanosec": 0}}, "child_frame_id": child,
                "transform": {"translation": {"x": 1.0, "y": 0.0, "z": 0.0},
                              "rotation": quaternion or {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}}
    assert tree.ingest(event("/tf_static", [transform("map", "odom")]))
    tree.ingest(event("/tf", [transform("odom", "base"), transform("other", "base")], "14000000000"))
    tree.ingest(event("/tf", [transform("island", "sensor", {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0})]))
    snapshot = tree.snapshot(now_ns=15_000_000_000, stale_after_s=3)
    assert snapshot["frames"] == ["base", "island", "map", "odom", "other", "sensor"]
    assert snapshot["roots"] == ["island", "map", "other"]
    assert next(edge for edge in snapshot["edges"] if edge["child"] == "odom")["static"] is True
    codes = {finding["code"] for finding in snapshot["diagnostics"]}
    assert {"multiple_parents", "disconnected", "rotation", "stale"} <= codes


def test_tf_tree_detects_cycles_and_bounds_edges():
    tree = TfTree(limit=2)
    rows = []
    for parent, child in (("a", "b"), ("b", "a"), ("x", "y")):
        rows.append({"header": {"frame_id": parent}, "child_frame_id": child,
                     "transform": {"rotation": {"x": 0, "y": 0, "z": 0, "w": 1}}})
    tree.ingest({"topic": "/tf", "t_ns": 1, "visual": {"data": {"transforms": rows}}})
    assert len(tree.snapshot(now_ns=1)["edges"]) == 2
    full = TfTree(); full.ingest({"topic": "/tf", "t_ns": 1, "visual": {"data": {"transforms": rows[:2]}}})
    assert any(finding["code"] == "cycle" for finding in full.snapshot(now_ns=1)["diagnostics"])
def test_parameter_failures_do_not_mutate_ros(stack):
    stack.ros.parameters = lambda name: {"node": name, "parameters": [{"name": "speed", "type": 3, "value": 1.2}], "truncated": False}
    result = stack.http.get("/api/live/parameters", params={"name": "/ns/node"})
    assert result.status_code == 200 and result.json()["node"] == "/ns/node"
    def timeout(_): raise TimeoutError("node unavailable")
    stack.ros.parameters = timeout
    assert stack.http.get("/api/live/parameters", params={"name": "/ns/node"}).status_code == 504
    assert stack.http.get("/api/live/parameters", params={"name": "invalid"}).status_code == 422


def test_late_tf_viewer_receives_cached_sample_without_new_publish():
    from backend.core.hub import LiveHub, Client
    from backend.core.config import Settings
    async def check():
        hub = LiveHub(Settings())
        first, second = Client(None), Client(None)
        hub.clients.update([first, second])
        await hub.watch(first, "/frames", 2, False, [], True)
        sample = {"ch": "sample", "topic": "/frames", "type": "tf2_msgs/msg/TFMessage", "t_ns": 123, "size": 45,
                  "source_mode": "live", "stamps": {"receive_ns": "123"}, "visual": {"kind": "message", "data": {"transforms": []}}}
        await hub._on_event(sample)
        await hub.watch(second, "/frames", 2, False, [], True)
        assert (await second.q.get())["stamps"]["receive_ns"] == "123"
        await hub.unwatch(first, "/frames"); await hub.unwatch(second, "/frames")
        assert hub.tf_previews == {}
    asyncio.run(check())
