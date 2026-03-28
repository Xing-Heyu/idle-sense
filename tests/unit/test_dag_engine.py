"""
Tests for DAG Execution Engine.
"""

import pytest

from legacy.distributed_task_v2.dag_engine import (
    DAGBuilder,
    DAGExecutionEngine,
    DAGTask,
    DependencyType,
    Stage,
    StageStatus,
    TaskChunk,
    TaskStatus,
)


class TestTaskChunk:
    """Test TaskChunk dataclass."""

    def test_create_chunk(self):
        """Test creating a task chunk."""
        chunk = TaskChunk(
            chunk_id="stage-1-chunk-0",
            stage_id="stage-1",
            task_id="task-001",
            data=[1, 2, 3],
            code="result = sum(data)"
        )

        assert chunk.chunk_id == "stage-1-chunk-0"
        assert chunk.status == TaskStatus.PENDING
        assert chunk.retry_count == 0
        assert chunk.max_retries == 3

    def test_to_dict(self):
        """Test chunk serialization."""
        chunk = TaskChunk(
            chunk_id="test-chunk",
            stage_id="stage-1",
            task_id="task-001",
            data=[1, 2, 3],
            code="test"
        )

        data = chunk.to_dict()

        assert data["chunk_id"] == "test-chunk"
        assert data["status"] == "pending"


class TestStage:
    """Test Stage dataclass."""

    def test_create_stage(self):
        """Test creating a stage."""
        stage = Stage(
            stage_id="stage-1",
            name="Map Stage",
            code_template="result = process(item)"
        )

        assert stage.stage_id == "stage-1"
        assert stage.status == StageStatus.PENDING
        assert stage.dependency_type == DependencyType.NARROW

    def test_is_ready(self):
        """Test stage dependency checking."""
        stage = Stage(
            stage_id="stage-2",
            name="Reduce Stage",
            code_template="result = reduce(items)",
            dependencies=["stage-1"]
        )

        assert stage.is_ready(set()) is False
        assert stage.is_ready({"stage-1"}) is True

    def test_get_progress(self):
        """Test progress calculation."""
        stage = Stage(
            stage_id="stage-1",
            name="Test Stage",
            code_template="test"
        )

        assert stage.get_progress() == 0.0

        stage.chunks = [
            TaskChunk("c1", "s1", "t1", [], "code", status=TaskStatus.COMPLETED),
            TaskChunk("c2", "s1", "t1", [], "code", status=TaskStatus.COMPLETED),
            TaskChunk("c3", "s1", "t1", [], "code", status=TaskStatus.PENDING),
        ]

        assert stage.get_progress() == pytest.approx(2/3)

    def test_to_dict(self):
        """Test stage serialization."""
        stage = Stage(
            stage_id="stage-1",
            name="Test Stage",
            code_template="test",
            chunks=[
                TaskChunk("c1", "s1", "t1", [], "code")
            ]
        )

        data = stage.to_dict()

        assert data["stage_id"] == "stage-1"
        assert data["total_chunks"] == 1


class TestDAGTask:
    """Test DAGTask dataclass."""

    def test_create_task(self):
        """Test creating a DAG task."""
        task = DAGTask(
            task_id="task-001",
            name="Test Task",
            description="A test task"
        )

        assert task.task_id == "task-001"
        assert task.status == TaskStatus.PENDING
        assert len(task.stages) == 0

    def test_get_ready_stages(self):
        """Test getting ready stages."""
        task = DAGTask(
            task_id="task-001",
            name="Test Task",
            stages=[
                Stage("s1", "Stage 1", "code"),
                Stage("s2", "Stage 2", "code", dependencies=["s1"]),
            ]
        )

        ready = task.get_ready_stages(set())
        assert len(ready) >= 1
        ready_ids = [s.stage_id for s in ready]
        assert "s1" in ready_ids

    def test_get_progress(self):
        """Test task progress calculation."""
        task = DAGTask(
            task_id="task-001",
            name="Test Task",
            stages=[
                Stage("s1", "Stage 1", "code", status=StageStatus.COMPLETED),
                Stage("s2", "Stage 2", "code", status=StageStatus.COMPLETED),
                Stage("s3", "Stage 3", "code", status=StageStatus.PENDING),
            ]
        )

        assert task.get_progress() == pytest.approx(2/3)


class TestDAGBuilder:
    """Test DAGBuilder class."""

    def test_build_simple_task(self):
        """Test building a simple task."""
        task = (
            DAGBuilder("task-001", "Simple Task")
            .add_map_stage(
                stage_id="map-1",
                code_template="result = process(item)",
                data=[1, 2, 3, 4, 5],
                partition_count=2
            )
            .build()
        )

        assert task.task_id == "task-001"
        assert len(task.stages) == 1
        assert len(task.stages[0].chunks) >= 2

    def test_build_map_reduce_task(self):
        """Test building a map-reduce task."""
        task = (
            DAGBuilder("task-002", "MapReduce Task")
            .add_map_stage(
                stage_id="map",
                code_template="result = map(item)",
                data=[1, 2, 3, 4],
                partition_count=2
            )
            .add_reduce_stage(
                stage_id="reduce",
                code_template="result = reduce(items)",
                dependencies=["map"]
            )
            .build()
        )

        assert len(task.stages) == 2
        assert task.stages[0].dependencies == []
        assert task.stages[1].dependencies == ["map"]
        assert task.stages[1].dependency_type == DependencyType.WIDE


class TestDAGExecutionEngine:
    """Test DAGExecutionEngine class."""

    @pytest.fixture
    def engine(self):
        """Create an execution engine."""
        return DAGExecutionEngine()

    def test_init(self, engine):
        """Test engine initialization."""
        assert engine._running is False
        assert len(engine.tasks) == 0

    @pytest.mark.asyncio
    async def test_start_stop(self, engine):
        """Test starting and stopping the engine."""
        await engine.start()
        assert engine._running is True

        await engine.stop()
        assert engine._running is False

    def test_submit_task(self, engine):
        """Test submitting a task."""
        task = DAGTask(
            task_id="task-001",
            name="Test Task",
            stages=[
                Stage("s1", "Stage 1", "code")
            ]
        )

        task_id = engine.submit_task(task)

        assert task_id == "task-001"
        assert "task-001" in engine.tasks

    def test_get_task_status(self, engine):
        """Test getting task status."""
        task = DAGTask(
            task_id="task-001",
            name="Test Task"
        )
        engine.submit_task(task)

        status = engine.get_task_status("task-001")

        assert status is not None
        assert status["task_id"] == "task-001"
        assert status["status"] == "pending"

    def test_get_task_status_not_found(self, engine):
        """Test getting status for non-existent task."""
        status = engine.get_task_status("nonexistent")
        assert status is None

    def test_get_task_result(self, engine):
        """Test getting task result."""
        task = DAGTask(
            task_id="task-001",
            name="Test Task",
            status=TaskStatus.COMPLETED,
            result={"total": 100}
        )
        engine.tasks["task-001"] = task

        result = engine.get_task_result("task-001")

        assert result == {"total": 100}

    def test_get_task_result_not_completed(self, engine):
        """Test getting result for incomplete task."""
        task = DAGTask(
            task_id="task-001",
            name="Test Task",
            status=TaskStatus.RUNNING
        )
        engine.tasks["task-001"] = task

        result = engine.get_task_result("task-001")
        assert result is None

    def test_cancel_task(self, engine):
        """Test canceling a task."""
        task = DAGTask(
            task_id="task-001",
            name="Test Task",
            status=TaskStatus.RUNNING
        )
        engine.tasks["task-001"] = task

        success = engine.cancel_task("task-001")

        assert success is True
        assert task.status == TaskStatus.CANCELLED

    def test_cancel_nonexistent_task(self, engine):
        """Test canceling a non-existent task."""
        success = engine.cancel_task("nonexistent")
        assert success is False

    def test_get_stats(self, engine):
        """Test getting engine stats."""
        stats = engine.get_stats()

        assert "tasks_submitted" in stats
        assert "tasks_completed" in stats
        assert "running" in stats

    @pytest.mark.asyncio
    async def test_execute_task_mock(self, engine):
        """Test executing a task with mock execution."""
        task = (
            DAGBuilder("task-001", "Test Task")
            .add_map_stage(
                stage_id="map",
                code_template="result = item * 2",
                data=[1, 2, 3],
                partition_count=1
            )
            .build()
        )

        engine.submit_task(task)

        success = await engine.execute_task("task-001")

        assert success is True
        assert task.status == TaskStatus.COMPLETED
