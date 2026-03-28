"""
闲置检测服务

封装 legacy.idle_sense 模块，提供统一的业务接口
"""

from typing import Any, Optional

from legacy.idle_sense import get_platform, get_system_status, is_idle


class IdleDetectionService:
    """
    闲置检测服务

    封装闲置检测功能，提供业务层接口

    Examples:
        >>> service = IdleDetectionService()
        >>> if service.is_system_idle():
        ...     print("系统空闲，可以执行任务")
    """

    def __init__(
        self,
        idle_threshold_sec: Optional[int] = None,
        cpu_threshold: Optional[float] = None,
        memory_threshold: Optional[float] = None
    ):
        """
        初始化闲置检测服务

        Args:
            idle_threshold_sec: 用户空闲时间阈值（秒）
            cpu_threshold: CPU使用率阈值（%）
            memory_threshold: 内存使用率阈值（%）
        """
        self._idle_threshold = idle_threshold_sec or 300
        self._cpu_threshold = cpu_threshold or 15.0
        self._memory_threshold = memory_threshold or 70.0

    def is_system_idle(
        self,
        idle_threshold_sec: Optional[int] = None,
        cpu_threshold: Optional[float] = None,
        memory_threshold: Optional[float] = None
    ) -> bool:
        """
        检查系统是否空闲

        Args:
            idle_threshold_sec: 用户空闲时间阈值（秒）
            cpu_threshold: CPU使用率阈值（%）
            memory_threshold: 内存使用率阈值（%）

        Returns:
            True 如果系统空闲
        """
        return is_idle(
            idle_threshold_sec=idle_threshold_sec or self._idle_threshold,
            cpu_threshold=cpu_threshold or self._cpu_threshold,
            memory_threshold=memory_threshold or self._memory_threshold
        )

    def get_status(
        self,
        idle_threshold_sec: Optional[int] = None,
        cpu_threshold: Optional[float] = None,
        memory_threshold: Optional[float] = None
    ) -> dict[str, Any]:
        """
        获取系统状态详情

        Args:
            idle_threshold_sec: 用户空闲时间阈值（秒）
            cpu_threshold: CPU使用率阈值（%）
            memory_threshold: 内存使用率阈值（%）

        Returns:
            系统状态信息
        """
        return get_system_status(
            idle_threshold_sec=idle_threshold_sec or self._idle_threshold,
            cpu_threshold=cpu_threshold or self._cpu_threshold,
            memory_threshold=memory_threshold or self._memory_threshold
        )

    def get_platform_name(self) -> str:
        """
        获取当前平台名称

        Returns:
            平台名称 ('windows', 'macos', 'linux')
        """
        return get_platform()

    def get_idle_time_seconds(self) -> float:
        """
        获取用户空闲时间（秒）

        Returns:
            空闲时间（秒）
        """
        status = self.get_status()
        return status.get("idle_time", 0)

    def get_resource_usage(self) -> dict[str, float]:
        """
        获取资源使用情况

        Returns:
            资源使用信息
        """
        status = self.get_status()
        return {
            "cpu_usage": status.get("cpu_usage", 0.0),
            "memory_usage": status.get("memory_usage", 0.0),
            "idle_time": status.get("idle_time", 0),
        }

    def should_start_task(
        self,
        min_idle_time: Optional[int] = None,
        max_cpu_usage: Optional[float] = None,
        max_memory_usage: Optional[float] = None
    ) -> dict[str, Any]:
        """
        判断是否应该开始执行任务

        Args:
            min_idle_time: 最小空闲时间要求（秒）
            max_cpu_usage: 最大CPU使用率要求（%）
            max_memory_usage: 最大内存使用率要求（%）

        Returns:
            判断结果和原因
        """
        min_idle = min_idle_time or self._idle_threshold
        max_cpu = max_cpu_usage or self._cpu_threshold
        max_mem = max_memory_usage or self._memory_threshold

        status = self.get_status()

        idle_time = status.get("idle_time", 0)
        cpu_usage = status.get("cpu_usage", 0.0)
        memory_usage = status.get("memory_usage", 0.0)

        reasons = []

        if idle_time < min_idle:
            reasons.append(f"用户空闲时间不足: {idle_time}秒 < {min_idle}秒")

        if cpu_usage > max_cpu:
            reasons.append(f"CPU使用率过高: {cpu_usage}% > {max_cpu}%")

        if memory_usage > max_mem:
            reasons.append(f"内存使用率过高: {memory_usage}% > {max_mem}%")

        should_start = len(reasons) == 0

        return {
            "should_start": should_start,
            "reasons": reasons,
            "current_status": {
                "idle_time": idle_time,
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
            },
            "thresholds": {
                "min_idle_time": min_idle,
                "max_cpu_usage": max_cpu,
                "max_memory_usage": max_mem,
            }
        }


__all__ = ["IdleDetectionService"]
