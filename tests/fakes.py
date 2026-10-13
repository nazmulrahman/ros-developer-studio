"""Controlled fixtures. FakeRos implements the same RosBackend interface as RclpyBackend. Test-only; never used by the product."""
from __future__ import annotations
import asyncio, socket, threading, time

import uvicorn

from agent.host_metrics.collector import HostCollector
from agent.ros_graph.backend import RosBackend, TopicNotFound, UnsupportedType
from agent.ros_graph.qos import qos_conflicts
from agent.server import AgentServer
from agent.subscriptions.fields import numeric_fields


class Vector3:
    @staticmethod
    def get_fields_and_field_types(): return {"x": "double", "y": "double", "z": "double"}

class Twist:
    @staticmethod
    def get_fields_and_field_types(): return {"linear": "geometry_msgs/Vector3", "angular": "geometry_msgs/Vector3"}

class Scan:
    @staticmethod
    def get_fields_and_field_types(): return {"frame_id": "string", "angle_min": "float", "ranges": "sequence<float>", "cov": "double[4]"}

CLASSES = {"geometry_msgs/msg/Vector3": Vector3, "geometry_msgs/msg/Twist": Twist, "sensor_msgs/msg/LaserScan": Scan}


def ep(node, reliability="RELIABLE", durability="VOLATILE"):
    return {"node": node, "namespace": "/", "type": "x", "qos": {"reliability": reliability, "durability": durability, "history": "KEEP_LAST", "depth": 10}}


class FakeRos(RosBackend):
    def __init__(self):
        self.topics: dict[str, dict] = {}
        self.nodes: list[tuple[str, str]] = []
        self.services = [("/reset", ["std_srvs/srv/Trigger"])]
        self.actions = [("/navigate", ["nav2_msgs/action/NavigateToPose"])]
        self.callbacks: dict[str, list] = {}
        self.fail_signature: str | None = None

    def add_topic(self, name, type_="geometry_msgs/msg/Twist", pubs=("talker",), subs=()):
        self.topics[name] = {"types": [type_], "pubs": [ep(n) for n in pubs], "subs": [ep(n) for n in subs]}

    def info(self): return {"available": True, "distro": "fake", "domain_id": "7", "rmw": "fake_rmw", "error": None}
    def signature(self):
        if self.fail_signature:
            raise RuntimeError(self.fail_signature)
        return tuple(sorted((k, tuple(v["types"])) for k, v in self.topics.items())), tuple(self.nodes)

    def graph(self, self_topics):
        return {"nodes": [{"name": n, "namespace": ns, "full": ns.rstrip("/") + "/" + n, "self": False} for n, ns in self.nodes],
                "topics": [{"name": k, "types": v["types"], "publishers": len(v["pubs"]), "subscribers": len(v["subs"])} for k, v in sorted(self.topics.items())],
                "services": [{"name": n, "types": t} for n, t in self.services],
                "actions": [{"name": n, "types": t} for n, t in self.actions], "warnings": []}

    def topic_info(self, name):
        t = self.topics.get(name)
        if not t: return None
        return {"name": name, "types": t["types"], "publishers": t["pubs"], "subscribers": t["subs"], "qos_conflicts": qos_conflicts(t["pubs"], t["subs"])}

    def topic_presence(self, name, self_subscribed):
        t = self.topics.get(name)
        return (False, 0, 0) if not t else (True, len(t["pubs"]), len(t["subs"]))

    def node_info(self, full): return {"name": full, "publishers": [], "subscribers": [], "service_servers": [], "service_clients": []}
    def fields_for(self, type_name):
        if type_name not in CLASSES: raise UnsupportedType(f"Message type '{type_name}' is not available")
        return numeric_fields(lambda t: CLASSES[t], type_name)

    def subscribe(self, topic, cb):
        t = self.topics.get(topic)
        if not t: raise TopicNotFound(f"Topic {topic} is not in the ROS graph")
        if t["types"][0] not in CLASSES: raise UnsupportedType(f"Message type '{t['types'][0]}' is not available")
        self.callbacks.setdefault(topic, []).append(cb)
        outer = self
        class H:
            types_ = list(t["types"])
            def close(self): outer.callbacks[topic].remove(cb)
        return H()

    def publish(self, topic, msg, size=64):
        for cb in list(self.callbacks.get(topic, [])):
            cb(time.monotonic(), size, lambda: msg)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


class AgentThread:
    """Real AgentServer on a real loopback WebSocket, in its own thread/loop (like the real agent process)."""
    def __init__(self, ros, port=None, token=None, host=None):
        self.ros, self.port, self.token = ros, port or free_port(), token
        self.host = host or HostCollector(gpu_probes=[])
        self.thread = None

    def start(self):
        ready = threading.Event()
        def run():
            async def main():
                self.loop = asyncio.get_running_loop()
                self.server = AgentServer(self.ros, self.host, window_s=5.0, graph_interval_s=0.2, token=self.token)
                self.srv = await self.server.serve("127.0.0.1", self.port)
                self.stop_ev = asyncio.Event(); ready.set()
                await self.stop_ev.wait()
                self.srv.close(); await self.server.aclose(); await self.srv.wait_closed()
            asyncio.run(main())
        self.thread = threading.Thread(target=run, daemon=True); self.thread.start()
        assert ready.wait(5), "agent did not start"
        return self

    def stop(self):
        self.loop.call_soon_threadsafe(self.stop_ev.set); self.thread.join(5)


class BackendThread:
    def __init__(self, agent_url, token="tok"):
        from backend.core import auth
        from backend.core.state import state
        auth.set_token(token)
        state.settings.agent_url = agent_url
        from backend.main import create_app
        self.port = free_port()
        self.server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=self.port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True); self.thread.start()
        t0 = time.time()
        while not self.server.started:
            assert time.time() - t0 < 5, "backend did not start"; time.sleep(0.02)
        self.token = token
        self.url = f"http://127.0.0.1:{self.port}"
        self.ws_url = f"ws://127.0.0.1:{self.port}/ws/live?token={token}"

    def stop(self):
        self.server.should_exit = True; self.thread.join(5)
