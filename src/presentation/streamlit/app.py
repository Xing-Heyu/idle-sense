"""
闲置计算加速器 - Streamlit Web界面

使用 Clean Architecture 架构
"""

import streamlit as st

from src.presentation.streamlit.utils.di_utils import ensure_wired

ensure_wired()

from src.presentation.streamlit.components.sidebar import render_sidebar  # noqa: E402
from src.presentation.streamlit.utils.session_manager import SessionManager  # noqa: E402
from src.presentation.streamlit.views.auth_page import render as render_auth  # noqa: E402
from src.presentation.streamlit.views.node_management_page import (
    render as render_node_management,  # noqa: E402
)
from src.presentation.streamlit.views.system_stats_page import (
    render as render_system_stats,  # noqa: E402
)
from src.presentation.streamlit.views.task_monitor_page import (
    render as render_task_monitor,  # noqa: E402
)
from src.presentation.streamlit.views.task_results_page import (
    render as render_task_results,  # noqa: E402
)
from src.presentation.streamlit.views.task_submission_page import (
    render as render_task_submission,  # noqa: E402
)


def configure_page():
    """配置页面"""
    st.set_page_config(
        page_title="闲置计算加速器",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        color: white;
    }
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
    }
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    </style>
    """, unsafe_allow_html=True)


def init_session_state():
    """初始化会话状态"""
    SessionManager.init_session_state()
    SessionManager.restore_from_localstorage()
    SessionManager.restore_from_url_params()


def render_main():
    """渲染主界面"""
    st.markdown("""
    <div class="main-header">
        <h1>🚀 闲置计算加速器</h1>
        <p>分布式计算资源调度平台 - Clean Architecture 版本</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.user_session:
        user_id = st.session_state.user_session.get("user_id")

        tabs = st.tabs([
            "📝 提交任务",
            "📊 任务监控",
            "🖥️ 节点管理",
            "📈 系统统计",
            "📋 任务结果"
        ])

        with tabs[0]:
            render_task_submission(user_id)

        with tabs[1]:
            render_task_monitor(user_id)

        with tabs[2]:
            render_node_management(user_id)

        with tabs[3]:
            render_system_stats(user_id)

        with tabs[4]:
            render_task_results(user_id)
    else:
        render_auth()


def main():
    """主函数"""
    configure_page()
    init_session_state()
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
