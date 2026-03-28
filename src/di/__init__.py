"""
di - 依赖注入容器模块

提供：
- container: 主容器
- providers: 提供者定义
- modules: 模块配置

使用示例：
    from src.di import Container, inject

    container = Container()
    container.wire(modules=[__name__])

    @inject
    def my_function(client: SchedulerClient = Provide[Container.scheduler_client]):
        client.check_health()
"""

from .container import Container, container

__all__ = [
    "Container",
    "container",
]
