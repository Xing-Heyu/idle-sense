"""
Integration tests for sandbox execution with scheduler.

Tests the integration between:
- Sandbox execution
- Task scheduling
- Result handling
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestSandboxSchedulerIntegration:
    """Integration tests for sandbox and scheduler."""

    @pytest.fixture
    def sandbox(self):
        """Create a sandbox instance."""
        try:
            from src.infrastructure.sandbox.sandbox import BasicSandbox, SandboxConfig

            return BasicSandbox(SandboxConfig(timeout=60))
        except ImportError:
            from legacy.sandbox import CodeSandbox

            return CodeSandbox()

    @pytest.fixture
    def scheduler(self):
        """Create a scheduler instance."""
        from src.infrastructure.scheduler.scheduler import NodeInfo, SimpleScheduler

        scheduler = SimpleScheduler()
        node = NodeInfo(
            node_id="test-node",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 4.0, "memory": 8192},
            is_idle=True,
            is_available=True,
        )
        scheduler.register_node(node)
        scheduler.update_node_heartbeat("test-node", {})
        return scheduler

    def test_sandbox_code_validation(self, sandbox):
        """Test sandbox code validation."""
        safe_code = "result = 1 + 1"
        result = (
            sandbox.validate_code(safe_code)
            if hasattr(sandbox, "validate_code")
            else sandbox.check_code_safety(safe_code)
        )
        if isinstance(result, dict):
            assert result.get("safe", result.get("is_safe", False))
        else:
            assert result.is_safe

    def test_sandbox_dangerous_code_blocked(self, sandbox):
        """Test that dangerous code is blocked."""
        dangerous_code = "import os; os.system('rm -rf /')"
        result = (
            sandbox.validate_code(dangerous_code)
            if hasattr(sandbox, "validate_code")
            else sandbox.check_code_safety(dangerous_code)
        )
        if isinstance(result, dict):
            assert not result.get("safe", result.get("is_safe", True))
        else:
            assert not result.is_safe

    def test_sandbox_execution(self, sandbox):
        """Test sandbox code execution."""
        code = "print('Hello, World!')"
        result = sandbox.execute(code)
        if hasattr(result, "success"):
            assert result.success
            assert "Hello, World!" in result.output
        else:
            assert result.get("success")

    def test_scheduler_task_assignment(self, scheduler):
        """Test scheduler task assignment."""
        from src.infrastructure.scheduler.scheduler import TaskInfo

        task = TaskInfo(
            task_id=0,
            code="result = 1 + 1",
            required_resources={"cpu": 1.0, "memory": 512},
            status="pending",
        )
        task_id = scheduler.add_task(task)
        assert task_id is not None

        assert task_id in scheduler.tasks

    def test_scheduler_node_management(self, scheduler):
        """Test scheduler node management."""
        from src.infrastructure.scheduler.scheduler import NodeInfo

        node = NodeInfo(
            node_id="new-node",
            capacity={"cpu": 8.0, "memory": 16384},
            available_resources={"cpu": 8.0, "memory": 16384},
        )
        result = scheduler.register_node(node)
        assert result

        nodes = scheduler.get_available_nodes()
        assert len(nodes) >= 2


class TestIdleDetectionIntegration:
    """Integration tests for idle detection."""

    def test_idle_detection_basic(self):
        """Test basic idle detection."""
        from legacy.idle_sense import get_system_status, is_idle

        result = is_idle()
        assert isinstance(result, bool)

        status = get_system_status()
        assert isinstance(status, dict)
        assert "idle" in status or "is_user_idle" in status

    def test_idle_detection_with_thresholds(self):
        """Test idle detection with custom thresholds."""
        from legacy.idle_sense import get_system_status, is_idle

        result = is_idle(idle_threshold_sec=60, cpu_threshold=50.0, memory_threshold=80.0)
        assert isinstance(result, bool)

        status = get_system_status(idle_threshold_sec=60, cpu_threshold=50.0, memory_threshold=80.0)
        assert isinstance(status, dict)


class TestStorageIntegration:
    """Integration tests for storage backends."""

    @pytest.mark.asyncio
    async def test_memory_storage_full_flow(self):
        """Test complete storage flow."""
        from legacy.storage import MemoryStorage, NodeInfo, NodeStatus, TaskInfo, TaskStatus

        storage = MemoryStorage()

        task = TaskInfo(task_id=0, code="result = 1")
        await storage.store_task(task)
        assert task.task_id > 0

        node = NodeInfo(
            node_id="test-node",
            capacity={"cpu": 4.0, "memory": 8192},
            status=NodeStatus.ONLINE_AVAILABLE,
        )
        await storage.store_node(node)

        stats = await storage.get_stats()
        assert stats["total_tasks"] == 1
        assert stats["total_nodes"] == 1

        await storage.update_task(task.task_id, {"status": TaskStatus.COMPLETED, "result": "1"})
        updated_task = await storage.get_task(task.task_id)
        assert updated_task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_storage_task_filtering(self):
        """Test storage task filtering."""
        from legacy.storage import MemoryStorage, TaskInfo

        storage = MemoryStorage()

        for i in range(5):
            task = TaskInfo(task_id=0, code=f"result = {i}")
            await storage.store_task(task)

        all_tasks = await storage.list_tasks()
        assert len(all_tasks) == 5


class TestTokenEconomyIntegration:
    """Integration tests for token economy."""

    def test_pricing_engine(self):
        """Test pricing engine."""
        from legacy.token_economy import PricingEngine, ResourceMetrics

        engine = PricingEngine()
        resources = ResourceMetrics(
            cpu_seconds=100, memory_gb_seconds=0.05, storage_gb=0.1, network_gb=0.01, gpu_seconds=0
        )
        price = engine.calculate_price(resources, priority=1)
        assert price > 0

    def test_reputation_system(self):
        """Test reputation system."""
        from legacy.token_economy import Account, ReputationAction, ReputationSystem

        system = ReputationSystem()
        account = Account(address="node-1", balance=0)

        system.update_reputation(account, ReputationAction.TASK_COMPLETED)
        system.update_reputation(account, ReputationAction.TASK_COMPLETED)
        system.update_reputation(account, ReputationAction.TASK_FAILED)

        assert 0 <= account.reputation <= 100


class TestP2PNetworkIntegration:
    """Integration tests for P2P network."""

    def test_dht_basic_operations(self):
        """Test DHT basic operations."""
        from legacy.p2p_network import KademliaDHT

        dht = KademliaDHT(node_id="test-node-001")
        dht.store("test_key", "test_value")

        value = dht.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_gossip_protocol(self):
        """Test gossip protocol."""
        from legacy.p2p_network import GossipProtocol, KademliaDHT

        dht = KademliaDHT(node_id="test-node-001")
        protocol = GossipProtocol(node_id="test-node-001", dht=dht)
        await protocol.broadcast("test_message", ["node-2", "node-3"])

        assert protocol.node_id == "test-node-001"
