"""
单元测试 - 持久化仓储测试

测试 SQLite 和 Redis 仓储实现
"""

import pytest

from src.core.entities import Node, NodeStatus, Task, TaskStatus
from src.infrastructure.repositories import (
    InMemoryNodeRepository,
    InMemoryTaskRepository,
    SQLiteNodeRepository,
    SQLiteTaskRepository,
)


class TestSQLiteNodeRepository:
    """SQLiteNodeRepository测试"""

    @pytest.fixture
    async def repo(self, tmp_path):
        db_path = str(tmp_path / "test_nodes.db")
        repository = SQLiteNodeRepository(db_path=db_path)
        yield repository
        await repository.close()

    @pytest.mark.asyncio
    async def test_save_and_get_node(self, repo):
        node = Node(
            node_id="node_001",
            platform="windows",
            status=NodeStatus.ONLINE,
            capacity={"cpu": 4, "memory": 8192},
            tags={"gpu": "true"},
            owner="user1",
        )

        saved = await repo.save(node)
        assert saved.node_id == "node_001"

        retrieved = await repo.get_by_id("node_001")
        assert retrieved is not None
        assert retrieved.node_id == "node_001"
        assert retrieved.platform == "windows"
        assert retrieved.status == NodeStatus.ONLINE
        assert retrieved.capacity == {"cpu": 4, "memory": 8192}

    @pytest.mark.asyncio
    async def test_update_node(self, repo):
        node = Node(node_id="node_001", status=NodeStatus.OFFLINE)
        await repo.save(node)

        node.status = NodeStatus.ONLINE
        node.is_idle = True
        await repo.update(node)

        retrieved = await repo.get_by_id("node_001")
        assert retrieved.status == NodeStatus.ONLINE
        assert retrieved.is_idle is True

    @pytest.mark.asyncio
    async def test_delete_node(self, repo):
        node = Node(node_id="node_001")
        await repo.save(node)

        result = await repo.delete("node_001")
        assert result is True

        retrieved = await repo.get_by_id("node_001")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_all(self, repo):
        await repo.save(Node(node_id="node_001", status=NodeStatus.ONLINE))
        await repo.save(Node(node_id="node_002", status=NodeStatus.OFFLINE))

        nodes = await repo.list_all()
        assert len(nodes) == 2

    @pytest.mark.asyncio
    async def test_list_by_status(self, repo):
        await repo.save(Node(node_id="node_001", status=NodeStatus.ONLINE))
        await repo.save(Node(node_id="node_002", status=NodeStatus.OFFLINE))
        await repo.save(Node(node_id="node_003", status=NodeStatus.ONLINE))

        online_nodes = await repo.list_by_status(NodeStatus.ONLINE)
        assert len(online_nodes) == 2

    @pytest.mark.asyncio
    async def test_list_online(self, repo):
        await repo.save(Node(node_id="node_001", status=NodeStatus.ONLINE))
        await repo.save(Node(node_id="node_002", status=NodeStatus.IDLE))
        await repo.save(Node(node_id="node_003", status=NodeStatus.OFFLINE))

        online_nodes = await repo.list_online()
        assert len(online_nodes) == 2

    @pytest.mark.asyncio
    async def test_list_idle(self, repo):
        await repo.save(Node(node_id="node_001", status=NodeStatus.IDLE, is_idle=True))
        await repo.save(Node(node_id="node_002", status=NodeStatus.ONLINE, is_idle=False))

        idle_nodes = await repo.list_idle()
        assert len(idle_nodes) == 1


class TestSQLiteTaskRepository:
    """SQLiteTaskRepository测试"""

    @pytest.fixture
    async def repo(self, tmp_path):
        db_path = str(tmp_path / "test_tasks.db")
        repository = SQLiteTaskRepository(db_path=db_path)
        yield repository
        await repository.close()

    @pytest.mark.asyncio
    async def test_save_and_get_task(self, repo):
        task = Task(
            task_id="task_001",
            code="print('hello')",
            status=TaskStatus.PENDING,
            user_id="user1",
            timeout=300,
            cpu_request=2.0,
            memory_request=1024,
        )

        saved = await repo.save(task)
        assert saved.task_id == "task_001"

        retrieved = await repo.get_by_id("task_001")
        assert retrieved is not None
        assert retrieved.task_id == "task_001"
        assert retrieved.code == "print('hello')"
        assert retrieved.status == TaskStatus.PENDING
        assert retrieved.user_id == "user1"

    @pytest.mark.asyncio
    async def test_update_task(self, repo):
        task = Task(task_id="task_001", code="test", status=TaskStatus.PENDING)
        await repo.save(task)

        task.status = TaskStatus.RUNNING
        task.assigned_node = "node_001"
        await repo.update(task)

        retrieved = await repo.get_by_id("task_001")
        assert retrieved.status == TaskStatus.RUNNING
        assert retrieved.assigned_node == "node_001"

    @pytest.mark.asyncio
    async def test_delete_task(self, repo):
        task = Task(task_id="task_001", code="test")
        await repo.save(task)

        result = await repo.delete("task_001")
        assert result is True

        retrieved = await repo.get_by_id("task_001")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_by_user(self, repo):
        await repo.save(Task(task_id="t1", code="test", user_id="user1"))
        await repo.save(Task(task_id="t2", code="test", user_id="user2"))
        await repo.save(Task(task_id="t3", code="test", user_id="user1"))

        tasks = await repo.list_by_user("user1")
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_list_by_status(self, repo):
        await repo.save(Task(task_id="t1", code="test", status=TaskStatus.PENDING))
        await repo.save(Task(task_id="t2", code="test", status=TaskStatus.RUNNING))
        await repo.save(Task(task_id="t3", code="test", status=TaskStatus.PENDING))

        pending_tasks = await repo.list_by_status(TaskStatus.PENDING)
        assert len(pending_tasks) == 2

    @pytest.mark.asyncio
    async def test_list_all(self, repo):
        await repo.save(Task(task_id="t1", code="test"))
        await repo.save(Task(task_id="t2", code="test"))

        tasks = await repo.list_all()
        assert len(tasks) == 2


class TestInMemoryNodeRepositoryAsync:
    """InMemoryNodeRepository同步接口测试（兼容性）"""

    def test_save_and_get_node(self):
        repo = InMemoryNodeRepository()
        node = Node(node_id="node_001", status=NodeStatus.ONLINE)

        saved = repo.save(node)
        assert saved.node_id == "node_001"

        retrieved = repo.get_by_id("node_001")
        assert retrieved.node_id == "node_001"

    def test_list_by_status(self):
        repo = InMemoryNodeRepository()
        repo.save(Node(node_id="n1", status=NodeStatus.ONLINE))
        repo.save(Node(node_id="n2", status=NodeStatus.OFFLINE))

        online = repo.list_by_status(NodeStatus.ONLINE)
        assert len(online) == 1

    def test_list_online(self):
        repo = InMemoryNodeRepository()
        repo.save(Node(node_id="n1", status=NodeStatus.ONLINE))
        repo.save(Node(node_id="n2", status=NodeStatus.IDLE))
        repo.save(Node(node_id="n3", status=NodeStatus.OFFLINE))

        online = repo.list_online()
        assert len(online) == 2

    def test_list_idle(self):
        repo = InMemoryNodeRepository()
        repo.save(Node(node_id="n1", status=NodeStatus.IDLE, is_idle=True))
        repo.save(Node(node_id="n2", status=NodeStatus.ONLINE, is_idle=False))

        idle = repo.list_idle()
        assert len(idle) == 1


class TestInMemoryTaskRepositoryAsync:
    """InMemoryTaskRepository同步接口测试（兼容性）"""

    def test_save_and_get_task(self):
        repo = InMemoryTaskRepository()
        task = Task(task_id="task_001", code="test", status=TaskStatus.PENDING)

        saved = repo.save(task)
        assert saved.task_id == "task_001"

        retrieved = repo.get_by_id("task_001")
        assert retrieved.task_id == "task_001"

    def test_list_by_user(self):
        repo = InMemoryTaskRepository()
        repo.save(Task(task_id="t1", code="test", user_id="u1"))
        repo.save(Task(task_id="t2", code="test", user_id="u2"))

        tasks = repo.list_by_user("u1")
        assert len(tasks) == 1

    def test_list_by_status(self):
        repo = InMemoryTaskRepository()
        repo.save(Task(task_id="t1", code="test", status=TaskStatus.PENDING))
        repo.save(Task(task_id="t2", code="test", status=TaskStatus.RUNNING))

        pending = repo.list_by_status(TaskStatus.PENDING)
        assert len(pending) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
