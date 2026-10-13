"""Agent <-> backend protocol (see docs/ARCHITECTURE.md §6). Declarative only in the scaffold.

Control: JSON  {"id": str, "op": str, "args": {}}  ->  {"id": str, "ok": bool, "result"|"error"}
Data:    msgpack frames {"ch": "sample"|"stats"|"host"|"log"|"diag", ...}
"""
OPS = (
    "graph.snapshot", "topic.info", "sub.start", "sub.stop", "sub.list",
    "host.start", "host.stop", "tf.snapshot", "logs.tail",
    "bag.record.start", "bag.record.stop", "bag.record.status",
    "test.publish", "test.service", "test.velocity",   # gated; refused unless enabled
)
CHANNELS = ("sample", "stats", "host", "log", "diag")
