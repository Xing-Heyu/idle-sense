"""
闲置计算加速器 - 统一Web界面
采用 Clean Architecture + 依赖注入

使用示例:
    streamlit run app_unified.py
"""

import hashlib
import json
import os
import time
from datetime import datetime

import streamlit as st

from config.settings import settings
from src.di import container
from src.infrastructure.external import SchedulerClient

MODERN_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { font-family: 'Inter', sans-serif; }

    .stApp {
        background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 50%, #581c87 100%);
        min-height: 100vh;
    }

    .main-header {
        text-align: center;
        padding: 2rem 0;
        margin-bottom: 1.5rem;
        background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }

    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }

    .main-header p {
        font-size: 1rem;
        color: rgba(255,255,255,0.8);
    }

    .glass-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.05) 100%);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 20px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    .metric-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.08) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 16px;
        padding: 1rem;
        text-align: center;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .metric-label {
        font-size: 0.85rem;
        color: rgba(255,255,255,0.9);
        margin-top: 0.3rem;
    }

    .stButton button {
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(96, 165, 250, 0.4);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 12px !important;
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: rgba(255,255,255,0.8) !important;
        padding: 0.6rem 1.2rem !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%) !important;
        color: white !important;
    }

    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 10px !important;
        color: white !important;
    }

    .stSlider [data-baseweb="slider"] { padding: 0.3rem 0; }

    h3 { color: rgba(255,255,255,0.95) !important; font-weight: 600 !important; }

    .stSuccess, .stWarning, .stError, .stInfo {
        border-radius: 12px !important;
        border: none !important;
    }
</style>
"""


def init_session_state():
    """初始化 Session State"""
    defaults = {
        'user_session': None,
        'task_history': [],
        'auto_refresh': settings.WEB.AUTO_REFRESH,
        'debug_mode': settings.DEBUG,
        'local_node_id': None,
        'node_start_time': None,
        'share_cpu_value': settings.RESOURCE.DEFAULT_CPU_SHARE,
        'share_memory_value': settings.RESOURCE.DEFAULT_MEMORY_SHARE,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if 'session_id' not in st.session_state:
        st.session_state.session_id = hashlib.md5(
            f"{datetime.now().isoformat()}_{os.getpid()}".encode()
        ).hexdigest()[:16]


def restore_session():
    """从 localStorage 恢复登录态"""
    if 'user_session' not in st.session_state:
        st.markdown("""
        <script>
        const savedSession = localStorage.getItem('idle_accelerator_session');
        if (savedSession) {
            try {
                const sessionData = JSON.parse(savedSession);
                const url = new URL(window.location.href);
                url.searchParams.set('restore_session', JSON.stringify(sessionData));
                window.history.replaceState({}, '', url);
            } catch(e) {}
        }
        </script>
        """, unsafe_allow_html=True)

        restore_data = st.query_params.get_all('restore_session')
        if restore_data:
            try:
                session_data = json.loads(restore_data[0])
                st.session_state.user_session = session_data
                st.query_params.clear()
            except (json.JSONDecodeError, KeyError, IndexError):
                pass


def get_scheduler_client() -> SchedulerClient:
    """获取调度器客户端"""
    return container.scheduler_client


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.markdown("### 📊 系统状态")

        client = get_scheduler_client()
        health_ok, health_info = client.check_health()

        if health_ok:
            st.success("✅ 调度器在线")
            online = health_info.get("nodes", {}).get("online", 0)
            st.metric("可用节点", online)
        else:
            st.error("❌ 调度器离线")
            st.code("python legacy/scheduler/simple_server.py", language="bash")

        st.markdown("---")
        st.markdown("### 👤 用户会话")

        if st.session_state.user_session:
            username = st.session_state.user_session.get('username', '用户')
            st.success(f"✅ {username}")

            user_id = st.session_state.user_session.get("user_id")
            if user_id:
                st.markdown("---")
                st.markdown("### 💰 Token账户")

                account = container.token_economy_service.get_account_info(user_id)

                st.metric("余额", f"{account['balance']:,.2f} CMP")

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("质押", f"{account['staked']:,.0f}")
                with col2:
                    st.metric(f"声誉 ({account['tier']})", f"{account['reputation']:.0f}")

            if st.button("退出登录", use_container_width=True):
                st.markdown("<script>localStorage.removeItem('idle_accelerator_session');</script>", unsafe_allow_html=True)
                st.session_state.user_session = None
                st.query_params.clear()
                st.rerun()
        else:
            st.warning("🔒 未登录")
            username = st.text_input("用户名", key="sidebar_username")

            if st.button("快速登录", use_container_width=True) and username:
                user_id = f"local_{hashlib.md5(username.encode()).hexdigest()[:8]}"
                session_data = {"username": username, "user_id": user_id}
                st.session_state.user_session = session_data

                container.token_economy_service.get_or_create_account(user_id)

                st.markdown(f"""
                <script>
                localStorage.setItem('idle_accelerator_session', JSON.stringify({json.dumps(session_data)}));
                </script>
                """, unsafe_allow_html=True)
                st.toast(f"✅ 欢迎 {username}，获得 {settings.TOKEN.INITIAL_BALANCE} CMP 初始余额！", icon="✅")
                time.sleep(0.3)
                st.rerun()

        st.markdown("---")
        st.markdown("### ⚙️ 资源分配")

        cpu_share = st.slider("共享CPU核心数", 0.5, 16.0, st.session_state.share_cpu_value, 0.5)
        st.session_state.share_cpu_value = cpu_share

        memory_share = st.slider("共享内存 (MB)", 512, 32768, st.session_state.share_memory_value, 512)
        st.session_state.share_memory_value = memory_share

        st.info(f"📊 {cpu_share} 核心, {memory_share}MB")


def render_task_submission():
    """渲染任务提交页面"""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🚀 提交计算任务")

    task_type = st.radio("任务类型", ["单节点", "分布式"], horizontal=True)

    if task_type == "单节点":
        st.info("💡 单节点任务在一个节点上执行")

        col1, col2 = st.columns(2)
        with col1:
            timeout = st.number_input("超时时间 (秒)", min_value=10, max_value=7200, value=300, step=10)
            cpu_request = st.slider("CPU需求 (核心)", 0.5, 32.0, 4.0, 0.5)
        with col2:
            memory_request = st.slider("内存需求 (MB)", 512, 65536, 4096, 512)

        code = st.text_area(
            "Python代码",
            value="",
            height=250,
            placeholder="# 在这里编写代码\nprint('Hello, IdleSense!')"
        )

        if st.button("✨ 提交任务", use_container_width=True, type="primary"):
            if not code.strip():
                st.toast("⚠️ 请输入代码", icon="⚠️")
            else:
                user_id = st.session_state.user_session.get("user_id") if st.session_state.user_session else None

                with st.spinner("提交中..."):
                    client = get_scheduler_client()
                    success, result = client.submit_task(code, timeout, cpu_request, memory_request, user_id)

                    if success:
                        task_id = result.get("task_id")
                        cost_info = container.token_economy_service.estimate_task_cost(
                            cpu_request, memory_request, timeout
                        )
                        st.toast(f"✅ 任务提交成功！ID: {task_id} | 预估: {cost_info['final_price']} CMP", icon="✅")

                        st.session_state.task_history.append({
                            "task_id": task_id,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "status": "submitted",
                        })
                    else:
                        st.toast(f"❌ 提交失败: {result.get('error', '未知错误')}", icon="❌")
    else:
        st.info("🚀 分布式任务利用多个节点并行处理")
        st.warning("分布式任务模块正在重构中...")

    st.markdown('</div>', unsafe_allow_html=True)


def render_task_monitor():
    """渲染任务监控页面"""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("📊 任务监控")

    if st.button("🔄 刷新", key="refresh_tasks"):
        st.rerun()

    client = get_scheduler_client()
    success, results = client.get_all_results()

    if success and results.get("results"):
        results_list = results["results"]

        if results_list:
            import pandas as pd
            results_data = []
            for result in results_list:
                results_data.append({
                    "任务ID": result.get("task_id", "N/A"),
                    "完成时间": datetime.fromtimestamp(result.get("completed_at", time.time())).strftime("%H:%M:%S") if result.get("completed_at") else "N/A",
                    "执行节点": result.get("assigned_node", "未知"),
                    "状态": "✅ 完成" if result.get("result") else "⏳ 处理中",
                })

            if results_data:
                df = pd.DataFrame(results_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无已完成的任务")
    else:
        st.warning("无法获取任务结果")

    st.markdown('</div>', unsafe_allow_html=True)


def render_node_management():
    """渲染节点管理页面"""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🖥️ 节点管理")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 激活本机节点", use_container_width=True, type="primary"):
            user_id = st.session_state.user_session.get("user_id") if st.session_state.user_session else None
            client = get_scheduler_client()

            success, result = client.activate_local_node(
                cpu_limit=st.session_state.share_cpu_value,
                memory_limit=st.session_state.share_memory_value,
                storage_limit=settings.RESOURCE.DEFAULT_STORAGE_SHARE,
                user_id=user_id
            )

            if success and result.get("success"):
                node_id = result.get("node_id", "unknown")
                st.toast(f"✅ 节点激活成功: {node_id}", icon="✅")
                st.session_state.local_node_id = node_id
                st.session_state.node_start_time = time.time()
            else:
                error_msg = result.get("error", "未知错误") if success else result
                st.toast(f"❌ 激活失败: {error_msg}", icon="❌")

    with col2:
        local_node_id = st.session_state.get("local_node_id")
        if local_node_id:
            if st.button("🛑 停止本机节点", use_container_width=True):
                client = get_scheduler_client()
                success, result = client.stop_node(local_node_id)

                if success and result.get("success"):
                    st.toast(f"✅ 节点已停止: {local_node_id}", icon="✅")
                    st.session_state.local_node_id = None
                    st.session_state.node_start_time = None
                else:
                    st.toast("❌ 停止失败", icon="❌")
        else:
            st.button("🛑 停止本机节点", use_container_width=True, disabled=True)

    st.markdown("---")

    client = get_scheduler_client()
    success, nodes_info = client.get_all_nodes()

    if success:
        nodes = nodes_info.get("nodes", [])

        if nodes:
            import pandas as pd
            node_data = []
            for node in nodes:
                node_data.append({
                    "节点ID": node["node_id"],
                    "状态": node["status"],
                    "详情": node["status_detail"],
                    "平台": node["platform"],
                    "所有者": node["owner"],
                })

            df = pd.DataFrame(node_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总节点", nodes_info["total_nodes"])
            with col2:
                st.metric("在线", nodes_info["online_nodes"])
            with col3:
                st.metric("空闲", nodes_info["idle_nodes"])
        else:
            st.info("暂无注册节点")
    else:
        st.error("无法获取节点信息")

    st.markdown('</div>', unsafe_allow_html=True)


def render_system_stats():
    """渲染系统统计页面"""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("📈 系统统计")

    client = get_scheduler_client()
    success, stats = client.get_system_stats()

    if success:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats['tasks']['total']}</div>
                <div class="metric-label">总任务数</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats['tasks']['completed']}</div>
                <div class="metric-label">已完成</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats['nodes']['total']}</div>
                <div class="metric-label">总节点数</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            online = stats['nodes']['idle'] + stats['nodes']['busy']
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{online}</div>
                <div class="metric-label">在线节点</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("💰 Token经济")

        token_stats = container.token_economy_service.get_system_stats()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总供应量", f"{token_stats['total_supply']:,.0f}", "CMP")
        with col2:
            st.metric("流通量", f"{token_stats['circulating_supply']:,.0f}", "CMP")
        with col3:
            st.metric("总质押", f"{token_stats['total_staked']:,.0f}", "CMP")
        with col4:
            st.metric("账户数", f"{token_stats['total_accounts']}")

        st.info("💡 完成任务可获得CMP奖励，质押CMP可提高任务优先级。")
    else:
        st.warning("无法获取系统统计")

    st.markdown('</div>', unsafe_allow_html=True)


def render_task_results():
    """渲染任务结果页面"""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("📋 任务结果")

    if st.session_state.task_history:
        import pandas as pd
        df = pd.DataFrame(st.session_state.task_history)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无任务历史记录")

    st.markdown('</div>', unsafe_allow_html=True)


def main():
    """应用入口"""
    st.set_page_config(
        page_title=settings.WEB.PAGE_TITLE,
        page_icon=settings.WEB.PAGE_ICON,
        layout=settings.WEB.LAYOUT,
        initial_sidebar_state=settings.WEB.INITIAL_SIDEBAR_STATE
    )

    st.markdown(MODERN_STYLE, unsafe_allow_html=True)

    init_session_state()
    restore_session()

    st.markdown("""
    <div class="main-header">
        <h1>闲置计算加速器</h1>
        <p>闲置计算资源分布式计算平台</p>
    </div>
    """, unsafe_allow_html=True)

    render_sidebar()

    if st.session_state.user_session:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📝 提交任务", "📊 任务监控", "🖥️ 节点管理", "📈 系统统计", "📋 任务结果"
        ])

        with tab1:
            render_task_submission()

        with tab2:
            render_task_monitor()

        with tab3:
            render_node_management()

        with tab4:
            render_system_stats()

        with tab5:
            render_task_results()
    else:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.info("🔐 请在左侧边栏登录以使用平台功能。")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align: center; padding: 2rem 0; margin-top: 2rem; border-top: 1px solid rgba(255,255,255,0.1); color: rgba(255,255,255,0.6); font-size: 0.85rem;">
        ✨ 闲置计算加速器 • 分布式计算平台 • 版本 2.0
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
