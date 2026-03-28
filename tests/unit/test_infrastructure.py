"""
单元测试 - 基础设施测试

测试仓储实现和工具函数
"""

import shutil
import tempfile

import pytest

from src.core.entities import Node, Task
from src.infrastructure.repositories import (
    FileUserRepository,
    InMemoryNodeRepository,
    InMemoryTaskRepository,
)
from src.infrastructure.utils import MemoryCache


class TestFileUserRepository:
    """FileUserRepository测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo = FileUserRepository(users_dir=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_get_user(self):
        """测试保存和获取用户"""
        from src.core.entities import User
        user = User(user_id="test_001", username="testuser")

        saved = self.repo.save(user)
        assert saved.user_id == "test_001"

        retrieved = self.repo.get_by_id("test_001")
        assert retrieved.username == "testuser"

    def test_get_by_username(self):
        """测试按用户名获取"""
        from src.core.entities import User
        user = User(user_id="test_001", username="testuser")
        self.repo.save(user)

        retrieved = self.repo.get_by_username("testuser")
        assert retrieved is not None
        assert retrieved.username == "testuser"

    def test_list_users(self):
        """测试列出所有用户"""
        from src.core.entities import User
        self.repo.save(User(user_id="u1", username="user1"))
        self.repo.save(User(user_id="u2", username="user2"))

        users = self.repo.list_all()
        assert len(users) == 2

    def test_delete_user(self):
        """测试删除用户"""
        from src.core.entities import User
        user = User(user_id="test_001", username="testuser")
        self.repo.save(user)

        result = self.repo.delete("test_001")
        assert result is True

        retrieved = self.repo.get_by_id("test_001")
        assert retrieved is None


class TestInMemoryTaskRepository:
    """InMemoryTaskRepository测试"""

    def setup_method(self):
        self.repo = InMemoryTaskRepository()

    def test_save_and_get_task(self):
        """测试保存和获取任务"""
        task = Task(code="test", task_id="task_001")

        saved = self.repo.save(task)
        assert saved.task_id == "task_001"

        retrieved = self.repo.get_by_id("task_001")
        assert retrieved.code == "test"

    def test_list_tasks(self):
        """测试列出任务"""
        self.repo.save(Task(code="test1", task_id="t1", user_id="u1"))
        self.repo.save(Task(code="test2", task_id="t2", user_id="u2"))

        tasks = self.repo.list_all()
        assert len(tasks) == 2

    def test_list_by_user(self):
        """测试按用户列出任务"""
        self.repo.save(Task(code="test", task_id="t1", user_id="u1"))
        self.repo.save(Task(code="test", task_id="t2", user_id="u2"))

        tasks = self.repo.list_by_user("u1")
        assert len(tasks) == 1
        assert tasks[0].user_id == "u1"


class TestInMemoryNodeRepository:
    """InMemoryNodeRepository测试"""

    def setup_method(self):
        self.repo = InMemoryNodeRepository()

    def test_save_and_get_node(self):
        """测试保存和获取节点"""
        node = Node(node_id="node_001")

        saved = self.repo.save(node)
        assert saved.node_id == "node_001"

        retrieved = self.repo.get_by_id("node_001")
        assert retrieved.node_id == "node_001"


class TestMemoryCache:
    """MemoryCache测试"""

    def setup_method(self):
        self.cache = MemoryCache(max_size=10, default_ttl=60)

    def test_set_and_get(self):
        """测试设置和获取"""
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        """测试获取不存在的键"""
        assert self.cache.get("nonexistent") is None

    def test_delete(self):
        """测试删除"""
        self.cache.set("key1", "value1")
        self.cache.delete("key1")
        assert self.cache.get("key1") is None

    def test_clear(self):
        """测试清空"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.clear()
        assert len(self.cache) == 0

    def test_stats(self):
        """测试统计"""
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        self.cache.get("nonexistent")

        stats = self.cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
