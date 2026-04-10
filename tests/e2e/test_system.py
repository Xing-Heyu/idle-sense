"""End-to-end tests for the complete system."""

import time

import pytest


class TestEndToEndTaskExecution:
    """End-to-end tests for task execution."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_submit_and_execute_task(self, scheduler_url):
        """Test submitting a task and getting the result."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests not installed")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        task_data = {
            "code": "result = sum(range(100))\n__result__ = result",
            "timeout": 60,
            "resources": {"cpu": 1.0, "memory": 512},
        }

        response = requests.post(f"{scheduler_url}/submit", json=task_data, timeout=10)

        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result

        task_id = result["task_id"]

        max_wait = 60
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = requests.get(f"{scheduler_url}/status/{task_id}", timeout=5)

            if response.status_code == 200:
                status = response.json()
                if status.get("status") in ["completed", "failed"]:
                    break

            time.sleep(2)

        response = requests.get(f"{scheduler_url}/status/{task_id}", timeout=5)
        assert response.status_code == 200

        final_status = response.json()
        assert final_status.get("status") == "completed"
        assert final_status.get("result") == "4950"

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_node_registration_and_task_assignment(self, scheduler_url):
        """Test node registration and task assignment."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests not installed")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        node_data = {
            "node_id": f"test-node-{int(time.time())}",
            "capacity": {"cpu": 4.0, "memory": 8192},
            "tags": {"test": True},
        }

        response = requests.post(f"{scheduler_url}/api/nodes/register", json=node_data, timeout=10)

        assert response.status_code == 200

        response = requests.get(f"{scheduler_url}/api/nodes", timeout=5)
        assert response.status_code == 200

        nodes = response.json()
        assert isinstance(nodes, list)


class TestEndToEndDistributedTask:
    """End-to-end tests for distributed tasks."""

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_map_reduce_task(self):
        """Test Map-Reduce distributed task execution."""
        try:
            from legacy.distributed_task_v2 import (
                DistributedTaskBuilder,
                create_task_from_template,
            )
        except ImportError:
            pytest.skip("distributed_task_v2 not available")

        data = list(range(100))

        task = (
            DistributedTaskBuilder("test-mr-001", "Test MapReduce")
            .add_map_stage(
                "map-stage", "result = [x * 2 for x in data]", data=data, partition_count=4
            )
            .add_reduce_stage("reduce-stage", "result = sum(results)", dependencies=["map-stage"])
            .build()
        )

        assert len(task.stages) == 2
        assert len(task.stages[0].chunks) == 4

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_parallel_search_task(self):
        """Test parallel search task."""
        try:
            from legacy.distributed_task_v2 import create_task_from_template
        except ImportError:
            pytest.skip("distributed_task_v2 not available")

        data = list(range(1000))

        task = create_task_from_template(
            template_name="parallel_search",
            task_id="search-001",
            data=data,
            code_templates={
                "Search": "result = [x for x in data if x % 100 == 0]",
                "Merge": "result = list(set([item for sublist in results for item in sublist]))",
            },
            partition_count=4,
        )

        assert task.task_id == "search-001"
        assert len(task.stages) == 2


class TestEndToEndSecurity:
    """End-to-end security tests."""

    @pytest.mark.e2e
    def test_sandbox_blocks_dangerous_code(self):
        """Test that sandbox blocks dangerous code."""
        try:
            from legacy.sandbox_v2 import SandboxLevel, SecureSandbox
        except ImportError:
            pytest.skip("sandbox_v2 not available")

        sandbox = SecureSandbox(level=SandboxLevel.BASIC)

        dangerous_codes = [
            "import os\nos.system('echo hacked')",
            "open('/etc/passwd', 'r')",
            "__import__('subprocess').run(['ls'])",
            'eval(\'__import__("os").system("ls")\')',
        ]

        for code in dangerous_codes:
            result = sandbox.execute(code)
            assert result.success is False, f"Should block: {code}"

    @pytest.mark.e2e
    def test_sandbox_allows_safe_code(self):
        """Test that sandbox allows safe code."""
        try:
            from legacy.sandbox_v2 import SandboxLevel, SecureSandbox
        except ImportError:
            pytest.skip("sandbox_v2 not available")

        sandbox = SecureSandbox(level=SandboxLevel.BASIC)

        safe_codes = [
            "result = 1 + 1\n__result__ = result",
            "import math\nresult = math.sqrt(16)\n__result__ = result",
            "data = [1, 2, 3, 4, 5]\nresult = sum(data)\n__result__ = result",
        ]

        for code in safe_codes:
            result = sandbox.execute(code)
            assert result.success is True, f"Should allow: {code}"


class TestEndToEndWebSocket:
    """End-to-end WebSocket tests."""

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection to scheduler."""
        try:
            from legacy.websocket_comm import (
                MessageType,
                NodeWebSocketClient,
                WebSocketMessage,
            )
        except ImportError:
            pytest.skip("websocket_comm not available")

        client = NodeWebSocketClient(scheduler_url="ws://localhost:8000", node_id="test-ws-node")

        connected = await client.connect()

        if not connected:
            pytest.skip("Could not connect to scheduler WebSocket")

        try:
            sent = await client.send_heartbeat(is_idle=True, cpu_usage=10.0, memory_usage=30.0)
            assert sent is True

            message = await client.receive_message()
            assert message is not None
            assert message.type in [MessageType.HEARTBEAT_ACK, MessageType.PONG]

        finally:
            await client.disconnect()


class TestEndToEndStorage:
    """End-to-end storage tests."""

    @pytest.mark.asyncio
    async def test_memory_storage_operations(self):
        """Test memory storage operations."""
        from legacy.storage import MemoryStorage, NodeInfo, TaskInfo

        storage = MemoryStorage()

        task = TaskInfo(task_id=0, code="print('test')")
        await storage.store_task(task)

        retrieved = await storage.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.code == "print('test')"

        node = NodeInfo(node_id="test-node")
        await storage.store_node(node)

        retrieved_node = await storage.get_node("test-node")
        assert retrieved_node is not None

        stats = await storage.get_stats()
        assert stats["total_tasks"] == 1
        assert stats["total_nodes"] == 1

    @pytest.mark.asyncio
    async def test_storage_task_lifecycle(self):
        """Test task lifecycle in storage."""
        from legacy.storage import MemoryStorage, TaskInfo, TaskStatus

        storage = MemoryStorage()

        task = TaskInfo(task_id=0, code="result = 1")
        await storage.store_task(task)

        assert task.status == TaskStatus.PENDING

        await storage.update_task(task.task_id, {"status": TaskStatus.RUNNING})
        task = await storage.get_task(task.task_id)
        assert task.status == TaskStatus.RUNNING

        await storage.update_task(task.task_id, {"status": TaskStatus.COMPLETED, "result": "1"})
        task = await storage.get_task(task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "1"
