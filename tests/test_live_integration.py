"""Real agent server + real backend + real WebSockets, with FakeRos behind the RosBackend interface.
This does NOT verify rclpy integration (no ROS in the build environment)."""
import time
from .conftest import Stack
from .fakes import AgentThread, FakeRos


def test_status_when_agent_not_running(stack_no_agent):
    s = stack_no_agent.http.get("/api/live/status").json()
    assert s["agent"]["state"] in ("connecting", "disconnected") and s["ros"] is None
    r = stack_no_agent.http.get("/api/live/graph")
    assert r.status_code == 503 and r.json()["detail"]["error"] == "agent_unavailable"

def test_empty_graph_is_not_a_disconnected_agent(stack):
    s = stack.http.get("/api/live/status").json()
    assert s["agent"]["state"] == "connected" and s["ros"]["available"] is True
    assert s["ros"]["distro"] == "fake" and s["ros"]["domain_id"] == "7" and s["ros"]["discovery"] == "active"
    g = stack.http.get("/api/live/graph").json()
    assert g["nodes"] == [] and g["topics"] == []
    assert stack.http.get("/api/session").json()["agent_connected"] is True

def test_graph_topic_node_details(stack):
    stack.ros.nodes = [("talker", "/"), ("listener", "/ns")]
    stack.ros.add_topic("/cmd_vel", pubs=("teleop",), subs=("base", "logger"))
    stack.ros.add_topic("/orphan", pubs=(), subs=("x",))
    g = stack.http.get("/api/live/graph").json()
    assert [n["full"] for n in g["nodes"]] == ["/talker", "/ns/listener"]
    t = {x["name"]: x for x in g["topics"]}
    assert t["/cmd_vel"]["publishers"] == 1 and t["/cmd_vel"]["subscribers"] == 2 and t["/orphan"]["publishers"] == 0
    assert g["services"][0]["name"] == "/reset" and g["actions"][0]["name"] == "/navigate"
    info = stack.http.get("/api/live/topic", params={"name": "/cmd_vel"}).json()
    assert info["types"] == ["geometry_msgs/msg/Twist"] and info["publishers"][0]["qos"]["reliability"] == "RELIABLE"
    assert "linear.x" in [f["path"] for f in info["fields"]] and info["fields_error"] is None
    assert stack.http.get("/api/live/topic", params={"name": "/nope"}).status_code == 404
    assert stack.http.get("/api/live/node", params={"name": "/talker"}).status_code == 200

def test_unsupported_message_type_still_inspectable(stack):
    stack.ros.add_topic("/custom", type_="my_pkg/msg/Weird")
    info = stack.http.get("/api/live/topic", params={"name": "/custom"}).json()
    assert info["fields"] == [] and "not available" in info["fields_error"]
    b = stack.ws(); b.send(op="watch", topic="/custom", hz=5, payload=True)
    e = b.wait(lambda e: e["ch"] == "watch_error")
    assert e["code"] == "unsupported_type"; b.close()

def test_qos_conflict_reported(stack):
    stack.ros.topics["/x"] = {"types": ["geometry_msgs/msg/Twist"], "pubs": [__import__("tests.fakes", fromlist=["ep"]).ep("p", "BEST_EFFORT")],
                              "subs": [__import__("tests.fakes", fromlist=["ep"]).ep("s", "RELIABLE")]}
    info = stack.http.get("/api/live/topic", params={"name": "/x"}).json()
    assert info["qos_conflicts"][0]["subscriber"] == "s"

def test_live_stream_values_payload_and_throttle(stack):
    stack.ros.add_topic("/cmd_vel")
    b = stack.ws(); b.send(op="watch", topic="/cmd_vel", hz=5, payload=True, fields=["linear.x", "angular.z"])
    b.wait(lambda e: e["ch"] == "status"); time.sleep(0.3)
    for i in range(300):
        stack.ros.publish("/cmd_vel", {"linear": {"x": i, "y": 0, "z": 0}, "angular": {"x": 0, "y": 0, "z": 0.5}}); time.sleep(0.003)
    evs = b.drain(0.5)
    samples = [e for e in b.seen + evs if e["ch"] == "sample"]
    assert 1 <= len(samples) <= 15, len(samples)           # ~1 s of publishing at 5 Hz cap, not 300
    assert samples[-1]["values"]["angular.z"] == 0.5 and samples[-1]["payload"]["linear"]["y"] == 0
    st = b.wait(lambda e: e["ch"] == "stats", timeout=3)
    assert st["status"] in ("receiving", "stalled") and st["stats"]["count"] == 300 and st["publishers"] == 1
    b.close()

def test_unsubscribe_on_unwatch_and_client_close(stack):
    stack.ros.add_topic("/a"); stack.ros.add_topic("/b")
    b = stack.ws(); b.send(op="watch", topic="/a", hz=2, payload=True); b.send(op="watch", topic="/b", hz=2, payload=True)
    time.sleep(0.5); assert len(stack.ros.callbacks["/a"]) == 1 and len(stack.ros.callbacks["/b"]) == 1
    b.send(op="unwatch", topic="/a"); time.sleep(0.4); assert stack.ros.callbacks["/a"] == []
    b.close(); time.sleep(0.6); assert stack.ros.callbacks["/b"] == []   # viewer closed -> ROS subscription destroyed

def test_two_viewers_share_one_ros_subscription(stack):
    stack.ros.add_topic("/a")
    b1, b2 = stack.ws(), stack.ws()
    b1.send(op="watch", topic="/a", hz=2, payload=True); b2.send(op="watch", topic="/a", hz=20, fields=["linear.x"])
    time.sleep(0.6); assert len(stack.ros.callbacks["/a"]) == 1
    b1.close(); time.sleep(0.6); assert len(stack.ros.callbacks["/a"]) == 1   # still needed by b2
    b2.close(); time.sleep(0.6); assert stack.ros.callbacks["/a"] == []

def test_no_publisher_vs_no_data_vs_receiving(stack):
    stack.ros.add_topic("/nopub", pubs=()); stack.ros.add_topic("/silent", pubs=("p",)); stack.ros.add_topic("/live", pubs=("p",))
    b = stack.ws()
    for t in ("/nopub", "/silent", "/live"): b.send(op="watch", topic=t, hz=2, payload=True)
    time.sleep(0.3)
    for _ in range(20): stack.ros.publish("/live", {}); time.sleep(0.02)
    got = {}
    end = time.time() + 4
    while len(got) < 3 and time.time() < end:
        try: e = b.wait(lambda e: e["ch"] == "stats", timeout=1.5); got[e["topic"]] = e["status"]
        except AssertionError: pass
    assert got == {"/nopub": "no_publisher", "/silent": "publisher_no_data", "/live": "receiving"}, got
    b.close()

def test_topic_disappearing(stack):
    stack.ros.add_topic("/gone")
    b = stack.ws(); b.send(op="watch", topic="/gone", hz=2, payload=True); time.sleep(0.4)
    del stack.ros.topics["/gone"]
    assert b.wait(lambda e: e["ch"] == "graph", timeout=3)               # graph change pushed, no polling by the browser
    assert b.wait(lambda e: e["ch"] == "stats" and e["topic"] == "/gone", timeout=3)["status"] == "topic_missing"
    b.close()

def test_high_frequency_topic(stack):
    stack.ros.add_topic("/fast")
    b = stack.ws(); b.send(op="watch", topic="/fast", hz=10, payload=True, fields=["linear.x"]); time.sleep(0.4)
    t0 = time.time()
    for i in range(20000): stack.ros.publish("/fast", {"linear": {"x": i}}, size=1000)
    took = time.time() - t0
    st = b.wait(lambda e: e["ch"] == "stats", timeout=3)
    assert st["stats"]["count"] == 20000 and st["stats"]["hz"] > 1000
    samples = [e for e in b.seen + b.drain(0.3) if e["ch"] == "sample"]
    assert len(samples) < 50                                              # browser traffic bounded regardless of source rate
    assert took < 5, f"publish path too slow: {took:.2f}s"
    b.close()

def test_discovery_error_is_reported_without_dropping_agent(stack):
    b = stack.ws(); stack.ros.fail_signature = "rmw error"
    e = b.wait(lambda e: e["ch"] == "status" and (e.get("ros") or {}).get("discovery") == "error", timeout=4)
    assert "rmw error" in e["ros"]["discovery_error"] and e["agent"]["state"] == "connected"
    b.close()

def test_agent_restart_resubscribes_and_reports_disconnect():
    ros = FakeRos(); ros.add_topic("/t"); agent = AgentThread(ros).start()
    s = Stack.__new__(Stack); s.ros, s.agent = ros, agent
    from .fakes import BackendThread; import httpx
    s.backend = BackendThread(f"ws://127.0.0.1:{agent.port}")
    s.http = httpx.Client(base_url=s.backend.url, headers={"Authorization": "Bearer tok"}, timeout=5)
    try:
        s.wait_agent(); b = s.ws(); b.send(op="watch", topic="/t", hz=20, payload=True); time.sleep(0.5)
        agent.stop()
        s.wait_agent("disconnected")
        assert b.wait(lambda e: e["ch"] == "status" and e["agent"]["state"] != "connected", timeout=3)
        ros.callbacks = {}                                              # new agent process starts with no subscriptions
        s.agent = AgentThread(ros, port=agent.port).start(); s.wait_agent()
        time.sleep(0.5); assert len(ros.callbacks["/t"]) == 1           # watch restored automatically
        ros.publish("/t", {"v": 1}); assert b.wait(lambda e: e["ch"] == "sample", timeout=3)["payload"] == {"v": 1}
        b.close()
    finally:
        s.close()

def test_host_metrics_stream_and_rest(stack):
    m = stack.http.get("/api/host/metrics").json()
    assert m["host"]["name"] and m["memory"]["total"] > 0 and m["gpu"] is None
    b = stack.ws(); b.send(op="host", interval_s=0.5)
    e = b.wait(lambda e: e["ch"] == "host", timeout=3); assert len(e["cpu"]["per_core"]) >= 1
    b.send(op="host", interval_s=None); b.close()

def test_app_diagnostics_and_auth(stack):
    d = stack.http.get("/api/app/diagnostics").json()
    assert d["backend"]["rss_bytes"] > 0 and d["agent"]["rss_bytes"] > 0
    import httpx
    assert httpx.get(stack.backend.url + "/api/live/status").status_code == 401
    from websockets.sync.client import connect
    try:
        with connect(f"ws://127.0.0.1:{stack.backend.port}/ws/live?token=bad") as w: w.recv(timeout=2); raise AssertionError("accepted bad token")
    except Exception as e: assert "AssertionError" not in type(e).__name__
