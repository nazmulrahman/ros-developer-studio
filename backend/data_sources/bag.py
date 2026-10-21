"""Source-independent adapter over the restricted offline bag library."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from .base import DataSource
from ..bags.studio import BagLibrary, MAX_MESSAGES
from ..core.models import Sample, Stamps, TopicInfo


def _field(payload: dict[str, Any] | None, path: str) -> float | None:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class BagSource(DataSource):
    mode = "bag"

    def __init__(self, library: BagLibrary, bag_id: str):
        self.library, self.bag_id = library, bag_id
        self.source_id = f"bag:{bag_id}"

    async def topics(self) -> list[TopicInfo]:
        metadata = await asyncio.to_thread(self.library.summary, self.library.get(self.bag_id))
        return [TopicInfo(name=row["name"], types=[row["type"]]) for row in metadata["topics"]]

    async def stream(self, topics: list[str]) -> AsyncIterator[Sample]:
        rows: list[dict[str, Any]] = []
        for topic in topics:
            rows.extend(await asyncio.to_thread(self.library.messages, self.bag_id, topic, None, None, MAX_MESSAGES))
        for row in sorted(rows, key=lambda item: int(item["record_ns"])):
            yield Sample(source_mode="bag", source_id=self.source_id, topic=row["topic"], type=row["type"],
                         stamps=Stamps(record_ns=int(row["record_ns"])), payload=row["payload"],
                         meta={"size_bytes": row["size"], "decode_error": row["error"]})

    async def numeric_series(self, topic: str, field: str, start_ns: int | None, end_ns: int | None, max_points: int):
        rows = await asyncio.to_thread(self.library.messages, self.bag_id, topic, start_ns, end_ns, min(max_points, MAX_MESSAGES))
        return {"t_ns": [int(row["record_ns"]) for row in rows], "values": [_field(row["payload"], field) for row in rows]}
