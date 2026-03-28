"""
文件夹实体模块

基于DDD设计原则的文件夹实体：
- 唯一标识：folder_id
- 属性：path, folder_type, user_id
- 方法：创建、删除、验证

使用示例：
    from src.core.entities import Folder, FolderType

    folder = Folder(
        folder_type=FolderType.USER_DATA,
        path="/data/user_data",
        user_id="user_123"
    )
"""

import contextlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class FolderType(Enum):
    """文件夹类型枚举"""
    USER_SYSTEM = "user_system"
    USER_DATA = "user_data"
    TEMP_DATA = "temp_data"
    DOCS = "docs"


class FolderPermission(Enum):
    """文件夹权限枚举"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


@dataclass
class Folder:
    """
    文件夹实体

    代表系统中的文件夹，具有以下职责：
    - 管理文件夹基本信息和类型
    - 处理文件夹创建和验证
    - 提供文件夹路径管理
    """
    folder_type: FolderType
    path: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    size: int = 0
    file_count: int = 0
    description: Optional[str] = None

    @property
    def name(self) -> str:
        """获取文件夹名称"""
        return Path(self.path).name

    @property
    def exists(self) -> bool:
        """检查文件夹是否存在"""
        return os.path.exists(self.path)

    @property
    def is_writable(self) -> bool:
        """检查文件夹是否可写"""
        if not self.exists:
            return False
        return os.access(self.path, os.W_OK)

    @property
    def is_readable(self) -> bool:
        """检查文件夹是否可读"""
        if not self.exists:
            return False
        return os.access(self.path, os.R_OK)

    def create(self, exist_ok: bool = True) -> bool:
        """
        创建文件夹

        Args:
            exist_ok: 如果文件夹已存在是否报错

        Returns:
            是否创建成功
        """
        try:
            os.makedirs(self.path, exist_ok=exist_ok)
            return True
        except Exception:
            return False

    def delete(self) -> bool:
        """
        删除文件夹

        Returns:
            是否删除成功
        """
        try:
            if self.exists:
                os.rmdir(self.path)
            return True
        except Exception:
            return False

    def get_size(self) -> int:
        """
        获取文件夹大小（字节）

        Returns:
            文件夹大小
        """
        if not self.exists:
            return 0

        total_size = 0
        try:
            for dirpath, _dirnames, filenames in os.walk(self.path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    with contextlib.suppress(OSError):
                        total_size += os.path.getsize(filepath)
        except Exception:
            pass

        return total_size

    def get_file_count(self) -> int:
        """
        获取文件数量

        Returns:
            文件数量
        """
        if not self.exists:
            return 0

        count = 0
        try:
            for _dirpath, _dirnames, filenames in os.walk(self.path):
                count += len(filenames)
        except Exception:
            pass

        return count

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "folder_type": self.folder_type.value,
            "path": self.path,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "size": self.size,
            "file_count": self.file_count,
            "description": self.description,
            "exists": self.exists,
            "is_writable": self.is_writable,
            "is_readable": self.is_readable
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Folder":
        """从字典创建文件夹实体"""
        return cls(
            folder_type=FolderType(data.get("folder_type", "user_data")),
            path=data.get("path", ""),
            user_id=data.get("user_id", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            size=data.get("size", 0),
            file_count=data.get("file_count", 0),
            description=data.get("description")
        )


class FolderFactory:
    """文件夹工厂类"""

    @staticmethod
    def create_user_folders(
        base_path: str,
        user_id: str,
        username: str  # noqa: ARG004
    ) -> dict[FolderType, Folder]:
        """
        创建用户文件夹结构

        Args:
            base_path: 基础路径
            user_id: 用户ID
            username: 用户名

        Returns:
            文件夹类型到文件夹实体的映射
        """
        folders = {}

        folder_configs = {
            FolderType.USER_SYSTEM: ("user_system (系统专用-请勿修改)", "系统文件夹"),
            FolderType.USER_DATA: ("user_data (您的数据文件-主要工作区)", "用户数据文件夹"),
            FolderType.TEMP_DATA: ("temp_data (临时文件-自动清理)", "临时文件夹"),
            FolderType.DOCS: ("docs (说明文档)", "文档文件夹")
        }

        for folder_type, (folder_name, description) in folder_configs.items():
            if folder_type == FolderType.DOCS:
                path = os.path.join(base_path, "user_system (系统专用-请勿修改)", user_id, folder_name)
            else:
                path = os.path.join(base_path, folder_name)

            folders[folder_type] = Folder(
                folder_type=folder_type,
                path=path,
                user_id=user_id,
                description=description
            )

        return folders

    @staticmethod
    def create_from_dict(data: dict[str, Any]) -> Folder:
        """从字典创建文件夹"""
        return Folder.from_dict(data)


# 文件夹类型描述
FOLDER_TYPE_DESCRIPTIONS = {
    FolderType.USER_SYSTEM: "存放用户ID等系统数据，平时不常用",
    FolderType.USER_DATA: "存放您不会删除的个人文件，系统可读取",
    FolderType.TEMP_DATA: "存放任务执行时的临时文件，会定期清理",
    FolderType.DOCS: "存放系统说明文档"
}

FOLDER_TYPE_NAMES = {
    FolderType.USER_SYSTEM: "用户系统文件夹",
    FolderType.USER_DATA: "用户数据文件夹",
    FolderType.TEMP_DATA: "临时数据文件夹",
    FolderType.DOCS: "文档文件夹"
}


__all__ = [
    "Folder",
    "FolderType",
    "FolderPermission",
    "FolderFactory",
    "FOLDER_TYPE_DESCRIPTIONS",
    "FOLDER_TYPE_NAMES"
]
