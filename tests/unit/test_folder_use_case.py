"""
单元测试 - 文件夹用例和服务测试

测试 FolderService 和 CreateFoldersUseCase
"""

import json
import os
from unittest.mock import Mock, patch

import pytest

from src.core.use_cases.system.create_folders_use_case import (
    CreateFoldersRequest,
    CreateFoldersUseCase,
    FolderService,
)


class TestFolderService:
    """文件夹服务测试"""

    def test_get_base_path_project(self):
        """测试项目目录路径"""
        path = FolderService.get_base_path("project")
        assert path.endswith("node_data")

    def test_get_base_path_c_drive(self):
        """测试C盘路径"""
        path = FolderService.get_base_path("c")
        assert path == "C:\\idle-sense-system-data"

    def test_get_base_path_d_drive(self):
        """测试D盘路径"""
        path = FolderService.get_base_path("d")
        assert path == "D:\\idle-sense-system-data"

    def test_get_base_path_default(self):
        """测试默认路径"""
        path = FolderService.get_base_path("unknown")
        assert path.endswith("node_data")

    def test_create_folder_structure(self, tmp_path):
        """测试创建文件夹结构"""
        base_path = str(tmp_path)
        folders = FolderService.create_folder_structure(base_path, "user123")

        assert os.path.exists(folders["user_system_dir"])
        assert os.path.exists(folders["user_data_dir"])
        assert os.path.exists(folders["temp_data_dir"])
        assert os.path.exists(folders["docs_dir"])

    def test_create_system_files(self, tmp_path):
        """测试创建系统文件"""
        system_dir = tmp_path / "system"
        os.makedirs(system_dir)

        folders = {
            "user_system_dir": str(system_dir)
        }

        system_file = FolderService.create_system_files(folders, "user123", "testuser")

        assert os.path.exists(system_file)
        with open(system_file, encoding="utf-8") as f:
            data = json.load(f)
            assert data["user_id"] == "user123"
            assert data["username"] == "testuser"

    def test_create_user_folders(self, tmp_path):
        """测试创建用户文件夹完整流程"""
        service = FolderService()

        with patch.object(FolderService, "get_base_path", return_value=str(tmp_path)):
            paths = service.create_user_folders("user123", "testuser", "project")

            assert "base_path" in paths
            assert "user_system_dir" in paths
            assert "system_file" in paths


class TestCreateFoldersUseCase:
    """创建文件夹用例测试"""

    def setup_method(self):
        self.mock_service = Mock()
        self.use_case = CreateFoldersUseCase(self.mock_service)

    def test_create_folders_success(self):
        """测试创建文件夹成功"""
        self.mock_service.create_user_folders.return_value = {
            "base_path": "/tmp/test",
            "user_system_dir": "/tmp/test/system",
            "user_data_dir": "/tmp/test/data",
            "temp_data_dir": "/tmp/test/temp",
            "docs_dir": "/tmp/test/docs",
            "system_file": "/tmp/test/system/system_info.json"
        }

        request = CreateFoldersRequest(
            user_id="user123",
            username="testuser",
            folder_location="project"
        )
        response = self.use_case.execute(request)

        assert response.success is True
        assert response.message == "文件夹创建成功"
        self.mock_service.create_user_folders.assert_called_once()

    def test_create_folders_permission_error(self):
        """测试权限不足"""
        self.mock_service.create_user_folders.side_effect = PermissionError()

        request = CreateFoldersRequest(
            user_id="user123",
            username="testuser"
        )
        response = self.use_case.execute(request)

        assert response.success is False
        assert "权限不足" in response.message

    def test_create_folders_general_error(self):
        """测试一般错误"""
        self.mock_service.create_user_folders.side_effect = OSError("磁盘已满")

        request = CreateFoldersRequest(
            user_id="user123",
            username="testuser"
        )
        response = self.use_case.execute(request)

        assert response.success is False
        assert "磁盘已满" in response.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
