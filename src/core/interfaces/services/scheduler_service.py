"""
调度器服务接口

定义调度中心通信的抽象接口：
- check_health: 健康检查
- get_nodes: 获取节点列表
- submit_task: 提交任务
- get_task_status: 获取任务状态
- get_system_stats: 获取系统统计
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ISchedulerService(ABC):
    """
    调度器服务接口

    定义与调度中心通信的契约
    """

    @abstractmethod
    def check_health(self) -> tuple[bool, dict[str, Any]]:
        """
        检查调度中心健康状态

        Returns:
            (是否在线, 健康信息)
        """
        pass

    @abstractmethod
    def get_nodes(self, online_only: bool = False) -> tuple[bool, dict[str, Any]]:
        """
        获取节点列表

        Args:
            online_only: 是否只获取在线节点

        Returns:
            (是否成功, 节点信息)
        """
        pass

    @abstractmethod
    def submit_task(
        self,
        code: str,
        timeout: int = 300,
        cpu: float = 1.0,
        memory: int = 512,
        user_id: Optional[str] = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        提交任务到调度中心

        Args:
            code: 任务代码
            timeout: 超时时间（秒）
            cpu: CPU需求
            memory: 内存需求（MB）
            user_id: 用户ID

        Returns:
            (是否成功, 任务信息)
        """
        pass

    @abstractmethod
    def get_task_status(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            (是否成功, 任务状态)
        """
        pass

    @abstractmethod
    def delete_task(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        删除任务

        Args:
            task_id: 任务ID

        Returns:
            (是否成功, 删除结果)
        """
        pass

    @abstractmethod
    def get_all_results(self) -> tuple[bool, dict[str, Any]]:
        """
        获取所有任务结果

        Returns:
            (是否成功, 任务结果)
        """
        pass

    @abstractmethod
    def get_system_stats(self) -> tuple[bool, dict[str, Any]]:
        """
        获取系统统计信息

        Returns:
            (是否成功, 统计信息)
        """
        pass

    @abstractmethod
    def stop_node(self, node_id: str) -> tuple[bool, dict[str, Any]]:
        """
        停止指定节点

        Args:
            node_id: 节点ID

        Returns:
            (是否成功, 停止结果)
        """
        pass

    @abstractmethod
    def activate_local_node(
        self, cpu_limit: float, memory_limit: int, storage_limit: int, user_id: Optional[str] = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        激活本地节点

        Args:
            cpu_limit: CPU限制
            memory_limit: 内存限制（MB）
            storage_limit: 存储限制（MB）
            user_id: 用户ID

        Returns:
            (是否成功, 节点信息)
        """
        pass


__all__ = ["ISchedulerService"]
