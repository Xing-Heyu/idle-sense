"""
End-to-End Integration Tests for Distributed Task System.

Tests the complete distributed task workflow:
- Task submission and execution
- DAG execution
- Shuffle operations
- Progress monitoring
- Fault tolerance
"""

import pytest

from legacy.distributed_task_v2.dag_engine import (
    DAGBuilder,
    DAGExecutionEngine,
)
from legacy.distributed_task_v2.fault_tolerance import (
    CircuitBreaker,
    FaultToleranceManager,
    RetryConfig,
    RetryPolicy,
)
from legacy.distributed_task_v2.progress_ws import (
    MessageType,
    ProgressTracker,
)
from legacy.distributed_task_v2.shuffle import (
    ShuffleManager,
)


class TestDAGExecutionE2E:
    """End-to-end tests for DAG execution."""

    @pytest.fixture
    def engine(self):
        """Create a DAG execution engine."""
        return DAGExecutionEngine()

    @pytest.fixture
    def simple_task(self):
        """Create a simple DAG task."""
        return (
            DAGBuilder("task-001", "Simple Task")
            .add_map_stage(
                stage_id="map",
                code_template="result = item * 2",
                data=[1, 2, 3, 4, 5],
                partition_count=2
            )
            .build()
        )

    @pytest.mark.asyncio
    async def test_engine_lifecycle(self, engine):
        """Test engine start and stop."""
        await engine.start()
        assert engine._running is True

        await engine.stop()
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_submit_and_execute_task(self, engine, simple_task):
        """Test submitting and executing a task."""
        await engine.start()

        task_id = engine.submit_task(simple_task)
        assert task_id == "task-001"

        success = await engine.execute_task("task-001")
        assert success is True

        result = engine.get_task_result("task-001")
        assert result is not None

        await engine.stop()

    @pytest.mark.asyncio
    async def test_task_status_tracking(self, engine, simple_task):
        """Test task status tracking."""
        await engine.start()

        engine.submit_task(simple_task)

        status = engine.get_task_status("task-001")
        assert status["status"] == "pending"

        await engine.execute_task("task-001")

        status = engine.get_task_status("task-001")
        assert status["status"] == "completed"

        await engine.stop()

    @pytest.mark.asyncio
    async def test_cancel_task(self, engine, simple_task):
        """Test canceling a task."""
        await engine.start()

        engine.submit_task(simple_task)

        success = engine.cancel_task("task-001")
        assert success is True

        status = engine.get_task_status("task-001")
        assert status["status"] == "cancelled"

        await engine.stop()

    @pytest.mark.asyncio
    async def test_engine_stats(self, engine):
        """Test engine statistics."""
        stats = engine.get_stats()

        assert "tasks_submitted" in stats
        assert "running" in stats


class TestShuffleE2E:
    """End-to-end tests for shuffle operations."""

    @pytest.fixture
    def manager(self):
        """Create a shuffle manager."""
        return ShuffleManager(num_partitions=4)

    def test_shuffle_workflow(self, manager):
        """Test complete shuffle workflow."""
        shuffle_id = manager.start_shuffle("task-001", "stage-1")

        assert shuffle_id is not None

        for i in range(10):
            manager.add_data(shuffle_id, f"key-{i % 3}", f"value-{i}")

        for i in range(4):
            manager.assign_partition(shuffle_id, i, f"node-{i}")

        success = manager.complete_shuffle(shuffle_id)
        assert success is True

        result = manager.get_shuffle_result(shuffle_id)
        assert result.status == "completed"

    def test_shuffle_stats(self, manager):
        """Test shuffle statistics."""
        stats = manager.get_stats()

        assert "shuffles_started" in stats
        assert "total_records_shuffled" in stats


class TestFaultToleranceE2E:
    """End-to-end tests for fault tolerance."""

    @pytest.fixture
    def manager(self):
        """Create a fault tolerance manager."""
        config = RetryConfig(
            max_retries=3,
            policy=RetryPolicy.EXPONENTIAL,
            base_delay=0.1,
        )
        return FaultToleranceManager(retry_config=config)

    @pytest.mark.asyncio
    async def test_manager_lifecycle(self, manager):
        """Test manager start and stop."""
        await manager.start()

        await manager.stop()

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, manager):
        """Test successful execution with retry."""
        call_count = 0

        async def execute_func():
            nonlocal call_count
            call_count += 1
            return "success"

        success, result = await manager.execute_with_retry(
            chunk_id="chunk-001",
            task_id="task-001",
            execute_func=execute_func,
        )

        assert success is True
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_retry_failure(self, manager):
        """Test execution that fails all retries."""
        call_count = 0

        async def execute_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Simulated failure")

        success, error = await manager.execute_with_retry(
            chunk_id="chunk-001",
            task_id="task-001",
            execute_func=execute_func,
        )

        assert success is False
        assert call_count == 4

    def test_circuit_breaker(self):
        """Test circuit breaker pattern."""
        cb = CircuitBreaker(failure_threshold=3)

        assert cb.can_execute() is True

        for _ in range(3):
            cb.record_failure()

        assert cb.can_execute() is False

        cb.record_success()
        cb.record_success()
        cb.record_success()

        assert cb.can_execute() is True

    def test_failure_stats(self, manager):
        """Test failure statistics."""
        stats = manager.get_failure_stats()

        assert "total_failures" in stats
        assert "failures_by_type" in stats


class TestProgressMonitoringE2E:
    """End-to-end tests for progress monitoring."""

    @pytest.fixture
    def tracker(self):
        """Create a progress tracker."""
        return ProgressTracker()

    def test_task_progress_workflow(self, tracker):
        """Test complete task progress workflow."""
        tracker.register_task("task-001", total_stages=2)

        progress = tracker.get_task_progress("task-001")
        assert progress.status == "pending"

        tracker.register_stage("task-001", "stage-1", total_chunks=5)
        tracker.register_stage("task-001", "stage-2", total_chunks=3)

        for i in range(5):
            tracker.complete_chunk("task-001", "stage-1", f"chunk-{i}")

        stage_progress = tracker.get_stage_progress("task-001", "stage-1")
        assert stage_progress.status == "running"
        assert stage_progress.progress == 1.0

        tracker.complete_task("task-001", result={"total": 100})

        progress = tracker.get_task_progress("task-001")
        assert progress.status == "completed"
        assert progress.progress == 1.0

    def test_progress_subscription(self, tracker):
        """Test progress subscription."""
        received = []

        def callback(update):
            received.append(update)

        tracker.subscribe("task-001", callback)
        tracker.register_task("task-001", total_stages=1)

        assert len(received) == 1
        assert received[0].message_type == MessageType.TASK_STATUS

    def test_progress_history(self, tracker):
        """Test progress history."""
        tracker.register_task("task-001", total_stages=1)
        tracker.update_task_status("task-001", "running")
        tracker.complete_task("task-001")

        history = tracker.get_history("task-001")

        assert len(history) == 3


class TestIntegratedWorkflow:
    """End-to-end tests for integrated workflow."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete distributed task workflow."""
        engine = DAGExecutionEngine()
        tracker = ProgressTracker()
        ft_manager = FaultToleranceManager()

        await engine.start()
        await ft_manager.start()

        try:
            task = (
                DAGBuilder("workflow-001", "Integration Test")
                .add_map_stage(
                    stage_id="map",
                    code_template="result = process(item)",
                    data=list(range(10)),
                    partition_count=2
                )
                .build()
            )

            tracker.register_task("workflow-001", total_stages=1)
            tracker.register_stage("workflow-001", "map", total_chunks=2)

            engine.submit_task(task)
            tracker.update_task_status("workflow-001", "running")

            success = await engine.execute_task("workflow-001")

            if success:
                tracker.complete_task("workflow-001")
            else:
                tracker.update_task_status("workflow-001", "failed")

            progress = tracker.get_task_progress("workflow-001")
            assert progress.status in ("completed", "failed")

        finally:
            await engine.stop()
            await ft_manager.stop()

    @pytest.mark.asyncio
    async def test_workflow_with_shuffle(self):
        """Test workflow with shuffle operation."""
        shuffle_manager = ShuffleManager(num_partitions=4)

        shuffle_id = shuffle_manager.start_shuffle("task-001", "shuffle-stage")

        data = [(f"key-{i % 3}", f"value-{i}") for i in range(20)]
        for key, value in data:
            shuffle_manager.add_data(shuffle_id, key, value)

        for i in range(4):
            shuffle_manager.assign_partition(shuffle_id, i, f"node-{i}")

        shuffle_manager.complete_shuffle(shuffle_id)

        result = shuffle_manager.get_shuffle_result(shuffle_id)
        assert result.status == "completed"
        assert result.total_size == 20


class TestSystemStats:
    """Tests for system statistics."""

    def test_dag_engine_stats(self):
        """Test DAG engine statistics."""
        engine = DAGExecutionEngine()

        stats = engine.get_stats()

        assert "tasks_submitted" in stats
        assert "tasks_completed" in stats
        assert "running" in stats

    def test_shuffle_manager_stats(self):
        """Test shuffle manager statistics."""
        manager = ShuffleManager()

        stats = manager.get_stats()

        assert "shuffles_started" in stats
        assert "shuffles_completed" in stats

    def test_fault_tolerance_stats(self):
        """Test fault tolerance statistics."""
        manager = FaultToleranceManager()

        stats = manager.get_stats()

        assert "total_failures" in stats
        assert "checkpoints_created" in stats

    def test_progress_tracker_stats(self):
        """Test progress tracker statistics."""
        tracker = ProgressTracker()

        tracker.register_task("task-001", total_stages=1)

        progress = tracker.get_task_progress("task-001")
        assert progress is not None
