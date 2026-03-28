"""
Task Checkpoint and Recovery Module.

This module provides checkpointing capabilities for long-running tasks,
enabling recovery from failures and resumption of interrupted work.

Architecture Reference:
- Spark Checkpointing: https://spark.apache.org/docs/latest/streaming-programming-guide.html#checkpointing
- Ray Checkpointing: https://docs.ray.io/en/latest/ray-core/actors/actor-checkpointing.html
"""
import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""
    checkpoint_id: str
    task_id: str
    stage: str
    timestamp: float
    size_bytes: int
    checksum: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointMetadata":
        return cls(**data)


@dataclass
class CheckpointData(Generic[T]):
    """Checkpoint data container."""
    checkpoint_id: str
    task_id: str
    stage: str
    state: T
    variables: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "stage": self.stage,
            "state": self.state,
            "variables": self.variables,
            "created_at": self.created_at,
        }


class CheckpointStorage:
    """Storage backend for checkpoints."""

    def __init__(self, base_path: str = "checkpoints"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _get_checkpoint_path(self, task_id: str, checkpoint_id: str) -> Path:
        """Get the file path for a checkpoint."""
        task_dir = self.base_path / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir / f"{checkpoint_id}.ckpt"

    def _get_metadata_path(self, task_id: str, checkpoint_id: str) -> Path:
        """Get the file path for checkpoint metadata."""
        task_dir = self.base_path / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir / f"{checkpoint_id}.meta"

    def save(self, checkpoint: CheckpointData) -> CheckpointMetadata:
        """Save a checkpoint to storage."""
        checkpoint_path = self._get_checkpoint_path(checkpoint.task_id, checkpoint.checkpoint_id)
        metadata_path = self._get_metadata_path(checkpoint.task_id, checkpoint.checkpoint_id)

        with self._lock:
            serialized = json.dumps(checkpoint.to_dict(), ensure_ascii=True).encode("utf-8")
            checksum = hashlib.sha256(serialized).hexdigest()[:16]

            with open(checkpoint_path, "wb") as f:
                f.write(serialized)

            metadata = CheckpointMetadata(
                checkpoint_id=checkpoint.checkpoint_id,
                task_id=checkpoint.task_id,
                stage=checkpoint.stage,
                timestamp=time.time(),
                size_bytes=len(serialized),
                checksum=checksum,
            )

            with open(metadata_path, "w") as f:
                json.dump(metadata.to_dict(), f, indent=2)

            return metadata

    def load(self, task_id: str, checkpoint_id: str) -> Optional[CheckpointData]:
        """Load a checkpoint from storage."""
        checkpoint_path = self._get_checkpoint_path(task_id, checkpoint_id)
        self._get_metadata_path(task_id, checkpoint_id)

        with self._lock:
            if not checkpoint_path.exists():
                return None

            with open(checkpoint_path, "rb") as f:
                data = json.load(f)

            return CheckpointData(
                checkpoint_id=data["checkpoint_id"],
                task_id=data["task_id"],
                stage=data["stage"],
                state=data["state"],
                variables=data.get("variables", {}),
                created_at=data.get("created_at", time.time()),
            )

    def list_checkpoints(self, task_id: str) -> list[CheckpointMetadata]:
        """List all checkpoints for a task."""
        task_dir = self.base_path / task_id

        if not task_dir.exists():
            return []

        checkpoints = []

        for meta_file in task_dir.glob("*.meta"):
            with open(meta_file) as f:
                data = json.load(f)
                checkpoints.append(CheckpointMetadata.from_dict(data))

        return sorted(checkpoints, key=lambda c: c.timestamp, reverse=True)

    def get_latest(self, task_id: str) -> Optional[CheckpointMetadata]:
        """Get the latest checkpoint for a task."""
        checkpoints = self.list_checkpoints(task_id)
        return checkpoints[0] if checkpoints else None

    def delete(self, task_id: str, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        checkpoint_path = self._get_checkpoint_path(task_id, checkpoint_id)
        metadata_path = self._get_metadata_path(task_id, checkpoint_id)

        with self._lock:
            deleted = False

            if checkpoint_path.exists():
                checkpoint_path.unlink()
                deleted = True

            if metadata_path.exists():
                metadata_path.unlink()
                deleted = True

            return deleted

    def cleanup_old(self, task_id: str, keep_count: int = 5) -> int:
        """Clean up old checkpoints, keeping only the latest N."""
        checkpoints = self.list_checkpoints(task_id)

        deleted_count = 0
        for checkpoint in checkpoints[keep_count:]:
            if self.delete(task_id, checkpoint.checkpoint_id):
                deleted_count += 1

        return deleted_count


class CheckpointManager:
    """
    Manager for task checkpointing.

    Usage:
        manager = CheckpointManager()

        # Create checkpoint
        checkpoint = manager.create_checkpoint(
            task_id="task-001",
            stage="processing",
            state={"progress": 50, "data": [...]}
        )

        # Restore from checkpoint
        restored = manager.restore("task-001")
        if restored:
            print(f"Restored from stage: {restored.stage}")
    """

    def __init__(
        self,
        storage: Optional[CheckpointStorage] = None,
        auto_cleanup: bool = True,
        keep_count: int = 5
    ):
        self.storage = storage or CheckpointStorage()
        self.auto_cleanup = auto_cleanup
        self.keep_count = keep_count

    def create_checkpoint(
        self,
        task_id: str,
        stage: str,
        state: Any,
        variables: Optional[dict[str, Any]] = None,
        checkpoint_id: Optional[str] = None
    ) -> CheckpointMetadata:
        """Create and save a checkpoint."""
        if checkpoint_id is None:
            checkpoint_id = f"ckpt_{int(time.time() * 1000)}"

        checkpoint = CheckpointData(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            stage=stage,
            state=state,
            variables=variables or {},
        )

        metadata = self.storage.save(checkpoint)

        if self.auto_cleanup:
            self.storage.cleanup_old(task_id, self.keep_count)

        return metadata

    def restore(
        self,
        task_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[CheckpointData]:
        """Restore from a checkpoint."""
        if checkpoint_id:
            return self.storage.load(task_id, checkpoint_id)

        latest = self.storage.get_latest(task_id)
        if latest:
            return self.storage.load(task_id, latest.checkpoint_id)

        return None

    def get_checkpoint_history(self, task_id: str) -> list[CheckpointMetadata]:
        """Get checkpoint history for a task."""
        return self.storage.list_checkpoints(task_id)

    def delete_checkpoint(self, task_id: str, checkpoint_id: str) -> bool:
        """Delete a specific checkpoint."""
        return self.storage.delete(task_id, checkpoint_id)

    def clear_task_checkpoints(self, task_id: str) -> int:
        """Clear all checkpoints for a task."""
        checkpoints = self.storage.list_checkpoints(task_id)
        deleted = 0

        for checkpoint in checkpoints:
            if self.storage.delete(task_id, checkpoint.checkpoint_id):
                deleted += 1

        return deleted


class CheckpointableTask:
    """
    Base class for tasks that support checkpointing.

    Usage:
        class MyTask(CheckpointableTask):
            def execute(self):
                for i in range(100):
                    self.checkpoint(stage="processing", state={"i": i})
                    # ... do work ...

                    if self.should_resume():
                        data = self.get_resume_state()
                        i = data["i"]
    """

    def __init__(
        self,
        task_id: str,
        checkpoint_manager: Optional[CheckpointManager] = None,
        checkpoint_interval: int = 10
    ):
        self.task_id = task_id
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.checkpoint_interval = checkpoint_interval
        self._last_checkpoint = 0
        self._resume_state: Optional[dict[str, Any]] = None

    def should_checkpoint(self) -> bool:
        """Check if it's time to create a checkpoint."""
        return time.time() - self._last_checkpoint >= self.checkpoint_interval

    def checkpoint(
        self,
        stage: str,
        state: Any,
        variables: Optional[dict[str, Any]] = None
    ) -> CheckpointMetadata:
        """Create a checkpoint."""
        self._last_checkpoint = time.time()
        return self.checkpoint_manager.create_checkpoint(
            task_id=self.task_id,
            stage=stage,
            state=state,
            variables=variables
        )

    def should_resume(self) -> bool:
        """Check if there's a checkpoint to resume from."""
        if self._resume_state is not None:
            return True

        restored = self.checkpoint_manager.restore(self.task_id)
        if restored:
            self._resume_state = restored.state
            return True

        return False

    def get_resume_state(self) -> Optional[Any]:
        """Get the state to resume from."""
        if self._resume_state is not None:
            return self._resume_state

        restored = self.checkpoint_manager.restore(self.task_id)
        if restored:
            return restored.state

        return None

    def clear_checkpoints(self) -> int:
        """Clear all checkpoints for this task."""
        return self.checkpoint_manager.clear_task_checkpoints(self.task_id)

    def execute(self) -> Any:
        """Execute the task. Override this method."""
        raise NotImplementedError("Subclasses must implement execute()")


def with_checkpoint(
    stage: str,
    interval: int = 10
) -> Callable:
    """
    Decorator for automatic checkpointing.

    Usage:
        @with_checkpoint(stage="processing", interval=5)
        def process_data(data, task_id, checkpoint_manager):
            # ... process data ...
            return result
    """
    def decorator(func: Callable) -> Callable:
        last_checkpoint = [0.0]

        def wrapper(*args, **kwargs):
            task_id = kwargs.get("task_id", "default")
            checkpoint_manager = kwargs.get("checkpoint_manager")

            if checkpoint_manager and time.time() - last_checkpoint[0] >= interval:
                checkpoint_manager.create_checkpoint(
                    task_id=task_id,
                    stage=stage,
                    state={"args": args, "kwargs": kwargs}
                )
                last_checkpoint[0] = time.time()

            return func(*args, **kwargs)

        return wrapper

    return decorator
