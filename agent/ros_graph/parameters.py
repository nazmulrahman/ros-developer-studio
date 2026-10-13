"""Read only the two standard parameter services. The existing ROS executor resolves futures."""
import threading
import time
from ..subscriptions.fields import describe

VALUE_FIELDS = [None, "bool_value", "integer_value", "double_value", "string_value", "byte_array_value",
                "bool_array_value", "integer_array_value", "double_array_value", "string_array_value"]


def read_parameters(node, name, list_type, get_type, timeout=3.0):
    deadline = time.monotonic() + timeout
    clients = []

    def call(kind, suffix, req):
        client = node.create_client(kind, name.rstrip("/") + suffix)
        clients.append(client)
        if not client.wait_for_service(timeout_sec=max(0, deadline - time.monotonic())):
            raise TimeoutError(f"Parameter service unavailable: {name}{suffix}")
        future = client.call_async(req)
        done = threading.Event()
        future.add_done_callback(lambda _: done.set())
        if not done.wait(max(0, deadline - time.monotonic())):
            future.cancel()
            raise TimeoutError(f"Parameter service timed out: {name}{suffix}")
        return future.result()

    try:
        listing = call(list_type, "/list_parameters", list_type.Request())
        names = sorted(listing.result.names)
        chosen = names[:500]
        req = get_type.Request()
        req.names = chosen
        values = call(get_type, "/get_parameters", req).values if chosen else []
        return {"node": name, "parameters": [{"name": n, "type": int(v.type),
                 "value": describe(getattr(v, VALUE_FIELDS[v.type])) if 0 < v.type < len(VALUE_FIELDS) else None}
                for n, v in zip(chosen, values)], "truncated": len(names) > 500}
    finally:
        for c in clients: node.destroy_client(c)
