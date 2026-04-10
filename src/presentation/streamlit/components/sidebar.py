"""
侧边栏组件

提供统一的侧边栏功能：
- 用户状态显示
- 系统状态显示
- 节点激活/停止
- 资源分配
- 调试模式切换
"""

import time

import streamlit as st

from src.core.use_cases.auth import LoginRequest
from src.presentation.streamlit.utils.di_utils import container
from src.presentation.streamlit.utils.session_manager import SessionManager


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("🔧 控制面板")

        _render_user_status()
        st.divider()
        _render_system_status()
        st.divider()
        _render_node_controls()
        st.divider()
        _render_resource_allocation()
        st.divider()
        _render_debug_mode()


def _render_user_status():
    """渲染用户状态"""
    st.subheader("👤 用户状态")

    if st.session_state.get("user_session"):
        user_session = st.session_state.user_session
        username = user_session.get("username", "未知用户")
        user_id = user_session.get("user_id", "")

        st.success(f"✅ 已登录: {username}")
        st.caption(f"ID: {user_id[:12]}...")

        _render_token_balance(user_id)
        _render_reputation(user_id)

        if st.button("🚪 退出登录", width="stretch"):
            SessionManager.clear_localstorage()
            st.session_state.user_session = None
            st.session_state.task_history = []
            st.rerun()
    else:
        st.warning("🔒 未登录")
        username = st.text_input("用户名", key="sidebar_username")

        if st.button("快速登录", width="stretch") and username:
            use_case = container.login_use_case()
            response = use_case.execute(LoginRequest(username_or_id=username))

            if response.success:
                st.session_state.user_session = {
                    "username": response.username,
                    "user_id": response.user_id,
                }
                SessionManager.save_to_localstorage(response.user_id, response.username)
                container.token_economy_service().get_or_create_account(response.user_id)
                st.rerun()
            else:
                st.error(f"登录失败: {response.message}")


def _render_system_status():
    """渲染系统状态"""
    st.subheader("📊 系统状态")

    client = container.scheduler_client()
    success, stats = client.get_system_stats()

    if success:
        nodes_info = stats.get("nodes", {})
        tasks_info = stats.get("tasks", {})

        col1, col2 = st.columns(2)
        with col1:
            st.metric("活跃节点", nodes_info.get("idle", 0) + nodes_info.get("busy", 0))
        with col2:
            st.metric("总节点", nodes_info.get("total", 0))

        col1, col2 = st.columns(2)
        with col1:
            st.metric("已完成任务", tasks_info.get("completed", 0))
        with col2:
            st.metric("失败任务", tasks_info.get("failed", 0))
    else:
        st.error("❌ 调度器离线")


def _render_node_controls():
    """渲染节点控制"""
    st.subheader("🖥️ 节点控制")

    if not st.session_state.get("user_session"):
        st.info("请先登录")
        return

    user_id = st.session_state.user_session.get("user_id")
    client = container.scheduler_client()

    if st.session_state.get("active_node_id"):
        st.success("🟢 节点已激活")
        st.caption(f"ID: {st.session_state.active_node_id[:12]}...")

        if st.button("🛑 停止节点", width="stretch"):
            success, result = client.stop_node(st.session_state.active_node_id)
            if success:
                st.session_state.active_node_id = None
                st.success("节点已停止")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"停止失败: {result.get('error', '未知错误')}")
    else:
        if st.button("🚀 激活节点", width="stretch", type="primary"):
            success, result = client.activate_local_node(
                cpu_limit=4.0, memory_limit=4096, storage_limit=10240, user_id=user_id
            )
            if success:
                st.session_state.active_node_id = result.get("node_id")
                st.success("节点激活成功")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"激活失败: {result.get('error', '未知错误')}")


def _render_resource_allocation():
    """渲染资源分配"""
    st.subheader("⚙️ 资源分配")

    cpu_allocation = st.slider("CPU核心", 0.5, 16.0, 4.0, 0.5, key="sidebar_cpu")
    memory_allocation = st.slider("内存(MB)", 512, 32768, 4096, 512, key="sidebar_memory")

    st.session_state.resource_allocation = {"cpu": cpu_allocation, "memory": memory_allocation}


def _render_debug_mode():
    """渲染调试模式"""
    st.subheader("🐛 调试模式")

    debug_mode = st.checkbox("启用调试模式", value=st.session_state.get("debug_mode", False))
    st.session_state.debug_mode = debug_mode

    if debug_mode:
        st.info("调试模式已启用")

        if st.button("清除Session", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def _render_token_balance(user_id: str):
    """渲染代币余额"""
    token_service = container.token_economy_service()
    account_info = token_service.get_account_info(user_id)

    st.subheader("💰 代币余额")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("可用余额", f"{account_info['balance']:.2f} CMP")
    with col2:
        st.metric("质押", f"{account_info['staked']:.2f} CMP")

    st.caption(
        f"总收益: {account_info['total_earned']:.2f} CMP | 总消费: {account_info['total_spent']:.2f} CMP"
    )


def _render_reputation(user_id: str):
    """渲染声誉信息"""
    token_service = container.token_economy_service()
    account_info = token_service.get_account_info(user_id)
    reputation = account_info.get("reputation", 50.0)

    st.subheader("⭐ 声誉等级")

    tier_colors = {
        "Platinum": "#E5E4E2",
        "Gold": "#FFD700",
        "Silver": "#C0C0C0",
        "Bronze": "#CD7F32",
        "Untrusted": "#808080",
    }

    tier = account_info.get("tier", "Bronze")
    color = tier_colors.get(tier, "#808080")

    st.progress(reputation / 100, text=f"声誉: {reputation:.1f}/100")
    st.markdown(
        f"<p style='color: {color}; font-weight: bold;'>等级: {tier}</p>", unsafe_allow_html=True
    )

    st.caption(
        f"完成任务: {account_info['tasks_completed']} | 失败: {account_info['tasks_failed']}"
    )


__all__ = ["render_sidebar"]
