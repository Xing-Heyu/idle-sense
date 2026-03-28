"""
单元测试 - 用例测试

测试 LoginUseCase, SubmitTaskUseCase 等用例
"""

from unittest.mock import Mock

import pytest

from src.core.use_cases.auth.login_use_case import LoginRequest, LoginUseCase
from src.core.use_cases.auth.register_use_case import RegisterRequest, RegisterUseCase
from src.core.use_cases.task.submit_task_use_case import SubmitTaskRequest, SubmitTaskUseCase


class TestLoginUseCase:
    """登录用例测试"""

    def setup_method(self):
        self.mock_repo = Mock()
        self.use_case = LoginUseCase(self.mock_repo)

    def test_login_success(self):
        """测试登录成功"""
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_user.user_id = "local_test123"
        self.mock_repo.get_by_username.return_value = mock_user

        request = LoginRequest(username_or_id="testuser")
        response = self.use_case.execute(request)

        assert response.success is True
        assert response.username == "testuser"
        self.mock_repo.update.assert_called_once()

    def test_login_user_not_found(self):
        """测试用户不存在"""
        self.mock_repo.get_by_username.return_value = None
        self.mock_repo.get_by_id.return_value = None

        request = LoginRequest(username_or_id="notexist")
        response = self.use_case.execute(request)

        assert response.success is False
        assert "不存在" in response.message

    def test_login_with_user_id(self):
        """测试使用用户ID登录"""
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_user.user_id = "local_abc123"
        mock_user.update_last_login = Mock()
        self.mock_repo.get_by_username.return_value = None
        self.mock_repo.get_by_id.return_value = mock_user

        request = LoginRequest(username_or_id="local_abc123")
        response = self.use_case.execute(request)

        assert response.success is True
        assert response.user_id == "local_abc123"
        self.mock_repo.update.assert_called_once()

    def test_login_empty_username(self):
        """测试空用户名"""
        self.mock_repo.get_by_username.return_value = None
        self.mock_repo.get_by_id.return_value = None

        request = LoginRequest(username_or_id="")
        response = self.use_case.execute(request)

        assert response.success is False


class TestRegisterUseCase:
    """注册用例测试"""

    def setup_method(self):
        self.mock_repo = Mock()
        self.mock_repo.find_available_username.return_value = "newuser"
        self.mock_repo.save.return_value = Mock()
        self.use_case = RegisterUseCase(self.mock_repo)

    def test_register_success(self):
        """测试注册成功"""
        request = RegisterRequest(username="newuser", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is True
        self.mock_repo.save.assert_called_once()

    def test_register_invalid_username(self):
        """测试无效用户名"""
        request = RegisterRequest(username="a" * 25, folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False

    def test_register_username_with_special_chars(self):
        """测试用户名包含特殊字符"""
        request = RegisterRequest(username="test@user!", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False

    def test_register_empty_username(self):
        """测试空用户名"""
        request = RegisterRequest(username="", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False

    def test_register_username_too_long(self):
        """测试用户名过长"""
        request = RegisterRequest(username="a" * 21, folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False


class TestSubmitTaskUseCase:
    """提交任务用例测试"""

    def setup_method(self):
        self.mock_repo = Mock()
        self.mock_scheduler = Mock()
        self.use_case = SubmitTaskUseCase(self.mock_repo, self.mock_scheduler)

    def test_submit_task_success(self):
        """测试提交任务成功"""
        self.mock_scheduler.submit_task.return_value = (True, {"task_id": "task_123"})

        request = SubmitTaskRequest(code="print('hello')", timeout=300)
        response = self.use_case.execute(request)

        assert response.success is True
        assert response.task_id == "task_123"
        self.mock_repo.save.assert_called_once()

    def test_submit_task_failure(self):
        """测试提交任务失败"""
        self.mock_scheduler.submit_task.return_value = (False, {"error": "Scheduler offline"})

        request = SubmitTaskRequest(code="print('hello')")
        response = self.use_case.execute(request)

        assert response.success is False
        assert "失败" in response.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
