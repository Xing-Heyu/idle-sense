"""
单元测试 - 权限服务测试

测试 PermissionService
"""

import os
from unittest.mock import patch

import pytest

from src.core.services.permission_service import PermissionService


class TestPermissionService:
    """权限服务测试"""

    def setup_method(self):
        self.service = PermissionService()

    def test_check_admin_permission_returns_bool(self):
        """测试管理员权限检查返回布尔值"""
        result = self.service.check_admin_permission()
        assert isinstance(result, (bool, int))

    def test_check_write_permission_success(self, tmp_path):
        """测试写入权限检查成功"""
        result = self.service.check_write_permission(str(tmp_path))
        assert result is True

    def test_check_write_permission_nonexistent_path(self):
        """测试写入权限检查不存在的路径"""
        result = self.service.check_write_permission("/nonexistent/path/12345")
        assert result is False

    def test_ensure_directory_with_permission_success(self, tmp_path):
        """测试确保目录权限成功"""
        test_path = str(tmp_path / "test_dir")
        success, message = self.service.ensure_directory_with_permission(test_path)

        assert success is True
        assert "通过" in message
        assert os.path.exists(test_path)

    def test_ensure_directory_with_permission_create_fail(self):
        """测试创建目录失败"""
        with patch("os.makedirs", side_effect=PermissionError("Access denied")):
            success, message = self.service.ensure_directory_with_permission("/nonexistent")

            assert success is False
            assert "权限不足" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
