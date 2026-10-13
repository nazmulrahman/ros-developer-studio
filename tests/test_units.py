import math, time
from agent.host_metrics.collector import HostCollector, _nvidia_smi
from agent.ros_graph.qos import qos_conflicts
from agent.subscriptions.fields import describe, get_path, numeric_fields
from agent.subscriptions.stats import TopicStats, classify
from .fakes import CLASSES


def feed(st, n, hz, size=100, t0=1000.0):
    for i in range(n): st.record(t0 + i / hz, size)
    return t0 + (n - 1) / hz

def test_stats_rate_period_bandwidth():
    st = TopicStats(window_s=5); end = feed(st, 31, 10.0)
    s = st.snapshot(now=end)
    assert abs(s["hz"] - 10) < 0.01 and abs(s["period_ms"] - 100) < 0.5
    assert abs(s["bandwidth_bps"] - 100 * 8 * 10) < 5 and s["count"] == 31 and s["last_size_bytes"] == 100

def test_stats_no_messages_has_no_rate():
    s = TopicStats().snapshot()
    assert s["hz"] is None and s["count"] == 0 and s["since_last_s"] is None

def test_stats_window_trims_old_samples():
    st = TopicStats(window_s=2); end = feed(st, 100, 10.0)
    assert st.snapshot(now=end)["samples_in_window"] <= 21
    assert st.snapshot(now=end + 10)["hz"] is None  # everything aged out
    assert st.snapshot(now=end + 10)["count"] == 100

def test_stats_bounded_memory():
    st = TopicStats(window_s=1e9, max_samples=500); feed(st, 5000, 1000.0)
    assert len(st._t) == 500

def test_classify_never_healthy_just_because_exists():
    snap0 = TopicStats().snapshot()
    assert classify(False, 0, snap0)[0] == "topic_missing"
    assert classify(True, 0, snap0)[0] == "no_publisher"
    assert classify(True, 1, snap0)[0] == "publisher_no_data"
    st = TopicStats(); end = feed(st, 20, 10.0)
    assert classify(True, 1, st.snapshot(now=end))[0] == "receiving"
    assert classify(True, 1, st.snapshot(now=end + 4))[0] == "stalled"

def test_numeric_fields_nested_fixed_and_sequences():
    f = {x["path"]: x for x in numeric_fields(lambda t: CLASSES[t], "geometry_msgs/msg/Twist")}
    assert set(f) == {f"{a}.{b}" for a in ("linear", "angular") for b in "xyz"}
    g = {x["path"]: x for x in numeric_fields(lambda t: CLASSES[t], "sensor_msgs/msg/LaserScan")}
    assert "frame_id" not in g and "angle_min" in g and "cov[3]" in g
    assert g["ranges[]"]["needs_index"] is True

def test_get_path_variants():
    m = {"a": {"b": [1, 2.5, {"c": True}]}, "n": float("nan"), "s": "x"}
    assert get_path(m, "a.b[1]") == 2.5 and get_path(m, "a.b[2].c") == 1.0
    assert get_path(m, "n") is None and get_path(m, "s") is None
    assert get_path(m, "a.b[9]") is None and get_path(m, "zzz") is None

def test_describe_truncates_and_is_json_safe():
    import json
    d = describe({"big": list(range(1000)), "blob": b"x" * 10_000, "f": float("inf"), "n": float("nan")})
    assert d["big"]["__truncated__"] == 1000 and len(d["big"]["items"]) == 64
    assert d["blob"] == {"__bytes__": 10000} and d["f"] == "Infinity" and d["n"] == "NaN"
    json.dumps(d, allow_nan=False)

def test_qos_conflicts():
    pubs = [{"node": "p", "qos": {"reliability": "BEST_EFFORT", "durability": "VOLATILE"}}]
    subs = [{"node": "s1", "qos": {"reliability": "RELIABLE", "durability": "VOLATILE"}},
            {"node": "s2", "qos": {"reliability": "BEST_EFFORT", "durability": "TRANSIENT_LOCAL"}},
            {"node": "s3", "qos": {"reliability": "BEST_EFFORT", "durability": "VOLATILE"}}]
    c = qos_conflicts(pubs, subs)
    assert [x["subscriber"] for x in c] == ["s1", "s2"]

def test_host_sample_real_measurements():
    h = HostCollector(gpu_probes=[]); time.sleep(0.2); s = h.sample()
    assert s["host"]["name"] and len(s["cpu"]["per_core"]) >= 1 and 0 <= s["memory"]["percent"] <= 100
    assert s["network"]["rx_bps"] >= 0 and s["uptime_s"] > 0 and s["gpu"] is None  # missing GPU interface -> None, not fabricated

def test_gpu_probe_failures_are_unavailable_not_errors():
    assert _nvidia_smi(which=lambda x: None) is None
    def boom(*a, **k): raise OSError("nope")
    assert _nvidia_smi(run=boom, which=lambda x: "/usr/bin/nvidia-smi") is None
    h = HostCollector(gpu_probes=[lambda: None]); assert h.sample()["gpu"] is None
