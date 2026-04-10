"""
权限检查服务

提供系统权限检查功能：
- 管理员权限检查
- 写入权限检查
- 目录权限确保

使用示例：
    from src.core.services import PermissionService

    service = PermissionService()
    if service.check_admin_permission():
        print("具有管理员权限")
"""

import ctypes
import os
import sys


class PermissionService:
    """权限检查服务"""

    def check_admin_permission(self) -> bool:
        """
        检查管理员权限（跨平台支持）

        Returns:
            是否具有管理员权限
        """
        try:
            if sys.platform == "win32":
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            else:
                return os.geteuid() == 0
        except (AttributeError, OSError):
            return False

    def check_write_permission(self, path: str) -> bool:
        """
        检查写入权限

        Args:
            path: 目录路径

        Returns:
            是否具有写入权限
        """
        try:
            test_file = os.path.join(path, ".permission_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except (PermissionError, OSError):
            return False

    def ensure_directory_with_permission(self, path: str) -> tuple[bool, str]:
        """
        确保目录存在且有写入权限

        Args:
            path: 目录路径

        Returns:
            (是否成功, 消息)
        """
        try:
            os.makedirs(path, exist_ok=True)
        except PermissionError:
            return False, "权限不足，无法创建文件夹"

        if not self.check_write_permission(path):
            return False, "权限不足，无法写入文件"

        return True, "权限检查通过"


__all__ = ["PermissionService"]
