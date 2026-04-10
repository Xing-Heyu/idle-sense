"""
文件夹管理用例

使用示例：
    from src.core.use_cases.system import CreateFoldersUseCase, CreateFoldersRequest

    use_case = CreateFoldersUseCase(folder_service)
    response = use_case.execute(CreateFoldersRequest(
        user_id="local_abc123",
        username="test_user",
        folder_location="project"
    ))

    if response.success:
        print(f"文件夹创建成功: {response.paths}")
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CreateFoldersRequest:
    """创建文件夹请求"""

    user_id: str
    username: str
    folder_location: str = "project"


@dataclass
class CreateFoldersResponse:
    """创建文件夹响应"""

    success: bool
    paths: dict = field(default_factory=dict)
    message: str = ""


class FolderService:
    """文件夹管理服务"""

    @staticmethod
    def get_base_path(folder_location: str) -> str:
        """根据用户选择获取基础路径"""
        project_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
        )

        if folder_location == "project":
            return os.path.join(project_root, "node_data")
        elif folder_location == "c":
            return "C:\\idle-sense-system-data"
        elif folder_location == "d":
            return "D:\\idle-sense-system-data"
        else:
            return os.path.join(project_root, "node_data")

    @staticmethod
    def create_folder_structure(base_path: str, user_id: str) -> dict:
        """创建三层平级文件夹结构"""
        folders = {
            "user_system_dir": os.path.join(base_path, "user_system (系统专用-请勿修改)", user_id),
            "user_data_dir": os.path.join(base_path, "user_data (您的数据文件-主要工作区)"),
            "temp_data_dir": os.path.join(base_path, "temp_data (临时文件-自动清理)"),
            "docs_dir": os.path.join(
                base_path, "user_system (系统专用-请勿修改)", user_id, "docs (说明文档)"
            ),
        }

        for folder_path in folders.values():
            os.makedirs(folder_path, exist_ok=True)

        return folders

    @staticmethod
    def create_system_files(folders: dict, user_id: str, username: str) -> str:
        """创建系统文件"""
        system_info = {
            "user_id": user_id,
            "username": username,
            "purpose": "此文件包含闲置计算加速器系统运行所需的信息，请勿删除",
        }

        system_file_path = os.path.join(folders["user_system_dir"], "system_info.json")
        with open(system_file_path, "w", encoding="utf-8") as f:
            json.dump(system_info, f, ensure_ascii=False, indent=2)

        return system_file_path

    def create_user_folders(self, user_id: str, username: str, location: str) -> dict:
        """
        创建用户文件夹

        Args:
            user_id: 用户ID
            username: 用户名
            location: 文件夹位置

        Returns:
            文件夹路径字典
        """
        base_path = self.get_base_path(location)
        folders = self.create_folder_structure(base_path, user_id)
        system_file = self.create_system_files(folders, user_id, username)

        return {
            "base_path": base_path,
            "user_system_dir": folders["user_system_dir"],
            "user_data_dir": folders["user_data_dir"],
            "temp_data_dir": folders["temp_data_dir"],
            "docs_dir": folders["docs_dir"],
            "system_file": system_file,
        }


class CreateFoldersUseCase:
    """创建文件夹用例"""

    def __init__(self, folder_service: Optional[FolderService] = None):
        """
        初始化创建文件夹用例

        Args:
            folder_service: 文件夹服务
        """
        self._folder_service = folder_service or FolderService()

    def execute(self, request: CreateFoldersRequest) -> CreateFoldersResponse:
        """
        执行创建文件夹

        Args:
            request: 创建文件夹请求

        Returns:
            创建文件夹响应
        """
        try:
            paths = self._folder_service.create_user_folders(
                user_id=request.user_id, username=request.username, location=request.folder_location
            )
            return CreateFoldersResponse(success=True, paths=paths, message="文件夹创建成功")
        except PermissionError:
            return CreateFoldersResponse(success=False, message="权限不足，无法创建文件夹")
        except Exception as e:
            return CreateFoldersResponse(success=False, message=f"文件夹创建失败: {str(e)}")


__all__ = ["CreateFoldersUseCase", "CreateFoldersRequest", "CreateFoldersResponse", "FolderService"]
