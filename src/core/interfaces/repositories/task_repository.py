"""
任务仓储接口

定义任务数据访问的抽象接口：
- get_by_id: 根据ID获取任务
- save: 保存任务
- update: 更新任务
- delete: 删除任务
- list_by_user: 获取用户的任务列表
- list_by_status: 获取指定状态的任务列表
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.core.entities import Task, TaskStatus


class ITaskRepository(ABC):
    """
    任务仓储接口

    定义任务数据访问的契约
    """

    @abstractmethod
    def get_by_id(self, task_id: str) -> Optional[Task]:
        """
        根据ID获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务实体，如果不存在则返回None
        """
        pass

    @abstractmethod
    def save(self, task: Task) -> Task:
        """
        保存任务

        Args:
            task: 任务实体

        Returns:
            保存后的任务实体
        """
        pass

    @abstractmethod
    def update(self, task: Task) -> Task:
        """
        更新任务

        Args:
            task: 任务实体

        Returns:
            更新后的任务实体
        """
        pass

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """
        删除任务

        Args:
            task_id: 任务ID

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    def list_by_user(self, user_id: str, limit: int = 100) -> list[Task]:
        """
        获取用户的任务列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制

        Returns:
            任务实体列表
        """
        pass

    @abstractmethod
    def list_by_status(self, status: TaskStatus, limit: int = 100) -> list[Task]:
        """
        获取指定状态的任务列表

        Args:
            status: 任务状态
            limit: 返回数量限制

        Returns:
            任务实体列表
        """
        pass

    @abstractmethod
    def list_all(self, limit: int = 100) -> list[Task]:
        """
        获取所有任务

        Args:
            limit: 返回数量限制

        Returns:
            任务实体列表
        """
        pass


__all__ = ["ITaskRepository"]
