"""
web_interface_academic.py
闲置计算加速器 - 学术风格网页控制界面
设计特点：简洁、专业、清晰的学术期刊风格
"""

import hashlib
import json
import os
import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ==================== 学术风格配置 ====================

ACADEMIC_STYLE = """
<style>
    /* 学术风格的全局样式 */
    @import url('https://fonts.googleapis.com/css2?family=Latin+Modern+Roman&family=Latin+Modern+Sans&display=swap');

    * {
        font-family: 'Latin Modern Roman', 'Latin Modern Sans', 'Times New Roman', serif;
    }

    /* 主标题样式 - 类似期刊标题 */
    .main-header {
        text-align: center;
        padding: 2rem 0;
        border-bottom: 2px solid #1a365d;
        margin-bottom: 2rem;
    }

    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 400;
        color: #1a365d;
        letter-spacing: 0.05em;
    }

    .main-header p {
        font-size: 1.1rem;
        color: #4a5568;
        font-style: italic;
    }

    /* 卡片样式 - 类似学术论文的章节 */
    .academic-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: none;
        border-left: 4px solid #1a365d;
    }

    /* 侧边栏样式 */
    .sidebar-section {
        padding: 1rem;
        margin-bottom: 1rem;
        border-bottom: 1px solid #e2e8f0;
    }

    .sidebar-title {
        font-size: 1rem;
        font-weight: 600;
        color: #1a365d;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 1rem;
    }

    /* 按钮样式 - 学术风格 */
    .stButton button {
        background-color: #1a365d !important;
        color: white !important;
        border: none !important;
        border-radius: 0 !important;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .stButton button:hover {
        background-color: #2c5282 !important;
    }

    /* 指标卡样式 */
    .metric-card {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        padding: 1rem;
        text-align: center;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #1a365d;
    }

    .metric-label {
        font-size: 0.9rem;
        color: #4a5568;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* 标签页样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 0;
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        margin-right: -1px;
    }

    .stTabs [aria-selected="true"] {
        background: #1a365d !important;
        color: white !important;
    }

    /* 表格样式 */
    .dataframe {
        font-family: 'Latin Modern Roman', serif;
    }

    /* 分割线 */
    .section-divider {
        border: none;
        border-top: 1px solid #e2e8f0;
        margin: 2rem 0;
    }

    /* 状态指示器 */
    .status-online {
        color: #2f855a;
        font-weight: 500;
    }

    .status-offline {
        color: #c53030;
        font-weight: 500;
    }

    /* 页脚 */
    .footer {
        text-align: center;
        padding: 2rem 0;
        margin-top: 3rem;
        border-top: 1px solid #e2e8f0;
        color: #718096;
        font-size: 0.9rem;
    }
</style>
"""

# ==================== 模块导入 ====================

try:
    from distributed_task import DISTRIBUTED_TASK_TEMPLATES, DistributedTaskManager  # noqa: F401
    DISTRIBUTED_TASK_AVAILABLE = True
except ImportError:
    DISTRIBUTED_TASK_AVAILABLE = False

try:
    from file_drop_and_recovery import (  # noqa: F401
        FileDropManager,
        create_file_drop_task_interface,
    )
    FILE_DROP_AVAILABLE = True
except ImportError:
    FILE_DROP_AVAILABLE = False

# ==================== 页面配置 ====================

st.set_page_config(
    page_title="IdleSense | 分布式计算平台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(ACADEMIC_STYLE, unsafe_allow_html=True)

SCHEDULER_URL = "http://localhost:8000"
REFRESH_INTERVAL = 30

# ==================== 持久化登录恢复 ====================

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

# ==================== 优化工具函数 ====================

def safe_api_call(func, *args, default=None, **kwargs):
    try:
        response = func(*args, **kwargs)
        if hasattr(response, 'status_code'):
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {"error": f"HTTP {response.status_code}", "text": response.text}
        else:
            return True, response
    except requests.exceptions.ConnectionError:
        return False, {"error": "无法连接到调度中心"}
    except requests.exceptions.Timeout:
        return False, {"error": "请求超时"}
    except Exception as e:
        return False, {"error": f"请求失败: {str(e)}"}

# ==================== 用户管理类 ====================

class UserManager:
    def __init__(self):
        self.users_dir = self._get_users_dir()

    def _get_users_dir(self):
        users_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_users")
        os.makedirs(users_dir, exist_ok=True)
        return users_dir

    def validate_username(self, username):
        import re
        if len(username) > 20:
            return False, "用户名长度不能超过20个字符"
        pattern = r'^[\u4e00-\u9fa5a-zA-Z0-9]+$'
        if not re.match(pattern, username):
            return False, "用户名只能包含中文、英文和数字"
        return True, "用户名格式正确"

    def save_user(self, user_id, username, folder_location="project"):
        user_file = os.path.join(self.users_dir, f"{user_id}.json")
        user_info = {
            "user_id": user_id,
            "username": username,
            "created_at": datetime.now().isoformat(),
            "folder_location": folder_location,
            "last_login": None
        }
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_info, f, ensure_ascii=False, indent=2)
        return user_info

    def get_user(self, user_id):
        user_file = os.path.join(self.users_dir, f"{user_id}.json")
        if os.path.exists(user_file):
            with open(user_file, encoding='utf-8') as f:
                return json.load(f)
        return None

    def update_user_login(self, user_id):
        user_info = self.get_user(user_id)
        if user_info:
            user_info["last_login"] = datetime.now().isoformat()
            user_file = os.path.join(self.users_dir, f"{user_id}.json")
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(user_info, f, ensure_ascii=False, indent=2)
            return True
        return False

    def list_users(self):
        users = []
        if os.path.exists(self.users_dir):
            for file_name in os.listdir(self.users_dir):
                if file_name.endswith('.json'):
                    user_id = file_name[:-5]
                    user_info = self.get_user(user_id)
                    if user_info:
                        users.append(user_info)
        return users

# ==================== 初始化管理器 ====================

user_manager = UserManager()

for key, default in [
    ('task_history', []),
    ('auto_refresh', False),
    ('last_refresh', datetime.now()),
    ('user_session', None),
    ('is_logged_in', False),
    ('last_node_status', {'online': 0, 'total': 0}),
    ('cache_data', {}),
    ('debug_mode', False),
    ('session_id', hashlib.md5(f"{datetime.now().isoformat()}_{os.getpid()}".encode()).hexdigest()[:16]),
    ('share_cpu_value', 4.0),
    ('share_memory_value', 8192)
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ==================== API 函数 ====================

def check_scheduler_health():
    success, health_data = safe_api_call(requests.get, f"{SCHEDULER_URL}/health", timeout=3)
    if not success:
        success, root_data = safe_api_call(requests.get, SCHEDULER_URL, timeout=3)
        if success:
            return True, {"status": "online", "nodes": {"online": 0, "total": 0}}
        return False, health_data

    success, nodes_data = safe_api_call(requests.get, f"{SCHEDULER_URL}/api/nodes",
                                       params={"online_only": False}, timeout=4)

    if success:
        all_nodes = nodes_data.get("nodes", [])
        online_nodes = 0

        for node in all_nodes:
            is_online = False
            if "is_online" in node:
                val = node["is_online"]
                if isinstance(val, bool):
                    is_online = val
                elif isinstance(val, str):
                    is_online = val.lower() in ["true", "yes", "1", "online"]
            elif "status" in node:
                status = node["status"]
                if isinstance(status, str):
                    is_online = status.lower() == "online_available"
            if is_online:
                online_nodes += 1

        if "nodes" not in health_data:
            health_data["nodes"] = {}
        health_data["nodes"]["online"] = online_nodes
        health_data["nodes"]["total"] = len(all_nodes)
    else:
        if "nodes" not in health_data:
            health_data["nodes"] = {}
        health_data["nodes"]["online"] = 0
        health_data["nodes"]["total"] = 0

    return True, health_data

def get_all_nodes():
    success, data = safe_api_call(requests.get, f"{SCHEDULER_URL}/api/nodes",
                                 params={"online_only": False}, timeout=5)

    if not success:
        return success, data

    nodes = data.get("nodes", [])
    processed_nodes = []
    online_count = 0
    idle_count = 0

    for node in nodes:
        node_id = node.get("node_id", "unknown")
        status = node.get("status", "")
        is_online = status.lower() == "online_available"
        is_idle = node.get("is_idle", False)

        if is_online:
            online_count += 1
            if is_idle:
                idle_count += 1

        processed_nodes.append({
            "node_id": node_id,
            "is_online": is_online,
            "is_idle": is_idle,
            "status": "Online" if is_online else "Offline",
            "status_detail": "Idle" if is_idle else "Busy" if is_online else "Offline",
            "platform": node.get("platform", "unknown"),
            "capacity": node.get("capacity", {}),
            "tags": node.get("tags", {}),
            "owner": node.get("tags", {}).get("user_id", "Unknown")
        })

    return True, {
        "nodes": processed_nodes,
        "total_nodes": len(processed_nodes),
        "online_nodes": online_count,
        "idle_nodes": idle_count,
        "busy_nodes": online_count - idle_count
    }

def submit_task(code, timeout=300, cpu=1.0, memory=512):
    user_id = None
    if st.session_state.user_session:
        user_id = st.session_state.user_session.get("user_id")
    payload = {
        "code": code,
        "timeout": timeout,
        "resources": {"cpu": cpu, "memory": memory},
        "user_id": user_id
    }
    return safe_api_call(requests.post, f"{SCHEDULER_URL}/submit", json=payload, timeout=10)

def get_task_status(task_id):
    return safe_api_call(requests.get, f"{SCHEDULER_URL}/status/{task_id}", timeout=5)

def delete_task(task_id):
    return safe_api_call(requests.delete, f"{SCHEDULER_URL}/api/tasks/{task_id}", timeout=5)

def get_system_stats():
    success, data = safe_api_call(requests.get, f"{SCHEDULER_URL}/stats", timeout=5)
    if not success:
        return False, data
    tasks_info = data.get("tasks", {})
    nodes_info = data.get("nodes", {})
    return True, {
        "tasks": {
            "total": tasks_info.get("total", 0),
            "completed": tasks_info.get("completed", 0),
            "failed": tasks_info.get("failed", 0),
            "avg_time": tasks_info.get("avg_completion_time", 0)
        },
        "nodes": {
            "idle": nodes_info.get("idle", 0),
            "busy": nodes_info.get("online", 0) - nodes_info.get("idle", 0),
            "offline": nodes_info.get("offline", 0),
            "total": nodes_info.get("total", 0)
        },
        "throughput": {
            "compute_hours": tasks_info.get("total", 0) * tasks_info.get("avg_completion_time", 0) / 3600
        },
        "scheduler": data.get("scheduler", {})
    }

def get_all_results():
    return safe_api_call(requests.get, f"{SCHEDULER_URL}/results", timeout=5)

def stop_node(node_id: str):
    return safe_api_call(requests.post, f"{SCHEDULER_URL}/api/nodes/{node_id}/stop", timeout=5)

# ==================== 主页面 ====================

st.markdown("""
<div class="main-header">
    <h1>IdleSense</h1>
    <p>闲置计算资源分布式计算平台</p>
</div>
""", unsafe_allow_html=True)

# ==================== 侧边栏 ====================

with st.sidebar:
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">系统状态</div>', unsafe_allow_html=True)

    health_ok, health_info = check_scheduler_health()

    if health_ok:
        st.success("✓ Scheduler Online")

        col1, col2 = st.columns(2)
        with col1:
            online = health_info.get("nodes", {}).get("online", 0)
            st.metric("Available Nodes", online)

        with col2:
            if st.button("↻", help="Refresh Status"):
                st.rerun()
    else:
        st.error("✗ Scheduler Offline")
        st.code("Run: python scheduler/simple_server.py")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">用户会话</div>', unsafe_allow_html=True)

    if st.session_state.user_session:
        st.success(f"✓ {st.session_state.user_session.get('username', '用户')}")
        if st.button("退出登录"):
            st.markdown("<script>localStorage.removeItem('idle_accelerator_session');</script>", unsafe_allow_html=True)
            st.session_state.user_session = None
            st.query_params.clear()
            st.rerun()
    else:
        st.warning("未登录")
        username = st.text_input("用户名", key="sidebar_username")

        if st.button("快速登录") and username:
            user_id = f"local_{hashlib.md5(username.encode()).hexdigest()[:8]}"
            user_manager.save_user(user_id, username, "project")
            st.session_state.user_session = {
                "username": username,
                "user_id": user_id
            }
            st.success(f"✓ 欢迎 {username}")
            time.sleep(1)
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">资源分配</div>', unsafe_allow_html=True)

    cpu_value = st.session_state.get('share_cpu_value', 4.0)
    memory_value = st.session_state.get('share_memory_value', 8192)

    cpu_share = st.slider("共享CPU核心数", 0.5, 16.0, cpu_value, 0.5)
    st.session_state.share_cpu_value = cpu_share

    memory_share = st.slider("共享内存大小 (MB)", 512, 32768, memory_value, 512)
    st.session_state.share_memory_value = memory_share

    st.info(f"共享: {cpu_share} 核心, {memory_share}MB 内存")
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== 主内容区 ====================

if st.session_state.user_session:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["提交任务", "任务监控", "节点管理", "系统统计", "任务结果"])

    with tab1:
        st.subheader("提交计算任务")

        task_type = st.radio("任务类型", ["单节点", "分布式"], horizontal=True,
                            disabled=not DISTRIBUTED_TASK_AVAILABLE)

        if task_type == "分布式" and not DISTRIBUTED_TASK_AVAILABLE:
            st.error("分布式任务模块不可用")

        if task_type == "单节点":
            st.info("单节点任务在一个节点上执行。大型工作负载请使用分布式任务。")

            col1, col2 = st.columns(2)
            with col1:
                timeout = st.number_input("超时时间 (秒)", min_value=10, max_value=7200, value=300, step=10)
                cpu_request = st.slider("CPU需求 (核心)", 0.5, 32.0, 4.0, 0.5)
            with col2:
                memory_request = st.slider("内存需求 (MB)", 512, 65536, 4096, 512)

            code = st.text_area(
                "Python代码",
                value="",
                height=300,
                placeholder="# 在这里编写你的代码\nprint('你好, IdleSense!')"
            )

            if st.button("提交任务", use_container_width=True):
                if not code.strip():
                    st.error("请输入Python代码")
                else:
                    with st.spinner("提交任务中..."):
                        success, result = submit_task(code, timeout, cpu_request, memory_request)

                        if success:
                            task_id = result.get("task_id")
                            st.success(f"✓ 任务提交成功！任务ID: {task_id}")
                        else:
                            st.error(f"✗ 提交失败: {result.get('error', '未知错误')}")

        else:
            st.info("分布式任务利用多个节点进行并行处理。")

    with tab2:
        st.subheader("任务监控")

        if st.button("刷新任务列表"):
            st.rerun()

        success, results = get_all_results()
        if success and results.get("results"):
            results_list = results["results"]

            if results_list:
                results_data = []
                for result in results_list:
                    results_data.append({
                        "任务ID": result.get("task_id", "N/A"),
                        "完成时间": datetime.fromtimestamp(result.get("completed_at", time.time())).strftime("%H:%M:%S") if result.get("completed_at") else "N/A",
                        "执行节点": result.get("assigned_node", "未知"),
                        "结果预览": (result.get("result", "无结果")[:50] + "...") if result.get("result") and len(result.get("result", "")) > 50 else (result.get("result", "无结果") or "无结果")
                    })

                if results_data:
                    results_df = pd.DataFrame(results_data)
                    st.dataframe(results_df, use_container_width=True, hide_index=True)
            else:
                st.info("暂无已完成的任务")
        elif not success:
            st.warning("无法获取任务结果")

    with tab3:
        st.subheader("节点管理")

        success, nodes_info = get_all_nodes()
        if success:
            nodes = nodes_info.get("nodes", [])

            if nodes:
                node_data = []
                for node in nodes:
                    node_data.append({
                        "节点ID": node["node_id"],
                        "状态": node["status"],
                        "详情": node["status_detail"],
                        "平台": node["platform"],
                        "所有者": node["owner"]
                    })

                node_df = pd.DataFrame(node_data)
                st.dataframe(node_df, use_container_width=True, hide_index=True)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("总节点数", nodes_info["total_nodes"])
                with col2:
                    st.metric("在线节点", nodes_info["online_nodes"])
                with col3:
                    st.metric("空闲节点", nodes_info["idle_nodes"])
            else:
                st.info("暂无注册节点")
        else:
            st.error("无法获取节点信息")

    with tab4:
        st.subheader("系统统计")

        success, stats = get_system_stats()
        if success:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-value">{}</div>
                    <div class="metric-label">总任务数</div>
                </div>
                """.format(stats["tasks"]["total"]), unsafe_allow_html=True)

            with col2:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-value">{}</div>
                    <div class="metric-label">已完成</div>
                </div>
                """.format(stats["tasks"]["completed"]), unsafe_allow_html=True)

            with col3:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-value">{}</div>
                    <div class="metric-label">总节点数</div>
                </div>
                """.format(stats["nodes"]["total"]), unsafe_allow_html=True)

            with col4:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-value">{}</div>
                    <div class="metric-label">在线节点</div>
                </div>
                """.format(stats["nodes"]["idle"] + stats["nodes"]["busy"]), unsafe_allow_html=True)

            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("任务分布")
                task_dist = [
                    stats["tasks"]["completed"],
                    stats["tasks"]["failed"],
                    stats["tasks"]["total"] - stats["tasks"]["completed"] - stats["tasks"]["failed"]
                ]
                task_labels = ["已完成", "失败", "待处理"]

                fig = go.Figure(data=[go.Pie(labels=task_labels, values=task_dist, hole=0.4)])
                fig.update_layout(height=300, margin={"l": 0, "r": 0, "t": 0, "b": 0})
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("节点状态")
                node_dist = [
                    stats["nodes"]["idle"],
                    stats["nodes"]["busy"],
                    stats["nodes"]["offline"]
                ]
                node_labels = ["空闲", "忙碌", "离线"]

                fig = go.Figure(data=[go.Pie(labels=node_labels, values=node_dist, hole=0.4)])
                fig.update_layout(height=300, margin={"l": 0, "r": 0, "t": 0, "b": 0})
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("无法获取系统统计信息")

    with tab5:
        st.subheader("任务结果")
        st.info("任务完成后结果将显示在这里。")

else:
    st.info("请登录以使用平台。")

st.markdown("""
<div class="footer">
    <p>IdleSense • 分布式计算平台 • 版本 2.0</p>
    <p>仅供研究和教育目的使用。</p>
</div>
""", unsafe_allow_html=True)
