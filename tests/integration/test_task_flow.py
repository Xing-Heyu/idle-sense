"""Integration tests for task flow."""
import time

import pytest

from legacy.storage import MemoryStorage, NodeInfo, NodeStatus, TaskInfo, TaskStatus


class TestTaskSubmissionFlow:
    """Integration tests for task submission flow."""

    @pytest.fixture
    def storage(self):
        """Create a storage instance."""
        return MemoryStorage()

    @pytest.mark.asyncio
    async def test_complete_task_flow(self, storage):
        """Test complete task flow: submit -> assign -> execute -> complete."""
        task = TaskInfo(
            task_id=0,
            code="result = 1 + 1",
            resources={"cpu": 1.0, "memory": 512}
        )

        await storage.store_task(task)
        assert task.task_id > 0

        node = NodeInfo(
            node_id="test-node-001",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 4.0, "memory": 8192},
            is_idle=True,
            status=NodeStatus.ONLINE_AVAILABLE
        )
        await storage.store_node(node)

        assigned_task = await storage.get_pending_task_for_node("test-node-001")
        assert assigned_task is not None
        assert assigned_task.task_id == task.task_id
        assert assigned_task.status == TaskStatus.ASSIGNED

        await storage.update_task(task.task_id, {
            "status": TaskStatus.RUNNING
        })

        await storage.update_task(task.task_id, {
            "status": TaskStatus.COMPLETED,
            "result": "2",
            "completed_at": time.time()
        })

        completed_task = await storage.get_task(task.task_id)
        assert completed_task.status == TaskStatus.COMPLETED
        assert completed_task.result == "2"

    @pytest.mark.asyncio
    async def test_multiple_tasks_scheduling(self, storage):
        """Test scheduling multiple tasks to multiple nodes."""
        tasks = []
        for i in range(5):
            task = TaskInfo(
                task_id=0,
                code=f"result = {i} * 2",
                resources={"cpu": 1.0, "memory": 512}
            )
            await storage.store_task(task)
            tasks.append(task)

        nodes = []
        for i in range(3):
            node = NodeInfo(
                node_id=f"node-{i:03d}",
                capacity={"cpu": 2.0, "memory": 4096},
                available_resources={"cpu": 2.0, "memory": 4096},
                is_idle=True,
                status=NodeStatus.ONLINE_AVAILABLE
            )
            await storage.store_node(node)
            nodes.append(node)

        assigned_count = 0
        for node in nodes:
            task = await storage.get_pending_task_for_node(node.node_id)
            if task:
                assigned_count += 1

        assert assigned_count >= 3

    @pytest.mark.asyncio
    async def test_task_failure_and_retry(self, storage):
        """Test task failure handling."""
        task = TaskInfo(
            task_id=0,
            code="raise ValueError('test error')",
            resources={"cpu": 1.0, "memory": 512}
        )
        await storage.store_task(task)

        node = NodeInfo(
            node_id="test-node-001",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 4.0, "memory": 8192},
            is_idle=True,
            status=NodeStatus.ONLINE_AVAILABLE
        )
        await storage.store_node(node)

        assigned_task = await storage.get_pending_task_for_node("test-node-001")
        assert assigned_task is not None

        await storage.update_task(task.task_id, {
            "status": TaskStatus.FAILED,
            "error": "ValueError: test error"
        })

        failed_task = await storage.get_task(task.task_id)
        assert failed_task.status == TaskStatus.FAILED
        assert "ValueError" in failed_task.error


class TestNodeLifecycle:
    """Integration tests for node lifecycle."""

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.mark.asyncio
    async def test_node_registration_and_heartbeat(self, storage):
        """Test node registration and heartbeat updates."""
        node = NodeInfo(
            node_id="node-001",
            capacity={"cpu": 4.0, "memory": 8192},
            status=NodeStatus.ONLINE_AVAILABLE
        )
        await storage.store_node(node)

        stored_node = await storage.get_node("node-001")
        assert stored_node is not None
        assert stored_node.node_id == "node-001"

        await storage.update_node("node-001", {
            "last_heartbeat": time.time(),
            "cpu_usage": 25.0,
            "memory_usage": 40.0,
            "is_idle": True
        })

        updated_node = await storage.get_node("node-001")
        assert updated_node.cpu_usage == 25.0
        assert updated_node.is_idle is True

    @pytest.mark.asyncio
    async def test_node_offline_detection(self, storage):
        """Test offline node detection."""
        node = NodeInfo(
            node_id="node-001",
            capacity={"cpu": 4.0, "memory": 8192},
            last_heartbeat=time.time() - 200,
            status=NodeStatus.ONLINE_AVAILABLE
        )
        await storage.store_node(node)

        old_heartbeat = time.time() - 200
        await storage.update_node("node-001", {
            "last_heartbeat": old_heartbeat
        })

        stats = await storage.get_stats()
        assert stats["total_nodes"] == 1


class TestResourceMatching:
    """Integration tests for resource matching."""

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.mark.asyncio
    async def test_resource_fit_matching(self, storage):
        """Test that tasks are matched to nodes with sufficient resources."""
        high_resource_task = TaskInfo(
            task_id=0,
            code="result = 'high resource task'",
            resources={"cpu": 4.0, "memory": 8192}
        )
        await storage.store_task(high_resource_task)

        low_resource_task = TaskInfo(
            task_id=0,
            code="result = 'low resource task'",
            resources={"cpu": 0.5, "memory": 128}
        )
        await storage.store_task(low_resource_task)

        small_node = NodeInfo(
            node_id="small-node",
            capacity={"cpu": 2.0, "memory": 2048},
            available_resources={"cpu": 1.5, "memory": 1500},
            is_idle=True,
            status=NodeStatus.ONLINE_AVAILABLE
        )
        await storage.store_node(small_node)

        large_node = NodeInfo(
            node_id="large-node",
            capacity={"cpu": 8.0, "memory": 16384},
            available_resources={"cpu": 6.0, "memory": 12000},
            is_idle=True,
            status=NodeStatus.ONLINE_AVAILABLE
        )
        await storage.store_node(large_node)

        task_for_small = await storage.get_pending_task_for_node("small-node")
        assert task_for_small is not None
        assert "low resource" in task_for_small.code

    @pytest.mark.asyncio
    async def test_no_match_for_insufficient_resources(self, storage):
        """Test that no task is assigned when resources are insufficient."""
        heavy_task = TaskInfo(
            task_id=0,
            code="result = 'heavy task'",
            resources={"cpu": 16.0, "memory": 32768}
        )
        await storage.store_task(heavy_task)

        small_node = NodeInfo(
            node_id="small-node",
            capacity={"cpu": 2.0, "memory": 2048},
            available_resources={"cpu": 2.0, "memory": 2048},
            is_idle=True,
            status=NodeStatus.ONLINE_AVAILABLE
        )
        await storage.store_node(small_node)

        task = await storage.get_pending_task_for_node("small-node")
        assert task is None


class TestStatistics:
    """Integration tests for statistics."""

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.mark.asyncio
    async def test_task_statistics(self, storage):
        """Test task statistics calculation."""
        for i in range(10):
            task = TaskInfo(
                task_id=0,
                code=f"result = {i}",
                status=TaskStatus.PENDING if i < 5 else TaskStatus.COMPLETED
            )
            if task.status == TaskStatus.COMPLETED:
                task.completed_at = time.time()
            await storage.store_task(task)

        stats = await storage.get_stats()
        assert stats["total_tasks"] == 10
        assert stats["pending_tasks"] == 5
        assert stats["completed_tasks"] == 5

    @pytest.mark.asyncio
    async def test_node_statistics(self, storage):
        """Test node statistics calculation."""
        for i in range(5):
            node = NodeInfo(
                node_id=f"node-{i}",
                capacity={"cpu": 4.0, "memory": 8192},
                status=NodeStatus.ONLINE_AVAILABLE if i < 3 else NodeStatus.OFFLINE
            )
            await storage.store_node(node)

        stats = await storage.get_stats()
        assert stats["total_nodes"] == 5
        assert stats["available_nodes"] == 3
        assert stats["offline_nodes"] == 2
