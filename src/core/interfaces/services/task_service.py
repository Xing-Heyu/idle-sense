"""
任务服务接口

定义任务管理的抽象接口：
- submit_task: 提交任务
- submit_distributed_task: 提交分布式任务
- get_task_status: 获取任务状态
- delete_task: 删除任务
- get_all_results: 获取所有结果
- get_system_stats: 获取系统统计
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ITaskService(ABC):
    """
    任务服务接口

    定义任务管理的契约
    """

    @abstractmethod
    def submit_task(
        self,
        code: str,
        timeout: int = 300,
        cpu: float = 1.0,
        memory: int = 512,
        user_id: Optional[str] = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        提交单节点任务

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
    def submit_distributed_task(
        self,
        name: str,
        description: str,
        code_template: str,
        data: Any,
        chunk_size: int = 10,
        max_parallel_chunks: int = 5,
        merge_code: Optional[str] = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        提交分布式任务

        Args:
            name: 任务名称
            description: 任务描述
            code_template: 代码模板
            data: 任务数据
            chunk_size: 分片大小
            max_parallel_chunks: 最大并行分片数
            merge_code: 合并代码

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
        获取系统统计

        Returns:
            (是否成功, 统计信息)
        """
        pass

    @abstractmethod
    def get_distributed_task_status(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        获取分布式任务状态

        Args:
            task_id: 任务ID

        Returns:
            (是否成功, 任务状态)
        """
        pass

    @abstractmethod
    def get_distributed_task_result(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        获取分布式任务结果

        Args:
            task_id: 任务ID

        Returns:
            (是否成功, 任务结果)
        """
        pass


__all__ = ["ITaskService"]
