"""
Legacy 模块集成器
将 legacy 目录下的成熟模块整合到主系统中

启用模块:
- health_check: 节点与服务健康检查
- distributed_lock: 分布式锁（调度器选举）
- retry_recovery: 任务重试与故障恢复
- timeout_manager: 任务超时管理
- monitoring: Prometheus 监控指标
- event_bus: 事件总线（模块解耦）
"""

from legacy.integration.integrator import LegacyIntegrator, get_integrator

__all__ = ["LegacyIntegrator", "get_integrator"]
