"""Result Aggregator - Aggregates and processes task results."""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, TypeVar, Union

T = TypeVar("T")
K = TypeVar("K")


class AggregationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class TaskResult(Generic[T]):
    task_id: str
    value: T
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    node_id: str | None = None
    duration_ms: int = 0


@dataclass
class AggregationResult(Generic[T]):
    aggregation_id: str
    status: AggregationStatus
    result: T | None = None
    partial_results: list[TaskResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    total_tasks: int = 0
    completed_tasks: int = 0

    @property
    def progress(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / self.total_tasks

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or time.time()
        return end - self.started_at


class AggregationStrategy(ABC, Generic[T]):
    @abstractmethod
    def aggregate(self, results: list[TaskResult]) -> T:
        pass

    @abstractmethod
    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        pass


class SumAggregator(AggregationStrategy[Union[int, float]]):
    def aggregate(self, results: list[TaskResult]) -> int | float:
        return sum(r.value for r in results if r.success)

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return len(results) == total


class AverageAggregator(AggregationStrategy[float]):
    def aggregate(self, results: list[TaskResult]) -> float:
        values = [r.value for r in results if r.success]
        return sum(values) / len(values) if values else 0.0

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return len(results) == total


class CountAggregator(AggregationStrategy[int]):
    def aggregate(self, results: list[TaskResult]) -> int:
        return sum(1 for r in results if r.success)

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return True


class MinAggregator(AggregationStrategy[Union[int, float]]):
    def aggregate(self, results: list[TaskResult]) -> int | float:
        values = [r.value for r in results if r.success]
        return min(values) if values else 0

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return len(results) == total


class MaxAggregator(AggregationStrategy[Union[int, float]]):
    def aggregate(self, results: list[TaskResult]) -> int | float:
        values = [r.value for r in results if r.success]
        return max(values) if values else 0

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return len(results) == total


class ListAggregator(AggregationStrategy[list[Any]]):
    def aggregate(self, results: list[TaskResult]) -> list[Any]:
        return [r.value for r in results if r.success]

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return True


class DictAggregator(AggregationStrategy[dict[str, Any]]):
    def aggregate(self, results: list[TaskResult]) -> dict[str, Any]:
        result = {}
        for r in results:
            if r.success and isinstance(r.value, dict):
                result.update(r.value)
        return result

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return True


class FirstAggregator(AggregationStrategy[Any]):
    def aggregate(self, results: list[TaskResult]) -> Any:
        for r in results:
            if r.success:
                return r.value
        return None

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return any(r.success for r in results)


class LastAggregator(AggregationStrategy[Any]):
    def aggregate(self, results: list[TaskResult]) -> Any:
        for r in reversed(results):
            if r.success:
                return r.value
        return None

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return len(results) == total


class MergeAggregator(AggregationStrategy[dict[str, Any]]):
    def __init__(self, deep: bool = True):
        self.deep = deep

    def aggregate(self, results: list[TaskResult]) -> dict[str, Any]:
        merged = {}
        for r in results:
            if r.success and isinstance(r.value, dict):
                if self.deep:
                    merged = self._deep_merge(merged, r.value)
                else:
                    merged.update(r.value)
        return merged

    def _deep_merge(self, base: dict, update: dict) -> dict:
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return True


class ReduceAggregator(AggregationStrategy[Any]):
    def __init__(
        self,
        reducer: Callable[[Any, Any], Any],
        initial: Any = None
    ):
        self.reducer = reducer
        self.initial = initial

    def aggregate(self, results: list[TaskResult]) -> Any:
        values = [r.value for r in results if r.success]
        if not values:
            return self.initial

        result = self.initial if self.initial is not None else values[0]
        start = 1 if self.initial is not None else 0

        for value in values[start:]:
            result = self.reducer(result, value)

        return result

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return len(results) == total


class GroupByAggregator(AggregationStrategy[dict[Any, list[Any]]]):
    def __init__(self, key_func: Callable[[Any], Any]):
        self.key_func = key_func

    def aggregate(self, results: list[TaskResult]) -> dict[Any, list[Any]]:
        grouped = defaultdict(list)
        for r in results:
            if r.success:
                key = self.key_func(r.value)
                grouped[key].append(r.value)
        return dict(grouped)

    def can_aggregate(self, results: list[TaskResult], total: int) -> bool:
        return True


class ResultAggregator(Generic[T]):
    def __init__(
        self,
        strategy: AggregationStrategy[T] | None = None,
        partial_aggregation: bool = False
    ):
        self.strategy = strategy or ListAggregator()
        self.partial_aggregation = partial_aggregation
        self._aggregations: dict[str, AggregationResult] = {}
        self._results: dict[str, list[TaskResult]] = {}
        self._expected_counts: dict[str, int] = {}

    def create_aggregation(
        self,
        aggregation_id: str,
        total_tasks: int
    ) -> AggregationResult[T]:
        result = AggregationResult[T](
            aggregation_id=aggregation_id,
            status=AggregationStatus.PENDING,
            total_tasks=total_tasks
        )

        self._aggregations[aggregation_id] = result
        self._results[aggregation_id] = []
        self._expected_counts[aggregation_id] = total_tasks

        return result

    def add_result(
        self,
        aggregation_id: str,
        result: TaskResult
    ) -> AggregationResult[T] | None:
        if aggregation_id not in self._aggregations:
            return None

        self._results[aggregation_id].append(result)

        agg_result = self._aggregations[aggregation_id]
        agg_result.partial_results.append(result)
        agg_result.completed_tasks = len(self._results[aggregation_id])

        if not result.success:
            agg_result.errors.append(result.error or "Unknown error")

        if agg_result.status == AggregationStatus.PENDING:
            agg_result.status = AggregationStatus.IN_PROGRESS

        total = self._expected_counts[aggregation_id]
        results = self._results[aggregation_id]

        if self.strategy.can_aggregate(results, total):
            try:
                agg_result.result = self.strategy.aggregate(results)
                agg_result.status = AggregationStatus.COMPLETED
                agg_result.completed_at = time.time()
            except Exception as e:
                agg_result.status = AggregationStatus.FAILED
                agg_result.errors.append(str(e))
        elif self.partial_aggregation and len(results) > 0:
            try:
                agg_result.result = self.strategy.aggregate(results)
                agg_result.status = AggregationStatus.PARTIAL
            except Exception:
                pass

        return agg_result

    def get_aggregation(self, aggregation_id: str) -> AggregationResult[T] | None:
        return self._aggregations.get(aggregation_id)

    def get_partial_result(self, aggregation_id: str) -> T | None:
        results = self._results.get(aggregation_id, [])
        if not results:
            return None

        try:
            return self.strategy.aggregate(results)
        except Exception:
            return None

    def cancel_aggregation(self, aggregation_id: str) -> bool:
        if aggregation_id not in self._aggregations:
            return False

        agg_result = self._aggregations[aggregation_id]
        if agg_result.status in (AggregationStatus.COMPLETED, AggregationStatus.FAILED):
            return False

        agg_result.status = AggregationStatus.FAILED
        agg_result.errors.append("Aggregation cancelled")
        agg_result.completed_at = time.time()

        return True

    def get_statistics(self, aggregation_id: str) -> dict[str, Any]:
        agg_result = self._aggregations.get(aggregation_id)
        if not agg_result:
            return {}

        results = self._results.get(aggregation_id, [])
        success_results = [r for r in results if r.success]

        durations = [r.duration_ms for r in results if r.duration_ms > 0]

        return {
            "aggregation_id": aggregation_id,
            "status": agg_result.status.value,
            "progress": agg_result.progress,
            "total_tasks": agg_result.total_tasks,
            "completed_tasks": agg_result.completed_tasks,
            "success_count": len(success_results),
            "error_count": len(agg_result.errors),
            "duration_seconds": agg_result.duration_seconds,
            "avg_task_duration_ms": sum(durations) / len(durations) if durations else 0
        }

    def clear_completed(self, max_age_seconds: int = 3600) -> int:
        now = time.time()
        to_remove = []

        for agg_id, agg_result in self._aggregations.items():
            if (
                agg_result.status in (AggregationStatus.COMPLETED, AggregationStatus.FAILED)
                and agg_result.completed_at
                and (now - agg_result.completed_at) > max_age_seconds
            ):
                to_remove.append(agg_id)

        for agg_id in to_remove:
            del self._aggregations[agg_id]
            del self._results[agg_id]
            del self._expected_counts[agg_id]

        return len(to_remove)


class DistributedResultCollector:
    def __init__(self, aggregator: ResultAggregator):
        self.aggregator = aggregator
        self._checksums: dict[str, str] = {}

    def collect(
        self,
        aggregation_id: str,
        task_id: str,
        value: Any,
        success: bool = True,
        error: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> AggregationResult | None:
        result = TaskResult(
            task_id=task_id,
            value=value,
            success=success,
            error=error,
            metadata=metadata or {}
        )

        return self.aggregator.add_result(aggregation_id, result)

    def compute_checksum(self, data: Any) -> str:
        try:
            serialized = json.dumps(data, sort_keys=True, ensure_ascii=True).encode("utf-8")
            return hashlib.sha256(serialized).hexdigest()
        except Exception:
            return ""

    def verify_integrity(
        self,
        aggregation_id: str,
        expected_checksum: str
    ) -> bool:
        agg_result = self.aggregator.get_aggregation(aggregation_id)
        if not agg_result or not agg_result.result:
            return False

        actual_checksum = self.compute_checksum(agg_result.result)
        return actual_checksum == expected_checksum


__all__ = [
    "AggregationStatus",
    "TaskResult",
    "AggregationResult",
    "AggregationStrategy",
    "SumAggregator",
    "AverageAggregator",
    "CountAggregator",
    "MinAggregator",
    "MaxAggregator",
    "ListAggregator",
    "DictAggregator",
    "FirstAggregator",
    "LastAggregator",
    "MergeAggregator",
    "ReduceAggregator",
    "GroupByAggregator",
    "ResultAggregator",
    "DistributedResultCollector",
]
