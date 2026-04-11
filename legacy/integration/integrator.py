"""
Legacy 模块集成器核心实现

提供统一的接口来启用和管理 legacy 模块
"""

import logging
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class IntegrationConfig:
    """集成配置"""
    enable_health_check: bool = True
    enable_distributed_lock: bool = True
    enable_retry_recovery: bool = True
    enable_timeout_manager: bool = True
    enable_monitoring: bool = True
    enable_event_bus: bool = True

    health_check_interval: float = 30.0
    lock_default_ttl: float = 30.0
    retry_max_attempts: int = 3
    task_default_timeout: float = 300.0
    metrics_namespace: str = "idle_accelerator"


class LegacyIntegrator:
    """
    Legacy 模块集成器

    统一管理所有 legacy 模块的初始化和生命周期
    """

    _instance: Optional["LegacyIntegrator"] = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[IntegrationConfig] = None):
        self.config = config or IntegrationConfig()

        self._health_checker = None
        self._health_monitor = None
        self._distributed_lock = None
        self._retry_manager = None
        self._fault_recovery_manager = None
        self._timeout_manager = None
        self._timeout_executor = None
        self._metrics_registry = None
        self._system_monitor = None
        self._event_bus = None

        self._initialized = False
        self._storage = None
        self._server_id = None

    @classmethod
    def get_instance(cls, config: Optional[IntegrationConfig] = None) -> "LegacyIntegrator":
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config)
        return cls._instance

    def initialize(self, storage=None, server_id: str = None):
        """
        初始化所有启用的模块

        Args:
            storage: 存储实例（用于与调度器集成）
            server_id: 服务器ID
        """
        if self._initialized:
            logger.warning("[集成器] 已经初始化，跳过")
            return

        self._storage = storage
        self._server_id = server_id or "unknown"

        logger.info("=" * 60)
        logger.info("Legacy 模块集成器 v1.0")
        logger.info("=" * 60)

        if self.config.enable_health_check:
            self._init_health_check()

        if self.config.enable_distributed_lock:
            self._init_distributed_lock()

        if self.config.enable_retry_recovery:
            self._init_retry_recovery()

        if self.config.enable_timeout_manager:
            self._init_timeout_manager()

        if self.config.enable_monitoring:
            self._init_monitoring()

        if self.config.enable_event_bus:
            self._init_event_bus()

        self._initialized = True
        logger.info("=" * 60)
        logger.info("Legacy 模块初始化完成!")
        logger.info("=" * 60)

    def _init_health_check(self):
        """初始化健康检查模块"""
        try:
            from legacy.health_check import (
                CPUHealthCheck,
                DiskHealthCheck,
                HealthChecker,
                HealthMonitor,
                MemoryHealthCheck,
                NetworkHealthCheck,
            )

            self._health_checker = HealthChecker(
                component_id=self._server_id,
                component_type="scheduler"
            )

            self._health_checker.register_check(CPUHealthCheck(threshold_percent=90))
            self._health_checker.register_check(MemoryHealthCheck(threshold_percent=90))
            self._health_checker.register_check(DiskHealthCheck(path=".", threshold_percent=90))
            self._health_checker.register_check(NetworkHealthCheck())

            self._health_monitor = HealthMonitor(
                check_interval=self.config.health_check_interval
            )
            self._health_monitor.register_checker(self._health_checker)
            self._health_monitor.start()

            logger.info(f"[健康检查] 已启用 - 检查间隔: {self.config.health_check_interval}s")

        except ImportError as e:
            logger.warning(f"[健康检查] 导入失败: {e}")
        except Exception as e:
            logger.error(f"[健康检查] 初始化失败: {e}")

    def _init_distributed_lock(self):
        """初始化分布式锁模块"""
        try:
            from legacy.distributed_lock import DistributedLock, MemoryLockBackend

            backend = MemoryLockBackend()

            self._distributed_lock = DistributedLock(
                backend=backend,
                default_ttl=self.config.lock_default_ttl,
                owner=self._server_id
            )

            logger.info(f"[分布式锁] 已启用 - 默认TTL: {self.config.lock_default_ttl}s")

        except ImportError as e:
            logger.warning(f"[分布式锁] 导入失败: {e}")
        except Exception as e:
            logger.error(f"[分布式锁] 初始化失败: {e}")

    def _init_retry_recovery(self):
        """初始化重试恢复模块"""
        try:
            from legacy.retry_recovery import FaultRecoveryManager, RetryManager

            self._retry_manager = RetryManager()
            self._fault_recovery_manager = FaultRecoveryManager()

            logger.info(f"[重试恢复] 已启用 - 最大重试: {self.config.retry_max_attempts}")

        except ImportError as e:
            logger.warning(f"[重试恢复] 导入失败: {e}")
        except Exception as e:
            logger.error(f"[重试恢复] 初始化失败: {e}")

    def _init_timeout_manager(self):
        """初始化超时管理模块"""
        try:
            from legacy.timeout_manager import TimeoutExecutor, TimeoutManager

            self._timeout_manager = TimeoutManager()
            self._timeout_executor = TimeoutExecutor(
                default_timeout=self.config.task_default_timeout
            )

            logger.info(f"[超时管理] 已启用 - 默认超时: {self.config.task_default_timeout}s")

        except ImportError as e:
            logger.warning(f"[超时管理] 导入失败: {e}")
        except Exception as e:
            logger.error(f"[超时管理] 初始化失败: {e}")

    def _init_monitoring(self):
        """初始化监控指标模块"""
        try:
            from legacy.monitoring import MetricsRegistry, SystemMonitor

            self._metrics_registry = MetricsRegistry(
                namespace=self.config.metrics_namespace
            )
            self._system_monitor = SystemMonitor(registry=self._metrics_registry)

            logger.info(f"[监控指标] 已启用 - 命名空间: {self.config.metrics_namespace}")

        except ImportError as e:
            logger.warning(f"[监控指标] 导入失败: {e}")
        except Exception as e:
            logger.error(f"[监控指标] 初始化失败: {e}")

    def _init_event_bus(self):
        """初始化事件总线模块"""
        try:
            from legacy.event_bus import EventBus

            self._event_bus = EventBus(history_size=100, debug=False)

            self._setup_event_handlers()

            logger.info("[事件总线] 已启用")

        except ImportError as e:
            logger.warning(f"[事件总线] 导入失败: {e}")
        except Exception as e:
            logger.error(f"[事件总线] 初始化失败: {e}")

    def _setup_event_handlers(self):
        """设置事件处理器"""
        if not self._event_bus:
            return

        @self._event_bus.on("task_submitted")
        def on_task_submitted(event):
            logger.debug(f"[事件] 任务提交: {event.data}")
            if self._system_monitor:
                self._system_monitor.record_task_submitted()

        @self._event_bus.on("task_completed")
        def on_task_completed(event):
            logger.debug(f"[事件] 任务完成: {event.data}")
            if self._system_monitor:
                duration = event.data.get("duration", 0)
                success = event.data.get("success", True)
                self._system_monitor.record_task_completed(duration, success)

        @self._event_bus.on("task_failed")
        def on_task_failed(event):
            logger.debug(f"[事件] 任务失败: {event.data}")
            if self._system_monitor:
                self._system_monitor.record_task_completed(0, False)

        @self._event_bus.on("node_offline")
        def on_node_offline(event):
            logger.warning(f"[事件] 节点离线: {event.data}")
            if self._fault_recovery_manager and self._storage:
                node_id = event.data.get("node_id")
                if node_id:
                    self._fault_recovery_manager.handle_node_failure(
                        node_id,
                        lambda nid: getattr(self._storage, 'assigned_tasks', {}).get(nid, [])
                    )

    @property
    def health_checker(self):
        return self._health_checker

    @property
    def health_monitor(self):
        return self._health_monitor

    @property
    def distributed_lock(self):
        return self._distributed_lock

    @property
    def retry_manager(self):
        return self._retry_manager

    @property
    def fault_recovery_manager(self):
        return self._fault_recovery_manager

    @property
    def timeout_manager(self):
        return self._timeout_manager

    @property
    def timeout_executor(self):
        return self._timeout_executor

    @property
    def metrics_registry(self):
        return self._metrics_registry

    @property
    def system_monitor(self):
        return self._system_monitor

    @property
    def event_bus(self):
        return self._event_bus

    def get_health_report(self) -> dict:
        """获取健康报告"""
        if self._health_checker:
            report = self._health_checker.run_all()
            return report.to_dict()
        return {"status": "unavailable"}

    def get_metrics_prometheus(self) -> str:
        """获取 Prometheus 格式的指标"""
        if self._metrics_registry:
            return self._metrics_registry.export_prometheus()
        return ""

    def get_system_stats(self) -> dict:
        """获取系统统计"""
        if self._system_monitor:
            return self._system_monitor.get_stats()
        return {}

    def acquire_lock(self, resource: str, timeout: float = 10.0) -> bool:
        """获取分布式锁"""
        if self._distributed_lock:
            from legacy.distributed_lock import LockState
            state = self._distributed_lock.acquire(resource, timeout_seconds=timeout)
            return state == LockState.ACQUIRED
        return True

    def release_lock(self, resource: str) -> bool:
        """释放分布式锁"""
        if self._distributed_lock:
            lock_info = self._distributed_lock.get_lock_info(resource)
            if lock_info:
                from legacy.distributed_lock import LockState
                state = self._distributed_lock.release(lock_info.lock_id)
                return state == LockState.RELEASED
        return True

    def configure_retry(self, task_id: int, max_retries: int = 3,
                       exponential_backoff: bool = True) -> bool:
        """配置任务重试"""
        if self._retry_manager:
            from legacy.retry_recovery import RetryConfig
            config = RetryConfig(
                max_retries=max_retries,
                exponential_backoff=exponential_backoff
            )
            self._retry_manager.configure(task_id, config)
            return True
        return False

    def should_retry(self, task_id: int, exception: Exception) -> bool:
        """判断是否应该重试"""
        if self._retry_manager:
            return self._retry_manager.should_retry(task_id, exception)
        return False

    def record_retry_attempt(self, task_id: int, exception: Exception = None):
        """记录重试尝试"""
        if self._retry_manager:
            self._retry_manager.record_attempt(task_id, exception)

    def get_retry_delay(self, task_id: int) -> float:
        """获取重试延迟"""
        if self._retry_manager:
            return self._retry_manager.get_retry_delay(task_id)
        return 1.0

    def publish_event(self, event_type: str, data: dict):
        """发布事件"""
        if self._event_bus:
            from legacy.event_bus import Event
            self._event_bus.publish(Event(event_type=event_type, data=data))

    def shutdown(self):
        """关闭所有模块"""
        logger.info("[集成器] 正在关闭...")

        if self._health_monitor:
            self._health_monitor.stop()
            logger.info("[健康检查] 已停止")

        if self._distributed_lock:
            self._distributed_lock.release_all()
            logger.info("[分布式锁] 已释放")

        logger.info("[集成器] 关闭完成")


def get_integrator(config: Optional[IntegrationConfig] = None) -> LegacyIntegrator:
    """获取集成器实例"""
    return LegacyIntegrator.get_instance(config)
