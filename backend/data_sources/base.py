"""One interface for live and recorded data. Visualizations depend only on this."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncIterator
from ..core.models import Sample, TopicInfo


class DataSource(ABC):
    source_id: str
    mode: str  # "live" | "bag"

    @abstractmethod
    async def topics(self) -> list[TopicInfo]: ...

    @abstractmethod
    def stream(self, topics: list[str]) -> AsyncIterator[Sample]: ...

    @abstractmethod
    async def numeric_series(self, topic: str, field: str, start_ns: int | None, end_ns: int | None, max_points: int): ...
