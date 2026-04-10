"""
Priority Queue Implementation for Task Scheduling.

This module provides multiple priority queue implementations
for different scheduling scenarios.
"""

import asyncio
import heapq
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(order=True)
class PrioritizedItem(Generic[T]):
    """Item with priority for heap-based priority queue."""

    priority: float
    sequence: int = field(compare=True)
    item: T = field(compare=False)
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)


class PriorityQueue(Generic[T]):
    """
    Thread-safe priority queue implementation.

    Lower priority values are processed first.

    Usage:
        queue = PriorityQueue()
        queue.put(item, priority=1.0)
        item = queue.get()
    """

    def __init__(self, maxsize: int = 0):
        self._queue: list[PrioritizedItem[T]] = []
        self._sequence = 0
        self._maxsize = maxsize
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition()

    async def put(
        self, item: T, priority: float = 0.0, metadata: Optional[dict[str, Any]] = None
    ) -> bool:
        """Add an item to the queue."""
        async with self._lock:
            if self._maxsize > 0 and len(self._queue) >= self._maxsize:
                return False

            prioritized = PrioritizedItem(
                priority=priority, sequence=self._sequence, item=item, metadata=metadata or {}
            )

            self._sequence += 1
            heapq.heappush(self._queue, prioritized)

            async with self._not_empty:
                self._not_empty.notify()

            return True

    def put_nowait(
        self, item: T, priority: float = 0.0, metadata: Optional[dict[str, Any]] = None
    ) -> bool:
        """Add an item without waiting."""
        if self._maxsize > 0 and len(self._queue) >= self._maxsize:
            return False

        prioritized = PrioritizedItem(
            priority=priority, sequence=self._sequence, item=item, metadata=metadata or {}
        )

        self._sequence += 1
        heapq.heappush(self._queue, prioritized)

        return True

    async def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """Get the highest priority item."""
        async with self._not_empty:
            if not self._queue:
                try:
                    await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None

            if not self._queue:
                return None

            prioritized = heapq.heappop(self._queue)
            return prioritized.item

    def get_nowait(self) -> Optional[T]:
        """Get item without waiting."""
        if not self._queue:
            return None

        prioritized = heapq.heappop(self._queue)
        return prioritized.item

    def peek(self) -> Optional[T]:
        """Peek at the highest priority item without removing."""
        if not self._queue:
            return None
        return self._queue[0].item

    def qsize(self) -> int:
        """Get queue size."""
        return len(self._queue)

    def empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._queue) == 0

    def clear(self) -> None:
        """Clear the queue."""
        self._queue.clear()


class BoundedPriorityQueue(Generic[T]):
    """
    Priority queue with bounded size and aging.

    Features:
    - Maximum size limit
    - Priority aging to prevent starvation
    - Statistics tracking
    """

    def __init__(
        self, maxsize: int = 1000, aging_factor: float = 0.1, aging_interval: float = 60.0
    ):
        self._queue: list[PrioritizedItem[T]] = []
        self._sequence = 0
        self._maxsize = maxsize
        self._aging_factor = aging_factor
        self._aging_interval = aging_interval
        self._last_aging = time.time()

        self._stats = {
            "total_enqueued": 0,
            "total_dequeued": 0,
            "total_dropped": 0,
            "current_size": 0,
        }

    def put(
        self, item: T, priority: float = 0.0, metadata: Optional[dict[str, Any]] = None
    ) -> bool:
        """Add an item to the queue."""
        self._apply_aging()

        if len(self._queue) >= self._maxsize:
            self._stats["total_dropped"] += 1
            return False

        prioritized = PrioritizedItem(
            priority=priority,
            sequence=self._sequence,
            item=item,
            metadata={**(metadata or {}), "enqueued_at": time.time()},
        )

        self._sequence += 1
        heapq.heappush(self._queue, prioritized)

        self._stats["total_enqueued"] += 1
        self._stats["current_size"] = len(self._queue)

        return True

    def get(self) -> Optional[T]:
        """Get the highest priority item."""
        self._apply_aging()

        if not self._queue:
            return None

        prioritized = heapq.heappop(self._queue)

        self._stats["total_dequeued"] += 1
        self._stats["current_size"] = len(self._queue)

        return prioritized.item

    def _apply_aging(self) -> None:
        """Apply priority aging to prevent starvation."""
        now = time.time()

        if now - self._last_aging < self._aging_interval:
            return

        self._last_aging = now

        for item in self._queue:
            age = now - item.metadata.get("enqueued_at", now)
            item.priority -= age * self._aging_factor

        heapq.heapify(self._queue)

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        return {**self._stats}

    def qsize(self) -> int:
        return len(self._queue)


class MultiLevelPriorityQueue(Generic[T]):
    """
    Multi-level priority queue with different priority classes.

    Similar to Unix process scheduling with multiple run queues.
    """

    def __init__(self, levels: int = 3):
        self._levels = levels
        self._queues: list[list[PrioritizedItem[T]]] = [[] for _ in range(levels)]
        self._sequence = 0
        self._current_level = 0

    def put(self, item: T, priority: float = 0.0, level: int = 0) -> bool:
        """Add an item to a specific priority level."""
        if level < 0 or level >= self._levels:
            return False

        prioritized = PrioritizedItem(priority=priority, sequence=self._sequence, item=item)

        self._sequence += 1
        heapq.heappush(self._queues[level], prioritized)

        return True

    def get(self) -> Optional[T]:
        """Get item using round-robin across levels."""
        for _ in range(self._levels):
            queue = self._queues[self._current_level]

            if queue:
                prioritized = heapq.heappop(queue)
                return prioritized.item

            self._current_level = (self._current_level + 1) % self._levels

        return None

    def qsize(self) -> int:
        return sum(len(q) for q in self._queues)

    def qsize_by_level(self) -> dict[int, int]:
        return {i: len(q) for i, q in enumerate(self._queues)}
