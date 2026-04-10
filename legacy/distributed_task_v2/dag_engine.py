"""
DAG Execution Engine for Distributed Tasks.

Implements a Spark-like DAG execution engine:
- Stage-based execution with dependencies
- Parallel task execution within stages
- Shuffle operations for wide dependencies
- Fault tolerance with checkpointing
- Progress tracking and monitoring

References:
- Spark DAG Scheduler: https://spark.apache.org/docs/latest/job-scheduling.html
- Dryad: Isard et al., "Dryad: Distributed Data-Parallel Programs" (2007)
"""

import asyncio
import contextlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DependencyType(Enum):
    NARROW = "narrow"
    WIDE = "wide"


@dataclass
class TaskChunk:
    """A chunk of work in a stage."""

    chunk_id: str
    stage_id: str
    task_id: str
    data: Any
    code: str
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_node: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "stage_id": self.stage_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "assigned_node": self.assigned_node,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class Stage:
    """A stage in the DAG."""

    stage_id: str
    name: str
    code_template: str
    dependencies: list[str] = field(default_factory=list)
    dependency_type: DependencyType = DependencyType.NARROW
    status: StageStatus = StageStatus.PENDING
    chunks: list[TaskChunk] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)
    partition_count: int = 4
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def is_ready(self, completed_stages: set[str]) -> bool:
        """Check if this stage can start based on dependencies."""
        return all(dep in completed_stages for dep in self.dependencies)

    def get_progress(self) -> float:
        """Get the completion progress (0.0 to 1.0)."""
        if not self.chunks:
            return 0.0
        completed = sum(1 for c in self.chunks if c.status == TaskStatus.COMPLETED)
        return completed / len(self.chunks)

    def get_failed_count(self) -> int:
        """Get the number of failed chunks."""
        return sum(1 for c in self.chunks if c.status == TaskStatus.FAILED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "dependency_type": self.dependency_type.value,
            "progress": self.get_progress(),
            "total_chunks": len(self.chunks),
            "completed_chunks": sum(1 for c in self.chunks if c.status == TaskStatus.COMPLETED),
            "failed_chunks": self.get_failed_count(),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class DAGTask:
    """A distributed task represented as a DAG."""

    task_id: str
    name: str
    description: str = ""
    stages: list[Stage] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def get_ready_stages(self, completed_stages: set[str]) -> list[Stage]:
        """Get stages that are ready to execute."""
        return [
            stage
            for stage in self.stages
            if stage.status == StageStatus.PENDING and stage.is_ready(completed_stages)
        ]

    def get_progress(self) -> float:
        """Get overall task progress."""
        if not self.stages:
            return 0.0
        completed = sum(1 for s in self.stages if s.status == StageStatus.COMPLETED)
        return completed / len(self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "progress": self.get_progress(),
            "total_stages": len(self.stages),
            "completed_stages": sum(1 for s in self.stages if s.status == StageStatus.COMPLETED),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stages": [s.to_dict() for s in self.stages],
        }


@dataclass
class Checkpoint:
    """Checkpoint for fault tolerance."""

    task_id: str
    stage_id: str
    chunk_id: str
    data: Any
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "stage_id": self.stage_id,
            "chunk_id": self.chunk_id,
            "timestamp": self.timestamp,
        }


class DAGExecutionEngine:
    """
    DAG Execution Engine for distributed task processing.

    Features:
    - Stage-based execution with dependency resolution
    - Parallel chunk execution within stages
    - Automatic retry on failure
    - Checkpoint-based recovery
    - Progress monitoring
    """

    MAX_CONCURRENT_CHUNKS = 10
    DEFAULT_TIMEOUT = 300
    CHECKPOINT_INTERVAL = 60

    def __init__(
        self,
        submit_func: Callable = None,
        check_status_func: Callable = None,
        max_concurrent_chunks: int = None,
    ):
        self.submit_func = submit_func
        self.check_status_func = check_status_func
        self.max_concurrent_chunks = max_concurrent_chunks or self.MAX_CONCURRENT_CHUNKS

        self.tasks: dict[str, DAGTask] = {}
        self.checkpoints: dict[str, Checkpoint] = {}
        self.completed_stages: dict[str, set[str]] = defaultdict(set)

        self._running = False
        self._tasks_list: list[asyncio.Task] = []
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "chunks_executed": 0,
            "chunks_failed": 0,
            "retries": 0,
        }

    async def start(self):
        """Start the execution engine."""
        if self._running:
            return

        self._running = True
        self._tasks_list = [
            asyncio.create_task(self._run_execution_loop()),
            asyncio.create_task(self._run_checkpoint_loop()),
        ]

    async def stop(self):
        """Stop the execution engine."""
        self._running = False
        for task in self._tasks_list:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks_list = []

    def submit_task(self, task: DAGTask) -> str:
        """Submit a DAG task for execution."""
        self.tasks[task.task_id] = task
        self.completed_stages[task.task_id] = set()
        self._stats["tasks_submitted"] += 1
        return task.task_id

    async def execute_task(self, task_id: str) -> bool:
        """Execute a submitted task."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        try:
            while True:
                ready_stages = task.get_ready_stages(self.completed_stages[task_id])

                if not ready_stages:
                    if all(s.status == StageStatus.COMPLETED for s in task.stages):
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = time.time()
                        self._stats["tasks_completed"] += 1
                        await self._finalize_task(task)
                        return True
                    elif any(s.status == StageStatus.FAILED for s in task.stages):
                        task.status = TaskStatus.FAILED
                        task.completed_at = time.time()
                        self._stats["tasks_failed"] += 1
                        return False
                    else:
                        await asyncio.sleep(0.5)
                        continue

                for stage in ready_stages:
                    asyncio.create_task(self._execute_stage(task, stage))

                await asyncio.sleep(0.1)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            self._stats["tasks_failed"] += 1
            return False

    async def _execute_stage(self, task: DAGTask, stage: Stage):
        """Execute a single stage."""
        stage.status = StageStatus.RUNNING
        stage.started_at = time.time()

        try:
            pending_chunks = [c for c in stage.chunks if c.status == TaskStatus.PENDING]

            semaphore = asyncio.Semaphore(self.max_concurrent_chunks)

            async def execute_chunk(chunk: TaskChunk):
                async with semaphore:
                    return await self._execute_chunk(task, stage, chunk)

            results = await asyncio.gather(
                *[execute_chunk(c) for c in pending_chunks], return_exceptions=True
            )

            failed_count = sum(1 for r in results if isinstance(r, Exception) or r is False)

            if failed_count > 0:
                stage.status = StageStatus.FAILED
            else:
                stage.status = StageStatus.COMPLETED
                self.completed_stages[task.task_id].add(stage.stage_id)
                stage.results = [c.result for c in stage.chunks if c.result is not None]

            stage.completed_at = time.time()

        except Exception:
            stage.status = StageStatus.FAILED
            stage.completed_at = time.time()

    async def _execute_chunk(self, task: DAGTask, stage: Stage, chunk: TaskChunk) -> bool:
        """Execute a single chunk with retry support."""
        chunk.status = TaskStatus.RUNNING
        chunk.started_at = time.time()

        for attempt in range(chunk.max_retries + 1):
            try:
                if not self.submit_func:
                    await asyncio.sleep(0.1)
                    chunk.result = {"mock": True, "data": chunk.data}
                    chunk.status = TaskStatus.COMPLETED
                    chunk.completed_at = time.time()
                    self._stats["chunks_executed"] += 1
                    return True

                task_id = await self.submit_func(chunk.code, chunk.data)

                if not task_id:
                    raise Exception("Failed to submit chunk to scheduler")

                chunk.assigned_node = task_id

                while True:
                    status, result = await self.check_status_func(task_id)

                    if status == "completed":
                        chunk.result = result
                        chunk.status = TaskStatus.COMPLETED
                        chunk.completed_at = time.time()
                        self._stats["chunks_executed"] += 1
                        return True
                    elif status == "failed":
                        raise Exception(result or "Chunk execution failed")

                    await asyncio.sleep(0.5)

            except Exception as e:
                chunk.retry_count += 1
                self._stats["retries"] += 1

                if attempt == chunk.max_retries:
                    chunk.status = TaskStatus.FAILED
                    chunk.error = str(e)
                    chunk.completed_at = time.time()
                    self._stats["chunks_failed"] += 1
                    return False

                await asyncio.sleep(2**attempt)

        return False

    async def _finalize_task(self, task: DAGTask):
        """Finalize task results after all stages complete."""
        final_stage = task.stages[-1] if task.stages else None
        if final_stage and final_stage.results:
            task.result = final_stage.results

    async def _run_execution_loop(self):
        """Background loop for task execution."""
        while self._running:
            await asyncio.sleep(0.1)

    async def _run_checkpoint_loop(self):
        """Background loop for checkpointing."""
        while self._running:
            await asyncio.sleep(self.CHECKPOINT_INTERVAL)
            await self._create_checkpoints()

    async def _create_checkpoints(self):
        """Create checkpoints for running tasks."""
        for task_id, task in self.tasks.items():
            if task.status == TaskStatus.RUNNING:
                for stage in task.stages:
                    if stage.status == StageStatus.RUNNING:
                        for chunk in stage.chunks:
                            if chunk.status == TaskStatus.COMPLETED:
                                checkpoint_key = f"{task_id}:{stage.stage_id}:{chunk.chunk_id}"
                                if checkpoint_key not in self.checkpoints:
                                    self.checkpoints[checkpoint_key] = Checkpoint(
                                        task_id=task_id,
                                        stage_id=stage.stage_id,
                                        chunk_id=chunk.chunk_id,
                                        data=chunk.result,
                                    )

    async def recover_from_checkpoint(self, task_id: str) -> bool:
        """Recover a task from checkpoints."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        for _, checkpoint in self.checkpoints.items():
            if checkpoint.task_id == task_id:
                for stage in task.stages:
                    if stage.stage_id == checkpoint.stage_id:
                        for chunk in stage.chunks:
                            if chunk.chunk_id == checkpoint.chunk_id:
                                chunk.result = checkpoint.data
                                chunk.status = TaskStatus.COMPLETED

        return True

    def get_task_status(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get the status of a task."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        return task.to_dict()

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """Get the result of a completed task."""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.COMPLETED:
            return task.result
        return None

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()

            for stage in task.stages:
                if stage.status == StageStatus.RUNNING:
                    stage.status = StageStatus.FAILED
                for chunk in stage.chunks:
                    if chunk.status == TaskStatus.RUNNING:
                        chunk.status = TaskStatus.CANCELLED

            return True

        return False

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            **self._stats,
            "active_tasks": sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING),
            "checkpoints": len(self.checkpoints),
            "running": self._running,
        }


class DAGBuilder:
    """Builder for creating DAG tasks."""

    def __init__(self, task_id: str, name: str, description: str = ""):
        self.task_id = task_id
        self.name = name
        self.description = description
        self.stages: list[Stage] = []
        self._stage_counter = 0

    def add_stage(
        self,
        stage_id: str,
        name: str,
        code_template: str,
        data: Any = None,
        dependencies: list[str] = None,
        dependency_type: DependencyType = DependencyType.NARROW,
        partition_count: int = 4,
    ) -> "DAGBuilder":
        """Add a stage to the DAG."""
        stage = Stage(
            stage_id=stage_id,
            name=name,
            code_template=code_template,
            dependencies=dependencies or [],
            dependency_type=dependency_type,
            partition_count=partition_count,
        )

        if data is not None:
            chunks = self._create_chunks(stage, data, partition_count)
            stage.chunks = chunks

        self.stages.append(stage)
        self._stage_counter += 1

        return self

    def add_map_stage(
        self, stage_id: str, code_template: str, data: list[Any], partition_count: int = 4
    ) -> "DAGBuilder":
        """Add a map stage (no dependencies)."""
        return self.add_stage(
            stage_id=stage_id,
            name=f"Map Stage {self._stage_counter}",
            code_template=code_template,
            data=data,
            dependencies=[],
            dependency_type=DependencyType.NARROW,
            partition_count=partition_count,
        )

    def add_reduce_stage(
        self, stage_id: str, code_template: str, dependencies: list[str], partition_count: int = 1
    ) -> "DAGBuilder":
        """Add a reduce stage (depends on previous stages)."""
        return self.add_stage(
            stage_id=stage_id,
            name=f"Reduce Stage {self._stage_counter}",
            code_template=code_template,
            data=None,
            dependencies=dependencies,
            dependency_type=DependencyType.WIDE,
            partition_count=partition_count,
        )

    def _create_chunks(self, stage: Stage, data: Any, partition_count: int) -> list[TaskChunk]:
        """Create chunks for a stage."""
        if isinstance(data, list):
            chunk_size = max(1, len(data) // partition_count)
            partitions = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
        else:
            partitions = [data]

        chunks = []
        for i, partition_data in enumerate(partitions):
            chunk = TaskChunk(
                chunk_id=f"{stage.stage_id}-chunk-{i}",
                stage_id=stage.stage_id,
                task_id=self.task_id,
                data=partition_data,
                code=stage.code_template,
            )
            chunks.append(chunk)

        return chunks

    def build(self) -> DAGTask:
        """Build the DAG task."""
        return DAGTask(
            task_id=self.task_id,
            name=self.name,
            description=self.description,
            stages=self.stages,
        )


__all__ = [
    "TaskStatus",
    "StageStatus",
    "DependencyType",
    "TaskChunk",
    "Stage",
    "DAGTask",
    "Checkpoint",
    "DAGExecutionEngine",
    "DAGBuilder",
]
