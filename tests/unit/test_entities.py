"""
单元测试 - 核心实体测试

测试 User, Task, Node, Folder 实体的功能
"""

import pytest

from src.core.entities import Folder, FolderType, Node, NodeStatus, Task, TaskStatus, User


class TestUser:
    """User实体测试"""

    def test_create_user(self):
        """测试创建用户"""
        user = User(user_id="test_001", username="testuser")
        assert user.user_id == "test_001"
        assert user.username == "testuser"
        assert user.folder_location == "project"

    def test_validate_username(self):
        """测试用户名验证"""
        user = User(user_id="test", username="validuser")
        is_valid, msg = user.validate()
        assert is_valid is True

        user = User(user_id="test", username="a" * 21)
        is_valid, msg = user.validate()
        assert is_valid is False
        assert "20个字符" in msg

    def test_update_last_login(self):
        """测试更新登录时间"""
        user = User(user_id="test", username="test")
        assert user.last_login is None
        user.update_last_login()
        assert user.last_login is not None

    def test_to_dict(self):
        """测试转换为字典"""
        user = User(user_id="test", username="test")
        data = user.to_dict()
        assert data["user_id"] == "test"
        assert data["username"] == "test"

    def test_from_dict(self):
        """测试从字典创建"""
        data = {"user_id": "test", "username": "test", "folder_location": "project"}
        user = User.from_dict(data)
        assert user.user_id == "test"
        assert user.username == "test"


class TestTask:
    """Task实体测试"""

    def test_create_task(self):
        """测试创建任务"""
        task = Task(code="print('hello')", timeout=300)
        assert task.code == "print('hello')"
        assert task.timeout == 300
        assert task.status == TaskStatus.PENDING

    def test_task_status_transitions(self):
        """测试任务状态转换"""
        task = Task(code="test")

        assert task.status == TaskStatus.PENDING
        assert not task.is_running

        task.start("node_001")
        assert task.status == TaskStatus.RUNNING
        assert task.is_running
        assert task.assigned_node == "node_001"

        task.complete("success")
        assert task.status == TaskStatus.COMPLETED
        assert task.is_completed
        assert task.result == "success"

    def test_task_fail(self):
        """测试任务失败"""
        task = Task(code="test")
        task.fail("error message")
        assert task.status == TaskStatus.FAILED
        assert task.error == "error message"

    def test_task_duration(self):
        """测试任务执行时长"""
        task = Task(code="test")
        task.start("node_001")
        import time

        time.sleep(0.01)
        task.complete("done")

        assert task.duration is not None
        assert task.duration > 0


class TestNode:
    """Node实体测试"""

    def test_create_node(self):
        """测试创建节点"""
        node = Node(node_id="node_001", platform="windows")
        assert node.node_id == "node_001"
        assert node.platform == "windows"
        assert node.status == NodeStatus.OFFLINE

    def test_node_status_transitions(self):
        """测试节点状态转换"""
        node = Node(node_id="test")

        node.go_online()
        assert node.status == NodeStatus.ONLINE
        assert node.is_online

        node.set_idle()
        assert node.status == NodeStatus.IDLE
        assert node.is_idle
        assert node.is_available_for_task

        node.set_busy()
        assert node.status == NodeStatus.BUSY
        assert not node.is_idle

        node.go_offline()
        assert node.status == NodeStatus.OFFLINE
        assert not node.is_online


class TestFolder:
    """Folder实体测试"""

    def test_create_folder(self):
        """测试创建文件夹"""
        folder = Folder(folder_type=FolderType.USER_DATA, path="/tmp/test", user_id="user_001")
        assert folder.folder_type == FolderType.USER_DATA
        assert folder.path == "/tmp/test"
        assert folder.user_id == "user_001"

    def test_folder_properties(self):
        """测试文件夹属性"""
        folder = Folder(folder_type=FolderType.USER_DATA, path="/tmp/test", user_id="user_001")
        assert folder.name == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
