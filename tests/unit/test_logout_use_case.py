"""
LogoutUseCase 单元测试
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.core.entities.user import User
from src.core.use_cases.auth.logout_use_case import LogoutRequest, LogoutUseCase


class TestLogoutUseCase:
    """测试登出用例"""

    def setup_method(self):
        """测试前置设置"""
        self.user_repository = Mock()
        self.use_case = LogoutUseCase(self.user_repository)

    def test_logout_existing_user(self):
        """测试正常登出存在的用户"""
        # Arrange
        user = User(
            user_id="user123",
            username="testuser",
            created_at=datetime.now(),
            folder_location="project"
        )
        self.user_repository.get_by_id.return_value = user

        request = LogoutRequest(user_id="user123")

        # Act
        response = self.use_case.execute(request)

        # Assert
        assert response.success is True
        assert "testuser" in response.message
        assert "登出成功" in response.message
        assert response.logout_time is not None
        self.user_repository.get_by_id.assert_called_once_with("user123")

    def test_logout_nonexistent_user(self):
        """测试登出不存在的用户"""
        # Arrange
        self.user_repository.get_by_id.return_value = None

        request = LogoutRequest(user_id="nonexistent")

        # Act
        response = self.use_case.execute(request)

        # Assert
        assert response.success is False
        assert "不存在" in response.message
        assert response.logout_time is None

    def test_logout_with_session_id(self):
        """测试带会话ID的登出"""
        # Arrange
        user = User(
            user_id="user456",
            username="sessionuser",
            created_at=datetime.now()
        )
        self.user_repository.get_by_id.return_value = user

        request = LogoutRequest(
            user_id="user456",
            session_id="session_abc_123"
        )

        # Act
        response = self.use_case.execute(request)

        # Assert
        assert response.success is True
        # 目前 session_id 只是预留字段，用例不处理它
        # 未来可以扩展为验证会话有效性


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
