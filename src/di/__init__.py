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

import streamlit as st

from .container import Container

_container = None


@st.cache_resource
def get_container():
    """获取或创建 DI 容器实例（单例）"""
    global _container
    if _container is None:
        _container = Container()
        _container.wire(modules=[
            "src.presentation.streamlit.components.sidebar",
            "src.presentation.streamlit.views.auth_page",
            "src.presentation.streamlit.views.task_monitor_page",
            "src.presentation.streamlit.views.task_submission_page",
            "src.presentation.streamlit.views.node_management_page",
            "src.presentation.streamlit.views.system_stats_page",
        ])
    return _container


container = get_container()


__all__ = [
    "Container",
    "container",
    "get_container",
]
