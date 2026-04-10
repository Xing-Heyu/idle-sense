"""
遗留系统适配器

实现 Strangler Fig Pattern，平滑迁移旧代码到新架构
- 保持 web_interface.py 的所有功能可用
- 通过功能开关控制新旧代码切换
- 支持 A/B 测试和灰度发布
"""

import os
import sys
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class FeatureFlag(Enum):
    """功能开关 - 控制新旧代码切换"""

    USE_NEW_AUTH = "use_new_auth"  # 使用新认证系统
    USE_NEW_TASK = "use_new_task"  # 使用新任务系统
    USE_NEW_NODE = "use_new_node"  # 使用新节点系统
    USE_NEW_UI = "use_new_ui"  # 使用新UI


@dataclass
class MigrationConfig:
    """迁移配置"""

    enabled_features: set = None
    fallback_on_error: bool = True  # 出错时回退到旧代码
    log_switching: bool = True  # 记录切换日志

    def __post_init__(self):
        if self.enabled_features is None:
            self.enabled_features = set()

    def is_enabled(self, feature: FeatureFlag) -> bool:
        return feature in self.enabled_features

    def enable(self, feature: FeatureFlag):
        self.enabled_features.add(feature)

    def disable(self, feature: FeatureFlag):
        self.enabled_features.discard(feature)


class LegacyAdapter:
    """
    遗留系统适配器

    提供统一的接口，内部根据功能开关决定使用新旧代码
    """

    def __init__(self, config: Optional[MigrationConfig] = None):
        self.config = config or MigrationConfig()
        self._legacy_module = None
        self._new_repositories = {}
        self._new_use_cases = {}

        # 显示弃用警告
        warnings.warn(
            "LegacyAdapter is deprecated. Please migrate to Clean Architecture.",
            DeprecationWarning,
            stacklevel=2,
        )

    def _get_legacy_module(self):
        """延迟加载旧模块"""
        if self._legacy_module is None:
            try:
                # 动态导入 web_interface.py 的功能
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "web_interface", os.path.join(project_root, "web_interface.py")
                )
                self._legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(self._legacy_module)
            except Exception as e:
                if self.config.fallback_on_error:
                    print(f"Warning: Could not load legacy module: {e}")
                    return None
                raise
        return self._legacy_module

    def _get_new_repository(self, name: str):
        """获取新架构的仓储"""
        if name not in self._new_repositories:
            if name == "user":
                from src.infrastructure.repositories import FileUserRepository

                self._new_repositories[name] = FileUserRepository()
            elif name == "task":
                from src.infrastructure.repositories import InMemoryTaskRepository

                self._new_repositories[name] = InMemoryTaskRepository()
            elif name == "node":
                from src.infrastructure.repositories import InMemoryNodeRepository

                self._new_repositories[name] = InMemoryNodeRepository()
        return self._new_repositories.get(name)

    # ==================== 认证适配 ====================

    def login(self, username: str) -> dict[str, Any]:
        """
        用户登录 - 根据功能开关选择实现

        Args:
            username: 用户名

        Returns:
            {"success": bool, "user": dict, "message": str}
        """
        if self.config.is_enabled(FeatureFlag.USE_NEW_AUTH):
            try:
                from src.core.use_cases.auth.login_use_case import LoginRequest, LoginUseCase

                user_repo = self._get_new_repository("user")
                use_case = LoginUseCase(user_repo)
                response = use_case.execute(LoginRequest(username=username))

                return {
                    "success": response.success,
                    "user": (
                        {
                            "user_id": response.user.user_id,
                            "username": response.user.username,
                            "folder_location": response.user.folder_location,
                        }
                        if response.user
                        else None
                    ),
                    "message": response.message,
                }
            except Exception as e:
                if self.config.fallback_on_error:
                    print(f"New auth failed, falling back to legacy: {e}")
                else:
                    raise

        # 回退到旧实现
        legacy = self._get_legacy_module()
        if legacy and hasattr(legacy, "UserManager"):
            manager = legacy.UserManager()
            # 模拟旧代码的登录逻辑
            users = manager.list_users()
            for user in users:
                if user.get("username") == username:
                    return {"success": True, "user": user, "message": "登录成功 (legacy)"}
            return {"success": False, "user": None, "message": "用户不存在"}

        return {"success": False, "message": "登录系统不可用"}

    def register(self, username: str, folder_location: str = "project") -> dict[str, Any]:
        """
        用户注册

        Args:
            username: 用户名
            folder_location: 文件夹位置

        Returns:
            {"success": bool, "user": dict, "message": str}
        """
        if self.config.is_enabled(FeatureFlag.USE_NEW_AUTH):
            try:
                from src.core.use_cases.auth.register_use_case import (
                    RegisterRequest,
                    RegisterUseCase,
                )

                user_repo = self._get_new_repository("user")
                use_case = RegisterUseCase(user_repo)
                response = use_case.execute(
                    RegisterRequest(username=username, folder_location=folder_location)
                )

                return {
                    "success": response.success,
                    "user": (
                        {
                            "user_id": response.user.user_id,
                            "username": response.user.username,
                            "folder_location": response.user.folder_location,
                        }
                        if response.user
                        else None
                    ),
                    "message": response.message,
                }
            except Exception as e:
                if self.config.fallback_on_error:
                    print(f"New register failed, falling back to legacy: {e}")
                else:
                    raise

        # 回退到旧实现
        legacy = self._get_legacy_module()
        if legacy and hasattr(legacy, "UserManager"):
            manager = legacy.UserManager()

            # 检查用户名
            is_valid, msg = manager.validate_username(username)
            if not is_valid:
                return {"success": False, "message": msg}

            # 生成唯一用户名
            new_username = manager.check_username_availability(username)

            # 创建用户
            import uuid

            user_id = str(uuid.uuid4())[:8]
            user_info = manager.save_user(user_id, new_username, folder_location)

            return {"success": True, "user": user_info, "message": "注册成功 (legacy)"}

        return {"success": False, "message": "注册系统不可用"}

    def logout(self, user_id: str) -> dict[str, Any]:
        """
        用户登出

        Note: 这是新功能，旧代码中没有实现
        """
        # 新架构中有 LogoutUseCase（待实现）
        # 暂时简单实现
        return {"success": True, "message": "登出成功"}

    # ==================== 任务适配 ====================

    def submit_task(
        self,
        code: str,
        timeout: int = 300,
        cpu: float = 1.0,
        memory: int = 512,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        提交任务

        Args:
            code: Python代码
            timeout: 超时时间
            cpu: CPU需求
            memory: 内存需求
            user_id: 用户ID

        Returns:
            {"success": bool, "task_id": str, "message": str}
        """
        if self.config.is_enabled(FeatureFlag.USE_NEW_TASK):
            try:
                from config.settings import settings
                from src.core.use_cases.task.submit_task_use_case import (
                    SubmitTaskRequest,
                    SubmitTaskUseCase,
                )
                from src.infrastructure.external import SchedulerClient

                task_repo = self._get_new_repository("task")
                scheduler = SchedulerClient(
                    base_url=settings.SCHEDULER.URL, timeout=settings.SCHEDULER.API_TIMEOUT
                )

                use_case = SubmitTaskUseCase(task_repo, scheduler)
                response = use_case.execute(
                    SubmitTaskRequest(
                        code=code, timeout=timeout, cpu=cpu, memory=memory, user_id=user_id
                    )
                )

                return {
                    "success": response.success,
                    "task_id": response.task_id if hasattr(response, "task_id") else None,
                    "message": response.message,
                }
            except Exception as e:
                if self.config.fallback_on_error:
                    print(f"New task submission failed, falling back to legacy: {e}")
                else:
                    raise

        # 回退到旧实现 - 直接调用调度器API
        try:
            import requests

            payload = {
                "code": code,
                "timeout": timeout,
                "resources": {"cpu": cpu, "memory": memory},
                "user_id": user_id,
            }

            response = requests.post("http://localhost:8000/submit", json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "task_id": data.get("task_id"),
                    "message": "任务提交成功 (legacy)",
                }
            else:
                return {"success": False, "message": f"提交失败: {response.text}"}
        except Exception as e:
            return {"success": False, "message": f"提交失败: {str(e)}"}

    # ==================== 节点适配 ====================

    def get_nodes(self) -> dict[str, Any]:
        """获取节点列表"""
        if self.config.is_enabled(FeatureFlag.USE_NEW_NODE):
            try:
                from config.settings import settings
                from src.infrastructure.external import SchedulerClient

                scheduler = SchedulerClient(
                    base_url=settings.SCHEDULER.URL, timeout=settings.SCHEDULER.API_TIMEOUT
                )

                success, data = scheduler.get_all_nodes()
                return {
                    "success": success,
                    "nodes": data.get("nodes", []),
                    "online_nodes": data.get("online_nodes", 0),
                    "idle_nodes": data.get("idle_nodes", 0),
                }
            except Exception as e:
                if self.config.fallback_on_error:
                    print(f"New node query failed, falling back to legacy: {e}")
                else:
                    raise

        # 回退到旧实现
        try:
            import requests

            response = requests.get("http://localhost:8000/nodes", timeout=10)
            if response.status_code == 200:
                return {"success": True, **response.json()}
            return {"success": False, "message": "获取失败"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ==================== 系统统计适配 ====================

    def get_system_stats(self) -> dict[str, Any]:
        """获取系统统计"""
        try:
            import requests

            response = requests.get("http://localhost:8000/stats", timeout=10)
            if response.status_code == 200:
                return {"success": True, **response.json()}
            return {"success": False, "message": "获取失败"}
        except Exception as e:
            return {"success": False, "message": str(e)}


# ==================== 便捷函数 ====================


def create_adapter(enable_new_features: bool = False) -> LegacyAdapter:
    """
    创建适配器实例

    Args:
        enable_new_features: 是否启用新功能

    Returns:
        LegacyAdapter 实例
    """
    config = MigrationConfig()

    if enable_new_features:
        config.enable(FeatureFlag.USE_NEW_AUTH)
        config.enable(FeatureFlag.USE_NEW_TASK)
        config.enable(FeatureFlag.USE_NEW_NODE)

    return LegacyAdapter(config)


# 全局适配器实例（单例）
_default_adapter: Optional[LegacyAdapter] = None


def get_adapter() -> LegacyAdapter:
    """获取默认适配器实例"""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = create_adapter()
    return _default_adapter
