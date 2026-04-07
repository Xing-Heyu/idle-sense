"""
Streamlit应用主类 - 重构版

使用Clean Architecture重构后的模块
"""

import time
from datetime import datetime

import streamlit as st

from config.settings import settings
from src.core.use_cases.auth.login_use_case import LoginRequest, LoginUseCase
from src.core.use_cases.auth.register_use_case import RegisterRequest, RegisterUseCase
from src.core.use_cases.task.submit_task_use_case import SubmitTaskRequest, SubmitTaskUseCase
from src.infrastructure.external import SchedulerClient
from src.infrastructure.repositories import FileUserRepository, InMemoryTaskRepository


@st.cache_resource
def get_repositories():
    """获取仓储实例"""
    return {
        'user_repo': FileUserRepository(),
        'task_repo': InMemoryTaskRepository()
    }


@st.cache_resource
def get_scheduler_client():
    """获取调度器客户端"""
    return SchedulerClient(
        base_url=settings.SCHEDULER.URL,
        timeout=settings.SCHEDULER.API_TIMEOUT,
        health_check_timeout=settings.SCHEDULER.HEALTH_CHECK_TIMEOUT
    )


def init_session_state():
    """初始化Session State"""
    defaults = {
        'user_session': None,
        'task_history': [],
        'auto_refresh': settings.WEB.AUTO_REFRESH,
        'debug_mode': settings.DEBUG
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def configure_page():
    """配置页面"""
    st.set_page_config(
        page_title=settings.WEB.PAGE_TITLE,
        page_icon=settings.WEB.PAGE_ICON,
        layout=settings.WEB.LAYOUT,
        initial_sidebar_state=settings.WEB.INITIAL_SIDEBAR_STATE
    )


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("控制面板")

        get_repositories()
        scheduler = get_scheduler_client()

        with st.expander("📊 系统状态", expanded=True):
            success, health = scheduler.check_health()
            if success:
                st.success("🟢 调度器在线")
                online = health.get("nodes", {}).get("online", 0)
                total = health.get("nodes", {}).get("total", 0)
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("在线节点", online)
                with col2:
                    st.metric("总节点", total)
            else:
                st.error("🔴 调度器离线")

        st.divider()

        if st.session_state.user_session:
            st.subheader("👤 用户状态")
            username = st.session_state.user_session.get('username', '用户')
            st.success(f"✅ 已登录: {username}")

            if st.button("🚪 退出登录", width="stretch"):
                st.session_state.user_session = None
                st.rerun()
        else:
            st.warning("🔒 未登录")


def render_auth_page():
    """渲染认证页面"""
    repos = get_repositories()
    user_repo = repos['user_repo']

    st.header("🔐 登录 / 注册")

    tab_login, tab_register = st.tabs(["登录", "注册"])

    with tab_login, st.form("login_form"):
        username = st.text_input("用户名", placeholder="输入用户名")
        submit = st.form_submit_button("登录", type="primary")

        if submit and username:
            use_case = LoginUseCase(user_repo)
            response = use_case.execute(LoginRequest(username=username))

            if response.success:
                st.session_state.user_session = {
                    "user_id": response.user.user_id,
                    "username": response.user.username,
                    "folder_location": response.user.folder_location
                }
                st.success(f"欢迎回来, {response.user.username}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error(response.message)

    with tab_register, st.form("register_form"):
        new_username = st.text_input("新用户名", placeholder="输入用户名")
        folder_location = st.selectbox("文件夹位置", ["project", "c", "d"])
        submit = st.form_submit_button("注册", type="primary")

        if submit and new_username:
            use_case = RegisterUseCase(user_repo)
            response = use_case.execute(RegisterRequest(
                username=new_username,
                folder_location=folder_location
            ))

            if response.success:
                st.session_state.user_session = {
                    "user_id": response.user.user_id,
                    "username": response.user.username,
                    "folder_location": response.user.folder_location
                }
                st.success(f"注册成功, {response.user.username}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error(response.message)


def render_task_submission_page():
    """渲染任务提交页面"""
    st.header("📝 提交计算任务")

    repos = get_repositories()
    scheduler = get_scheduler_client()

    st.radio("选择任务类型", ["单节点任务", "分布式任务"], horizontal=True,
                        disabled=True, help="分布式任务即将上线")

    col1, col2 = st.columns(2)
    with col1:
        timeout = st.number_input("超时时间(秒)", min_value=10, max_value=7200, value=300)
        cpu = st.slider("CPU需求(核心)", 0.5, 32.0, 4.0, 0.5)
    with col2:
        memory = st.slider("内存需求(MB)", 512, 65536, 4096, 512)

    code = st.text_area("输入Python代码", height=250,
                        placeholder="print('Hello World')")

    if st.button("🚀 提交任务", type="primary", width="stretch"):
        if not code.strip():
            st.error("请输入Python代码")
            return

        use_case = SubmitTaskUseCase(repos['task_repo'], scheduler)
        response = use_case.execute(SubmitTaskRequest(
            code=code,
            timeout=timeout,
            cpu=cpu,
            memory=memory,
            user_id=st.session_state.user_session.get('user_id')
        ))

        if response.success:
            st.success(f"✅ 任务提交成功! 任务ID: {response.task_id}")

            st.session_state.task_history.append({
                "task_id": response.task_id,
                "time": datetime.now().strftime("%H:%M:%S"),
                "status": "submitted",
                "code_preview": code[:50] + "...",
                "type": "单节点任务"
            })
        else:
            st.error(f"❌ 提交失败: {response.message}")


def render_task_monitor_page():
    """渲染任务监控页面"""
    st.header("📊 任务监控")

    if st.session_state.task_history:
        for task in reversed(st.session_state.task_history[-10:]):
            with st.expander(f"任务: {task.get('task_id', 'N/A')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**状态**: {task.get('status', 'N/A')}")
                    st.write(f"**时间**: {task.get('time', 'N/A')}")
                with col2:
                    st.write(f"**类型**: {task.get('type', 'N/A')}")
                    st.write(f"**代码**: {task.get('code_preview', 'N/A')}")
    else:
        st.info("暂无任务记录")


def render_node_management_page():
    """渲染节点管理页面"""
    st.header("🖥️ 节点管理")

    scheduler = get_scheduler_client()
    success, data = scheduler.get_all_nodes()

    if success:
        nodes = data.get("nodes", [])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总节点", len(nodes))
        with col2:
            st.metric("在线节点", data.get("online_nodes", 0))
        with col3:
            st.metric("空闲节点", data.get("idle_nodes", 0))

        if nodes:
            for node in nodes:
                status_color = "🟢" if node.get("is_online") else "🔴"
                st.write(f"{status_color} **{node.get('node_id', 'N/A')}** - {node.get('status_detail', 'N/A')}")
        else:
            st.info("暂无节点")
    else:
        st.error("无法获取节点信息")


def render_system_stats_page():
    """渲染系统统计页面"""
    st.header("📈 系统统计")

    scheduler = get_scheduler_client()
    success, stats = scheduler.get_system_stats()

    if success:
        tasks = stats.get("tasks", {})
        nodes = stats.get("nodes", {})

        st.subheader("📊 任务统计")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总任务", tasks.get("total", 0))
        with col2:
            st.metric("已完成", tasks.get("completed", 0))
        with col3:
            st.metric("失败", tasks.get("failed", 0))
        with col4:
            st.metric("平均耗时", f"{tasks.get('avg_time', 0):.1f}秒")

        st.subheader("🖥️ 节点统计")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("空闲", nodes.get("idle", 0))
        with col2:
            st.metric("忙碌", nodes.get("busy", 0))
        with col3:
            st.metric("离线", nodes.get("offline", 0))
    else:
        st.error("无法获取系统统计")


def render_task_results_page():
    """渲染任务结果页面"""
    st.header("📋 任务结果")

    scheduler = get_scheduler_client()
    success, results = scheduler.get_all_results()

    if success:
        st.json(results)
    else:
        st.info("暂无任务结果")


def main():
    """应用入口"""
    configure_page()
    init_session_state()

    st.title(f"⚡ {settings.WEB.PAGE_TITLE}")
    st.markdown("利用个人电脑闲置算力的分布式计算平台")

    render_sidebar()

    if st.session_state.user_session:
        tabs = st.tabs(["📝 提交任务", "📊 任务监控", "🖥️ 节点管理", "📈 系统统计", "📋 任务结果"])

        with tabs[0]:
            render_task_submission_page()

        with tabs[1]:
            render_task_monitor_page()

        with tabs[2]:
            render_node_management_page()

        with tabs[3]:
            render_system_stats_page()

        with tabs[4]:
            render_task_results_page()
    else:
        render_auth_page()

    st.divider()
    st.caption(f"{settings.APP_NAME} v{settings.APP_VERSION} | 开源免费项目")

    if st.session_state.auto_refresh:
        time.sleep(settings.WEB.REFRESH_INTERVAL)
        st.rerun()


if __name__ == "__main__":
    main()
