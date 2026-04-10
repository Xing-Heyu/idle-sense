"""
Distributed Task Partitioning Module.

This module provides intelligent task partitioning algorithms inspired by
Spark DAG and MapReduce patterns for efficient distributed execution.

Architecture Reference:
- Spark DAG Scheduler: https://spark.apache.org/docs/latest/job-scheduling.html
- MapReduce: https://research.google/pubs/pub62/
- Ray: https://docs.ray.io/en/latest/ray-core/tasks.html
"""
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, Optional, TypeVar

from legacy.distributed_task_v2.dag_engine import (
    Checkpoint,
    DAGBuilder,
    DAGExecutionEngine,
    DAGTask,
    StageStatus,
)
from legacy.distributed_task_v2.dag_engine import (
    Stage as DAGStage,
)
from legacy.distributed_task_v2.dag_engine import (
    TaskChunk as DAGTaskChunk,
)
from legacy.distributed_task_v2.dag_engine import (
    TaskStatus as DAGTaskStatus,
)
from legacy.distributed_task_v2.fault_tolerance import (
    CircuitBreaker,
    FailureType,
    FaultToleranceManager,
    RetryConfig,
    RetryPolicy,
    StragglerDetector,
)

T = TypeVar("T")
R = TypeVar("R")


class DependencyType(str, Enum):
    """Task dependency type."""
    NARROW = "narrow"
    WIDE = "wide"


class PartitionStrategy(str, Enum):
    """Partition strategy enumeration."""
    HASH = "hash"
    RANGE = "range"
    SIZE = "size"
    ROUND_ROBIN = "round_robin"
    KEY = "key"


class TaskStageStatus(str, Enum):
    """Task stage status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskChunk:
    """A chunk of a distributed task."""
    chunk_id: str
    parent_task_id: str
    stage_id: str
    data: Any
    code: str
    dependencies: list[str] = field(default_factory=list)
    status: TaskStageStatus = TaskStageStatus.PENDING
    assigned_node: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "parent_task_id": self.parent_task_id,
            "stage_id": self.stage_id,
            "data": self.data,
            "code": self.code,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "assigned_node": self.assigned_node,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class TaskStage:
    """A stage in the task DAG."""
    stage_id: str
    name: str
    code_template: str
    dependencies: list[str] = field(default_factory=list)
    dependency_type: DependencyType = DependencyType.NARROW
    partition_strategy: PartitionStrategy = PartitionStrategy.HASH
    partition_count: int = 4
    status: TaskStageStatus = TaskStageStatus.PENDING
    chunks: list[TaskChunk] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)

    def is_ready(self, completed_stages: set) -> bool:
        """Check if this stage is ready to execute."""
        return all(dep in completed_stages for dep in self.dependencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "code_template": self.code_template,
            "dependencies": self.dependencies,
            "dependency_type": self.dependency_type.value,
            "partition_strategy": self.partition_strategy.value,
            "partition_count": self.partition_count,
            "status": self.status.value,
            "chunk_count": len(self.chunks),
        }


@dataclass
class DistributedTask:
    """A distributed task with multiple stages."""
    task_id: str
    name: str
    description: str = ""
    stages: list[TaskStage] = field(default_factory=list)
    current_stage_index: int = 0
    status: TaskStageStatus = TaskStageStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def get_ready_stages(self, completed_stages: set) -> list[TaskStage]:
        """Get stages that are ready to execute."""
        return [
            stage for stage in self.stages
            if stage.status == TaskStageStatus.PENDING
            and stage.is_ready(completed_stages)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "stages": [s.to_dict() for s in self.stages],
            "current_stage_index": self.current_stage_index,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class Partitioner(ABC, Generic[T]):
    """Abstract base class for partitioners."""

    @abstractmethod
    def partition(self, data: list[T], num_partitions: int) -> dict[int, list[T]]:
        """Partition data into specified number of partitions."""
        pass


class HashPartitioner(Partitioner):
    """
    Hash-based partitioner.

    Distributes data evenly across partitions using hash values.
    Suitable for uniform distribution.
    """

    def __init__(self, key_func: Optional[Callable[[T], Any]] = None):
        self.key_func = key_func or (lambda x: x)

    def partition(self, data: list[T], num_partitions: int) -> dict[int, list[T]]:
        partitions: dict[int, list[T]] = {i: [] for i in range(num_partitions)}

        for item in data:
            key = self.key_func(item)
            key_hash = hashlib.md5(str(key).encode()).hexdigest()
            partition_id = int(key_hash, 16) % num_partitions
            partitions[partition_id].append(item)

        return partitions


class RangePartitioner(Partitioner):
    """
    Range-based partitioner.

    Distributes data based on value ranges.
    Suitable for sorted or ordered data.
    """

    def __init__(self, key_func: Optional[Callable[[T], Any]] = None):
        self.key_func = key_func or (lambda x: x)

    def partition(self, data: list[T], num_partitions: int) -> dict[int, list[T]]:
        if not data:
            return {i: [] for i in range(num_partitions)}

        sorted_data = sorted(data, key=self.key_func)
        chunk_size = len(sorted_data) // num_partitions

        partitions: dict[int, list[T]] = {}

        for i in range(num_partitions):
            start = i * chunk_size
            end = start + chunk_size if i < num_partitions - 1 else len(sorted_data)
            partitions[i] = sorted_data[start:end]

        return partitions


class SizePartitioner(Partitioner):
    """
    Size-based partitioner.

    Creates partitions based on target chunk size.
    Automatically determines optimal partition count.
    """

    def __init__(self, target_chunk_size: int = 100):
        self.target_chunk_size = target_chunk_size

    def partition(self, data: list[T], num_partitions: int) -> dict[int, list[T]]:
        num_partitions = max(1, len(data) // self.target_chunk_size)
        num_partitions = min(num_partitions, 100)

        partitions: dict[int, list[T]] = {i: [] for i in range(num_partitions)}

        for i, item in enumerate(data):
            partition_id = i % num_partitions
            partitions[partition_id].append(item)

        return partitions


class RoundRobinPartitioner(Partitioner):
    """
    Round-robin partitioner.

    Distributes data in a circular fashion.
    Simple and ensures even distribution.
    """

    def partition(self, data: list[T], num_partitions: int) -> dict[int, list[T]]:
        partitions: dict[int, list[T]] = {i: [] for i in range(num_partitions)}

        for i, item in enumerate(data):
            partition_id = i % num_partitions
            partitions[partition_id].append(item)

        return partitions


class KeyPartitioner(Partitioner):
    """
    Key-based partitioner.

    Groups items with the same key into the same partition.
    Useful for aggregation operations.
    """

    def __init__(self, key_func: Callable[[T], Any]):
        self.key_func = key_func

    def partition(self, data: list[T], num_partitions: int) -> dict[int, list[T]]:
        groups: dict[Any, list[T]] = {}

        for item in data:
            key = self.key_func(item)
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        partitions: dict[int, list[T]] = {i: [] for i in range(num_partitions)}
        keys = list(groups.keys())

        for i, key in enumerate(keys):
            partition_id = i % num_partitions
            partitions[partition_id].extend(groups[key])

        return partitions


PARTITIONERS: dict[PartitionStrategy, type] = {
    PartitionStrategy.HASH: HashPartitioner,
    PartitionStrategy.RANGE: RangePartitioner,
    PartitionStrategy.SIZE: SizePartitioner,
    PartitionStrategy.ROUND_ROBIN: RoundRobinPartitioner,
    PartitionStrategy.KEY: KeyPartitioner,
}


def create_partitioner(
    strategy: PartitionStrategy,
    **kwargs
) -> Partitioner:
    """Factory function to create a partitioner."""
    partitioner_class = PARTITIONERS.get(strategy)

    if not partitioner_class:
        raise ValueError(f"Unknown partition strategy: {strategy}")

    return partitioner_class(**kwargs)


class DistributedTaskBuilder:
    """
    Builder for creating distributed tasks.

    Usage:
        task = (DistributedTaskBuilder("task-001", "My Task")
            .add_map_stage("stage-1", "result = process(item)", data)
            .add_reduce_stage("stage-2", "result = sum(items)", ["stage-1"])
            .build())
    """

    def __init__(self, task_id: str, name: str, description: str = ""):
        self.task_id = task_id
        self.name = name
        self.description = description
        self.stages: list[TaskStage] = []
        self._stage_counter = 0

    def add_stage(
        self,
        stage_id: str,
        name: str,
        code_template: str,
        data: Optional[list[Any]] = None,
        dependencies: Optional[list[str]] = None,
        dependency_type: DependencyType = DependencyType.NARROW,
        partition_strategy: PartitionStrategy = PartitionStrategy.HASH,
        partition_count: int = 4
    ) -> "DistributedTaskBuilder":
        """Add a stage to the task."""
        stage = TaskStage(
            stage_id=stage_id,
            name=name,
            code_template=code_template,
            dependencies=dependencies or [],
            dependency_type=dependency_type,
            partition_strategy=partition_strategy,
            partition_count=partition_count,
        )

        if data:
            partitioner = create_partitioner(partition_strategy)
            partitions = partitioner.partition(data, partition_count)

            for partition_id, partition_data in partitions.items():
                chunk = TaskChunk(
                    chunk_id=f"{stage_id}-chunk-{partition_id}",
                    parent_task_id=self.task_id,
                    stage_id=stage_id,
                    data=partition_data,
                    code=code_template,
                )
                stage.chunks.append(chunk)

        self.stages.append(stage)
        self._stage_counter += 1

        return self

    def add_map_stage(
        self,
        stage_id: str,
        code_template: str,
        data: list[Any],
        partition_count: int = 4
    ) -> "DistributedTaskBuilder":
        """Add a map stage (first stage, no dependencies)."""
        return self.add_stage(
            stage_id=stage_id,
            name=f"Map Stage {self._stage_counter}",
            code_template=code_template,
            data=data,
            dependencies=[],
            dependency_type=DependencyType.NARROW,
            partition_strategy=PartitionStrategy.HASH,
            partition_count=partition_count
        )

    def add_reduce_stage(
        self,
        stage_id: str,
        code_template: str,
        dependencies: list[str],
        partition_count: int = 1
    ) -> "DistributedTaskBuilder":
        """Add a reduce stage (depends on previous stages)."""
        return self.add_stage(
            stage_id=stage_id,
            name=f"Reduce Stage {self._stage_counter}",
            code_template=code_template,
            data=None,
            dependencies=dependencies,
            dependency_type=DependencyType.WIDE,
            partition_strategy=PartitionStrategy.HASH,
            partition_count=partition_count
        )

    def build(self) -> DistributedTask:
        """Build the distributed task."""
        return DistributedTask(
            task_id=self.task_id,
            name=self.name,
            description=self.description,
            stages=self.stages,
        )


DISTRIBUTED_TASK_TEMPLATES = {
    "map_reduce": {
        "description": "Map-Reduce pattern for parallel processing",
        "stages": [
            {
                "name": "Map",
                "type": "map",
                "description": "Apply function to each item in parallel"
            },
            {
                "name": "Shuffle",
                "type": "shuffle",
                "description": "Group items by key"
            },
            {
                "name": "Reduce",
                "type": "reduce",
                "description": "Aggregate grouped items"
            }
        ]
    },
    "parallel_search": {
        "description": "Parallel search pattern",
        "stages": [
            {
                "name": "Search",
                "type": "map",
                "description": "Search in parallel across partitions"
            },
            {
                "name": "Merge",
                "type": "reduce",
                "description": "Merge search results"
            }
        ]
    },
    "data_processing": {
        "description": "Data processing pipeline",
        "stages": [
            {
                "name": "Extract",
                "type": "map",
                "description": "Extract data from sources"
            },
            {
                "name": "Transform",
                "type": "map",
                "description": "Transform data"
            },
            {
                "name": "Load",
                "type": "reduce",
                "description": "Load processed data"
            }
        ]
    },
    "monte_carlo": {
        "description": "Monte Carlo simulation pattern",
        "stages": [
            {
                "name": "Simulate",
                "type": "map",
                "description": "Run simulations in parallel"
            },
            {
                "name": "Aggregate",
                "type": "reduce",
                "description": "Aggregate simulation results"
            }
        ]
    }
}


def create_task_from_template(
    template_name: str,
    task_id: str,
    data: list[Any],
    code_templates: dict[str, str],
    partition_count: int = 4
) -> DistributedTask:
    """
    Create a distributed task from a predefined template.

    Args:
        template_name: Name of the template (map_reduce, parallel_search, etc.)
        task_id: Unique task identifier
        data: Input data for the task
        code_templates: Code templates for each stage
        partition_count: Number of partitions

    Returns:
        DistributedTask instance
    """
    if template_name not in DISTRIBUTED_TASK_TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}")

    template = DISTRIBUTED_TASK_TEMPLATES[template_name]
    builder = DistributedTaskBuilder(task_id, template["description"])

    for i, stage_config in enumerate(template["stages"]):
        stage_id = f"stage-{i}"
        stage_type = stage_config["type"]

        if stage_type == "map":
            builder.add_map_stage(
                stage_id=stage_id,
                code_template=code_templates.get(stage_config["name"], "# Map stage"),
                data=data,
                partition_count=partition_count
            )
        elif stage_type == "reduce":
            builder.add_reduce_stage(
                stage_id=stage_id,
                code_template=code_templates.get(stage_config["name"], "# Reduce stage"),
                dependencies=[f"stage-{i-1}"]
            )
        elif stage_type == "shuffle":
            builder.add_stage(
                stage_id=stage_id,
                name=stage_config["name"],
                code_template=code_templates.get(stage_config["name"], "# Shuffle stage"),
                data=None,
                dependencies=[f"stage-{i-1}"],
                dependency_type=DependencyType.WIDE,
                partition_strategy=PartitionStrategy.KEY,
                partition_count=partition_count
            )

    return builder.build()


__all__ = [
    "DependencyType",
    "PartitionStrategy",
    "TaskStageStatus",
    "TaskChunk",
    "TaskStage",
    "DistributedTask",
    "Partitioner",
    "HashPartitioner",
    "RangePartitioner",
    "SizePartitioner",
    "RoundRobinPartitioner",
    "KeyPartitioner",
    "DistributedTaskBuilder",
    "DISTRIBUTED_TASK_TEMPLATES",
    "create_partitioner",
    "create_task_from_template",
    "DAGExecutionEngine",
    "DAGBuilder",
    "DAGTask",
    "DAGTaskStatus",
    "StageStatus",
    "DAGTaskChunk",
    "DAGStage",
    "Checkpoint",
    "FaultToleranceManager",
    "RetryPolicy",
    "RetryConfig",
    "FailureType",
    "CircuitBreaker",
    "StragglerDetector",
]
