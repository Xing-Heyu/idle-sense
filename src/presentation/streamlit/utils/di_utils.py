"""
Streamlit DI 工具 - 提供与 Streamlit 集成的 DI 功能

使用示例：
    from src.presentation.streamlit.utils.di_utils import get_container, container

    container = get_container()
"""

import streamlit as st

from src.di import Container


@st.cache_resource
def get_container():
    """获取或创建 DI 容器实例（Streamlit 缓存单例）"""
    container = Container()
    return container


container = get_container()


def ensure_wired():
    """确保容器已连接模块（延迟连接，避免循环导入）"""
    if not hasattr(container, '_wired') or not container._wired:
        try:
            container.wire(modules=[
                "src.presentation.streamlit.components.sidebar",
                "src.presentation.streamlit.views.auth_page",
                "src.presentation.streamlit.views.task_monitor_page",
                "src.presentation.streamlit.views.task_submission_page",
                "src.presentation.streamlit.views.node_management_page",
                "src.presentation.streamlit.views.system_stats_page",
            ])
            container._wired = True
        except Exception:
            container._wired = False


__all__ = [
    "get_container",
    "container",
    "ensure_wired",
]
