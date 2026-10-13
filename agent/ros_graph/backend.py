"""ROS access behind one interface. RclpyBackend is the only code that imports rclpy.

NOTE: RclpyBackend has NOT been run against a real ROS 2 graph in the build environment (no ROS available).
"""
from __future__ import annotations
import os, threading, time
from abc import ABC, abstractmethod
from typing import Callable

from ..subscriptions.fields import numeric_fields
from .qos import qos_conflicts

MsgCallback = Callable[[float, "int | None", Callable[[], object]], None]


class RosUnavailable(Exception):
    pass


class TopicNotFound(Exception):
    pass


class UnsupportedType(Exception):
    pass


class RosBackend(ABC):
    NODE_NAME = "ros_developer_studio_agent"

    @abstractmethod
    def info(self) -> dict: ...
    @abstractmethod
    def graph(self, self_topics: set[str]) -> dict: ...
    @abstractmethod
    def signature(self) -> tuple: ...
    @abstractmethod
    def topic_info(self, name: str) -> dict | None: ...
    @abstractmethod
    def topic_presence(self, name: str, self_subscribed: bool) -> tuple[bool, int, int]: ...
    @abstractmethod
    def node_info(self, full_name: str) -> dict | None: ...
    @abstractmethod
    def subscribe(self, topic: str, cb: MsgCallback): ...
    @abstractmethod
    def fields_for(self, type_name: str) -> list[dict]: ...
    def close(self) -> None: ...


class NullRos(RosBackend):
    """Used when rclpy cannot be imported. Host metrics still work; every ROS call reports why it can't."""

    def __init__(self, error: str):
        self.error = error

    def info(self):
        return {"available": False, "distro": os.environ.get("ROS_DISTRO"), "domain_id": os.environ.get("ROS_DOMAIN_ID", "0"),
                "rmw": None, "error": self.error}

    def _no(self, *a, **k):
        raise RosUnavailable(self.error)

    graph = signature = topic_info = topic_presence = node_info = subscribe = fields_for = _no


def _enum(x) -> str | None:
    return None if x is None else str(getattr(x, "name", x)).split(".")[-1]


class RclpyBackend(RosBackend):
    def __init__(self):
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        self._rclpy = rclpy
        rclpy.init()
        self.node = rclpy.create_node(self.NODE_NAME)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self.node)
        self._thread = threading.Thread(target=self._executor.spin, daemon=True, name="rclpy-spin")
        self._thread.start()

    def info(self):
        return {"available": True, "distro": os.environ.get("ROS_DISTRO"),
                "domain_id": os.environ.get("ROS_DOMAIN_ID", "0"),
                "rmw": os.environ.get("RMW_IMPLEMENTATION") or "default",
                "localhost_only": os.environ.get("ROS_LOCALHOST_ONLY"), "error": None}

    def _is_self(self, name: str, ns: str) -> bool:
        return name == self.NODE_NAME and ns in ("", "/")

    def signature(self):
        topics = tuple(sorted((n, tuple(t)) for n, t in self.node.get_topic_names_and_types()))
        nodes = tuple(sorted(self.node.get_node_names_and_namespaces()))
        return topics, nodes

    def graph(self, self_topics):
        nodes = [{"name": n, "namespace": ns, "full": (ns.rstrip("/") + "/" + n), "self": self._is_self(n, ns)}
                 for n, ns in sorted(self.node.get_node_names_and_namespaces())]
        topics = []
        for name, types in sorted(self.node.get_topic_names_and_types()):
            subs = self.node.count_subscribers(name) - (1 if name in self_topics else 0)
            topics.append({"name": name, "types": list(types), "publishers": self.node.count_publishers(name),
                           "subscribers": max(0, subs)})
        services = [{"name": n, "types": list(t)} for n, t in sorted(self.node.get_service_names_and_types())]
        warnings: list[str] = []
        try:
            from rclpy.action import get_action_names_and_types
            actions = [{"name": n, "types": list(t)} for n, t in sorted(get_action_names_and_types(self.node))]
        except Exception as e:  # keep graph usable if action introspection is unavailable
            actions = []
            warnings.append(f"Action discovery unavailable: {type(e).__name__}: {e}")
        return {"nodes": nodes, "topics": topics, "services": services, "actions": actions, "warnings": warnings}

    def _endpoint(self, i) -> dict:
        q = i.qos_profile
        return {"node": i.node_name, "namespace": i.node_namespace, "type": i.topic_type,
                "qos": {"reliability": _enum(q.reliability), "durability": _enum(q.durability),
                        "history": _enum(q.history), "depth": q.depth, "liveliness": _enum(q.liveliness)}}

    def topic_info(self, name):
        types = dict(self.node.get_topic_names_and_types()).get(name)
        if types is None:
            return None
        pubs = [self._endpoint(i) for i in self.node.get_publishers_info_by_topic(name) if not self._is_self(i.node_name, i.node_namespace)]
        subs = [self._endpoint(i) for i in self.node.get_subscriptions_info_by_topic(name) if not self._is_self(i.node_name, i.node_namespace)]
        return {"name": name, "types": list(types), "publishers": pubs, "subscribers": subs,
                "qos_conflicts": qos_conflicts(pubs, subs)}

    def topic_presence(self, name, self_subscribed):
        types = dict(self.node.get_topic_names_and_types()).get(name)
        if types is None:
            return False, 0, 0
        subs = self.node.count_subscribers(name) - (1 if self_subscribed else 0)
        return True, self.node.count_publishers(name), max(0, subs)

    def node_info(self, full_name):
        ns, _, name = full_name.rpartition("/")
        ns = ns or "/"
        try:
            def pack(rows):
                return [{"name": n, "types": list(t)} for n, t in sorted(rows)]
            return {"name": full_name,
                    "publishers": pack(self.node.get_publisher_names_and_types_by_node(name, ns)),
                    "subscribers": pack(self.node.get_subscriber_names_and_types_by_node(name, ns)),
                    "service_servers": pack(self.node.get_service_names_and_types_by_node(name, ns)),
                    "service_clients": pack(self.node.get_client_names_and_types_by_node(name, ns))}
        except Exception:  # node vanished between listing and inspection
            return None

    def _msg_class(self, type_name: str):
        from rosidl_runtime_py.utilities import get_message
        try:
            return get_message(type_name)
        except Exception as e:
            raise UnsupportedType(f"Message type '{type_name}' is not available in this ROS environment "
                                  f"(is its package built and sourced?): {type(e).__name__}: {e}")

    def fields_for(self, type_name):
        return numeric_fields(self._msg_class, type_name)

    def subscribe(self, topic, cb):
        from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
        from rclpy.serialization import deserialize_message
        types = dict(self.node.get_topic_names_and_types()).get(topic)
        if not types:
            raise TopicNotFound(f"Topic {topic} is not in the ROS graph")
        cls = self._msg_class(types[0])
        # BEST_EFFORT + VOLATILE is compatible with every publisher QoS, so measurement never fails on QoS.
        qos = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT, durability=QoSDurabilityPolicy.VOLATILE,
                         history=QoSHistoryPolicy.KEEP_LAST, depth=10)

        def raw(data: bytes):
            cb(time.monotonic(), len(data), lambda: deserialize_message(data, cls))

        sub = self.node.create_subscription(cls, topic, raw, qos, raw=True)  # raw: stats cost no deserialization
        node = self.node

        class Handle:
            types_ = list(types)
            def close(self_inner):
                node.destroy_subscription(sub)
        return Handle()

    def close(self):
        try:
            self._executor.shutdown()
            self.node.destroy_node()
            self._rclpy.shutdown()
        except Exception:
            pass
