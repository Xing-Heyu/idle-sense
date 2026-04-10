"""
di - 依赖注入容器模块

提供：
- Container: 容器类
- container: 预初始化的全局容器实例（向后兼容）
- get_container: 获取容器实例的函数（向后兼容）

使用示例：
    from src.di import Container

    container = Container()
    container.wire(modules=[__name__])

    from dependency_injector.wiring import inject, Provide

    @inject
    def my_function(client: SchedulerClient = Provide[Container.scheduler_client]):
        client.check_health()

向后兼容说明：
    以下导入方式已弃用但仍然可用：
    - from src.di import container  # 使用预初始化的全局容器
    - from src.di import get_container  # 获取容器实例
"""

import warnings

from .container import Container, container as _container


def get_container():
    """
    获取全局容器实例（向后兼容）

    .. deprecated:: 1.0.0
        此函数将在 v2.0.0 版本中移除。

        迁移方式一（推荐）- 创建新容器实例：
            # 旧代码
            from src.di import get_container
            container = get_container()

            # 新代码
            from src.di import Container
            container = Container()
            container.wire(modules=[__name__])

        迁移方式二 - 使用预初始化的全局容器：
            # 旧代码
            from src.di import get_container
            container = get_container()

            # 新代码
            from src.di import container
            # 或
            from src.di.container import container

        迁移时间表：
            - v1.0.0: 标记为废弃，发出 DeprecationWarning
            - v1.5.0: 发出 FutureWarning（更严重的警告）
            - v2.0.0: 移除此函数
    """
    warnings.warn(
        "get_container() is deprecated since v1.0.0 and will be removed in v2.0.0. "
        "Migration examples:\n"
        "  # Option 1 (recommended):\n"
        "  from src.di import Container\n"
        "  container = Container()\n\n"
        "  # Option 2:\n"
        "  from src.di import container\n"
        "  # or: from src.di.container import container",
        DeprecationWarning,
        stacklevel=2
    )
    return _container


container = _container


__all__ = [
    "Container",
    "container",
    "get_container",
]
