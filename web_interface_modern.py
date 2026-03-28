"""
web_interface_modern.py
闲置计算加速器 - 现代风格网页控制界面
设计特点：渐变色彩、玻璃态效果、现代卡片设计
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

from config.settings import settings
from legacy.token_economy import ResourceMetrics, TokenEconomy

# ==================== 现代风格配置 ====================

MODERN_STYLE = """
<style>
    /* 导入现代字体 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * {
        font-family: 'Inter', sans-serif;
    }

    /* 全局背景渐变 */
    .stApp {
        background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 50%, #581c87 100%);
        min-height: 100vh;
    }

    /* 主标题样式 - 现代渐变 */
    .main-header {
        text-align: center;
        padding: 3rem 0;
        margin-bottom: 2rem;
        background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }

    .main-header h1 {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        letter-spacing: -0.02em;
    }

    .main-header p {
        font-size: 1.2rem;
        color: rgba(255,255,255,0.8);
        font-weight: 300;
    }

    /* 玻璃态卡片样式 */
    .glass-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.05) 100%);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 24px;
        padding: 2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }

    /* 侧边栏玻璃态 */
    .sidebar-glass {
        background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
        backdrop-filter: blur(10px);
        border-radius: 0 24px 24px 0;
        padding: 1.5rem;
    }

    /* 侧边栏标题 */
    .sidebar-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: rgba(255,255,255,0.9);
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 1rem;
    }

    /* 现代按钮样式 */
    .stButton button {
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600;
        padding: 0.75rem 1.5rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(96, 165, 250, 0.4);
    }

    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(96, 165, 250, 0.6);
    }

    /* 二级按钮 */
    .secondary-btn {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        color: white !important;
        box-shadow: none !important;
    }

    /* 指标卡样式 - 渐变玻璃态 */
    .metric-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.08) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 20px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
    }

    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.2);
    }

    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .metric-label {
        font-size: 0.9rem;
        color: rgba(255,255,255,0.9);
        font-weight: 500;
        margin-top: 0.5rem;
    }

    /* 标签页样式 - 现代风格 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        padding-bottom: 0.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 16px !important;
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: rgba(255,255,255,0.8) !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(96, 165, 250, 0.4);
    }

    /* 文本颜色 */
    .white-text {
        color: rgba(255,255,255,0.95) !important;
    }

    .white-text-soft {
        color: rgba(255,255,255,0.8) !important;
    }

    /* 输入框样式 */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 12px !important;
        color: white !important;
    }

    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: rgba(255,255,255,0.5) !important;
    }

    /* 滑块样式 */
    .stSlider [data-baseweb="slider"] {
        padding: 0.5rem 0;
    }

    /* 分割线 */
    .section-divider {
        border: none;
        border-top: 1px solid rgba(255,255,255,0.1);
        margin: 2rem 0;
    }

    /* 状态指示器 */
    .status-online {
        color: #34d399;
        font-weight: 600;
    }

    .status-offline {
        color: #f87171;
        font-weight: 600;
    }

    /* 页脚 */
    .footer {
        text-align: center;
        padding: 3rem 0;
        margin-top: 3rem;
        border-top: 1px solid rgba(255,255,255,0.1);
        color: rgba(255,255,255,0.6);
        font-size: 0.9rem;
    }

    /* 成功/警告/错误消息样式 */
    .stSuccess, .stWarning, .stError {
        border-radius: 16px !important;
        border: none !important;
    }

    /* Info box 样式 */
    .stInfo {
        background: linear-gradient(135deg, rgba(96,165,250,0.2) 0%, rgba(167,139,250,0.2) 100%) !important;
        border: 1px solid rgba(96,165,250,0.3) !important;
        color: rgba(255,255,255,0.9) !important;
        border-radius: 16px !important;
    }

    /* Subheader 样式 */
    h3 {
        color: rgba(255,255,255,0.95) !important;
        font-weight: 600 !important;
    }

    /* DataFrame 样式 */
    .dataframe {
        background: rgba(255,255,255,0.1) !important;
        border-radius: 16px !important;
    }

    /* 装饰性图形 */
    .decoration-circle {
        position: fixed;
        border-radius: 50%;
        filter: blur(60px);
        opacity: 0.4;
        pointer-events: none;
        z-index: 0;
    }

    .circle-1 {
        width: 400px;
        height: 400px;
        background: linear-gradient(135deg, #60a5fa, #a78bfa);
        top: -100px;
        right: -100px;
    }

    .circle-2 {
        width: 300px;
        height: 300px;
        background: linear-gradient(135deg, #f472b6, #fb7185);
        bottom: -50px;
        left: -50px;
    }
</style>
"""

# ==================== 模块导入 ====================

try:
    from legacy.distributed_task import (  # noqa: F401
        DISTRIBUTED_TASK_TEMPLATES,
        DistributedTaskManager,
    )
    DISTRIBUTED_TASK_AVAILABLE = True
except ImportError:
    DISTRIBUTED_TASK_AVAILABLE = False

try:
    from legacy.file_drop_and_recovery import (  # noqa: F401
        FileDropManager,
        create_file_drop_task_interface,
    )
    FILE_DROP_AVAILABLE = True
except ImportError:
    FILE_DROP_AVAILABLE = False

# ==================== 页面配置 ====================

st.set_page_config(
    page_title="闲置计算加速器 | 分布式计算平台",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(MODERN_STYLE, unsafe_allow_html=True)

# 添加装饰性背景图形
st.markdown("""
<div class="decoration-circle circle-1"></div>
<div class="decoration-circle circle-2"></div>
""", unsafe_allow_html=True)

SCHEDULER_URL = settings.SCHEDULER.URL
REFRESH_INTERVAL = settings.WEB.REFRESH_INTERVAL

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

# ==================== 初始化管理器 ====================

user_manager = UserManager()

if 'token_economy' not in st.session_state:
    st.session_state.token_economy = TokenEconomy()

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
    ('share_memory_value', 8192),
    ('node_start_time', None),
    ('last_uptime_reward', None)
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ==================== API 函数 ====================

def get_user_token_account(user_id: str) -> dict:
    """获取用户 Token 账户信息"""
    economy = st.session_state.token_economy
    account = economy.get_account(user_id)

    if not account:
        economy.create_account(user_id, initial_balance=1000.0)
        account = economy.get_account(user_id)

    return {
        "balance": account.balance,
        "staked": account.staked,
        "locked": account.locked,
        "reputation": account.reputation,
        "total_earned": account.total_earned,
        "total_spent": account.total_spent,
        "tasks_completed": account.tasks_completed,
        "tasks_failed": account.tasks_failed
    }

def estimate_task_cost(cpu: float, memory: int, timeout: int, priority: float = 0.0) -> dict:
    """估算任务成本"""
    economy = st.session_state.token_economy
    resources = ResourceMetrics(
        cpu_seconds=cpu * timeout,
        memory_gb_seconds=(memory / 1024) * timeout
    )

    base_price = economy.pricing.calculate_price(resources, priority=priority)
    congestion = economy.pricing._congestion_level

    return {
        "base_price": round(base_price, 4),
        "congestion_factor": round(congestion, 2),
        "final_price": round(base_price * congestion, 4),
        "priority_fee": round(base_price * 0.1 * priority, 4) if priority > 0 else 0
    }

def stake_tokens(user_id: str, amount: float) -> tuple:
    """质押 Token"""
    economy = st.session_state.token_economy
    try:
        economy.stake(user_id, amount)
        return True, {"amount": amount, "message": f"成功质押 {amount} CMP"}
    except Exception as e:
        return False, {"error": str(e)}

def unstake_tokens(user_id: str, amount: float) -> tuple:
    """解除质押"""
    economy = st.session_state.token_economy
    try:
        unstaked = economy.unstake(user_id, amount)
        return True, {"amount": unstaked, "message": f"成功解除质押 {unstaked} CMP"}
    except Exception as e:
        return False, {"error": str(e)}

def check_uptime_reward(node_id: str, capacity: dict) -> dict:
    """检查并发放在线时间奖励"""
    economy = st.session_state.token_economy

    if st.session_state.node_start_time is None:
        st.session_state.node_start_time = time.time()
        return {"rewarded": False, "message": "开始计时"}

    current_time = time.time()
    uptime_seconds = current_time - st.session_state.node_start_time

    last_reward = st.session_state.last_uptime_reward or 0
    time_since_last_reward = current_time - last_reward

    if time_since_last_reward >= 60:
        reward_seconds = min(uptime_seconds, time_since_last_reward)
        success, result = economy.reward_node_uptime(
            node_id=node_id,
            uptime_seconds=reward_seconds,
            capacity=capacity
        )
        if success:
            st.session_state.last_uptime_reward = current_time
            return {
                "rewarded": True,
                "amount": result["amount"],
                "uptime_seconds": reward_seconds
            }

    return {"rewarded": False, "uptime_seconds": uptime_seconds}

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
        online_nodes = sum(1 for node in all_nodes if node.get("is_online", False))

        if "nodes" not in health_data:
            health_data["nodes"] = {}
        health_data["nodes"]["online"] = online_nodes
        health_data["nodes"]["total"] = len(all_nodes)

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
            "status": "在线" if is_online else "离线",
            "status_detail": "空闲" if is_idle else "忙碌" if is_online else "离线",
            "platform": node.get("platform", "unknown"),
            "owner": node.get("tags", {}).get("user_id", "未知")
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

def get_all_results():
    return safe_api_call(requests.get, f"{SCHEDULER_URL}/results", timeout=5)

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
        },
        "nodes": {
            "idle": nodes_info.get("idle", 0),
            "busy": nodes_info.get("online", 0) - nodes_info.get("idle", 0),
            "offline": nodes_info.get("offline", 0),
            "total": nodes_info.get("total", 0)
        }
    }

# ==================== 主页面 ====================

st.markdown("""
<div class="main-header">
    <h1>闲置计算加速器</h1>
    <p>闲置计算资源分布式计算平台</p>
</div>
""", unsafe_allow_html=True)

# ==================== 侧边栏 ====================

with st.sidebar:
    st.markdown('<div class="sidebar-glass">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">系统状态</div>', unsafe_allow_html=True)

    health_ok, health_info = check_scheduler_health()

    if health_ok:
        st.success("✅ 调度器在线")

        col1, col2 = st.columns(2)
        with col1:
            online = health_info.get("nodes", {}).get("online", 0)
            st.metric("可用节点", online)

        with col2:
            if st.button("↻", help="刷新状态"):
                st.rerun()
    else:
        st.error("❌ 调度器离线")
        st.code("运行: python legacy/scheduler/simple_server.py", language="bash")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">用户会话</div>', unsafe_allow_html=True)

    if st.session_state.user_session:
        st.success(f"✅ {st.session_state.user_session.get('username', '用户')}")

        user_id = st.session_state.user_session.get("user_id")
        if user_id:
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-title">💰 Token账户</div>', unsafe_allow_html=True)

            account = get_user_token_account(user_id)

            st.metric("余额", f"{account['balance']:,.2f} CMP")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("质押", f"{account['staked']:,.0f}")
            with col2:
                tier = st.session_state.token_economy.reputation.get_reputation_tier(account['reputation'])
                st.metric(f"声誉 ({tier})", f"{account['reputation']:.0f}")

            with st.expander("💎 质押管理"):
                stake_amount = st.number_input("质押数量", min_value=10.0, max_value=account['balance'], value=10.0, step=10.0)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("质押", use_container_width=True):
                        success, result = stake_tokens(user_id, stake_amount)
                        if success:
                            st.toast(f"✅ {result['message']}", icon="✅")
                            st.rerun()
                        else:
                            st.toast(f"❌ {result['error']}", icon="❌")
                with col2:
                    if st.button("解除质押", use_container_width=True):
                        success, result = unstake_tokens(user_id, stake_amount)
                        if success:
                            st.toast(f"✅ {result['message']}", icon="✅")
                            st.rerun()
                        else:
                            st.toast(f"❌ {result['error']}", icon="❌")

        if st.button("退出登录"):
            st.markdown("<script>localStorage.removeItem('idle_accelerator_session');</script>", unsafe_allow_html=True)
            st.session_state.user_session = None
            st.query_params.clear()
            st.rerun()
    else:
        st.warning("🔒 未登录")
        username = st.text_input("用户名", key="sidebar_username")

        if st.button("快速登录") and username:
            user_id = f"local_{hashlib.md5(username.encode()).hexdigest()[:8]}"
            user_manager.save_user(user_id, username, "project")
            session_data = {
                "username": username,
                "user_id": user_id
            }
            st.session_state.user_session = session_data
            st.session_state.token_balance = 1000.0
            st.session_state.staked_balance = 0.0
            st.session_state.reputation_score = 50.0
            st.markdown(f"""
            <script>
            localStorage.setItem('idle_accelerator_session', JSON.stringify({json.dumps(session_data)}));
            </script>
            """, unsafe_allow_html=True)
            st.toast(f"✅ 欢迎 {username}，获得1000 CMP初始余额！", icon="✅")
            time.sleep(0.5)
            st.rerun()

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">资源分配</div>', unsafe_allow_html=True)

    cpu_value = st.session_state.get('share_cpu_value', 4.0)
    memory_value = st.session_state.get('share_memory_value', 8192)

    cpu_share = st.slider("共享CPU核心数", 0.5, 16.0, cpu_value, 0.5)
    st.session_state.share_cpu_value = cpu_share

    memory_share = st.slider("共享内存大小 (MB)", 512, 32768, memory_value, 512)
    st.session_state.share_memory_value = memory_share

    st.info(f"📊 共享: {cpu_share} 核心, {memory_share}MB 内存")
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== 主内容区 ====================

if st.session_state.user_session:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 提交任务", "📊 任务监控", "🖥️ 节点管理", "📈 系统统计", "📋 任务结果"])

    with tab1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("🚀 提交计算任务")

        task_type = st.radio("任务类型", ["单节点", "分布式"], horizontal=True,
                            disabled=not DISTRIBUTED_TASK_AVAILABLE)

        if task_type == "分布式" and not DISTRIBUTED_TASK_AVAILABLE:
            st.error("分布式任务模块不可用")

        if task_type == "单节点":
            st.info("💡 单节点任务在一个节点上执行。大型工作负载请使用分布式任务。")

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

            if st.button("✨ 提交任务", use_container_width=True):
                if not code.strip():
                    st.toast("⚠️ 请输入Python代码", icon="⚠️")
                else:
                    with st.spinner("提交任务中..."):
                        success, result = submit_task(code, timeout, cpu_request, memory_request)

                        if success:
                            task_id = result.get("task_id")
                            user_id = st.session_state.user_session.get("user_id")

                            cost_info = estimate_task_cost(cpu_request, memory_request, timeout, priority=0.0)
                            st.toast(f"✅ 任务提交成功！任务ID: {task_id} | 预估费用: {cost_info['final_price']} CMP", icon="✅")
                        else:
                            st.toast(f"❌ 提交失败: {result.get('error', '未知错误')}", icon="❌")

        else:
            st.info("🚀 分布式任务利用多个节点进行并行处理。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📊 任务监控")

        if st.button("🔄 刷新任务列表"):
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
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("🖥️ 节点管理")

        col_act, col_stop = st.columns(2)
        with col_act:
            if st.button("🚀 激活本机节点", use_container_width=True, type="primary"):
                user_id = None
                if st.session_state.user_session:
                    user_id = st.session_state.user_session.get("user_id")
                success, result = safe_api_call(
                    requests.post,
                    f"{SCHEDULER_URL}/api/nodes/activate-local",
                    json={
                        "cpu_limit": st.session_state.share_cpu_value,
                        "memory_limit": st.session_state.share_memory_value,
                        "storage_limit": 10240,
                        "user_id": user_id
                    },
                    timeout=10
                )
                if success and result.get("success"):
                    node_id = result.get("node_id", "unknown")
                    st.toast(f"✅ 节点激活成功: {node_id}", icon="✅")
                    st.session_state.local_node_id = node_id
                    st.session_state.node_start_time = time.time()
                    st.session_state.last_uptime_reward = time.time()

                    if user_id:
                        account = get_user_token_account(user_id)
                        st.toast("💰 账户已创建， 1000 CMP 初始余额", icon="💰")
                else:
                    error_msg = result.get("error", "未知错误") if success else result
                    st.toast(f"❌ 激活失败: {error_msg}", icon="❌")

        with col_stop:
            local_node_id = st.session_state.get("local_node_id")
            if local_node_id:
                if st.button("🛑 停止本机节点", use_container_width=True):
                    success, result = safe_api_call(
                        requests.post,
                        f"{SCHEDULER_URL}/api/nodes/{local_node_id}/stop",
                        timeout=5
                    )
                    if success and result.get("success"):
                        st.toast(f"✅ 节点已停止: {local_node_id}", icon="✅")

                        user_id = st.session_state.user_session.get("user_id") if st.session_state.user_session else None
                        if user_id:
                            uptime_seconds = time.time() - st.session_state.node_start_time if st.session_state.node_start_time else 0
                            capacity = {
                                "cpu": st.session_state.share_cpu_value,
                                "memory": st.session_state.share_memory_value
                            }
                            success, reward_result = check_uptime_reward(local_node_id, capacity)
                            if success and reward_result.get("rewarded"):
                                amount = reward_result.get("amount", 0)
                                st.toast(f"🎉 在线奖励: {amount:.2f} CMP (在线 {reward_result['uptime_seconds']:.0f}秒)", icon="🎉")

                        st.session_state.local_node_id = None
                        st.session_state.node_start_time = None
                    else:
                        error_msg = result.get("error", "未知错误") if success else result
                        st.toast(f"❌ 停止失败: {error_msg}", icon="❌")
            else:
                st.button("🛑 停止本机节点", use_container_width=True, disabled=True)

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        if st.session_state.get("local_node_id"):
            with st.expander("⏱ 在线时间奖励"):
                if st.session_state.node_start_time:
                    uptime = time.time() - st.session_state.node_start_time
                    uptime_minutes = uptime / 60
                    next_reward = 60 - (uptime % 60)
                    st.info(f"⏱ 在线时间: {uptime_minutes:.0f} 分钟 | 下次奖励: {next_reward:.1f} 分钟")
                    progress_value = min(uptime_minutes / 60, 1.0)
                    st.progress(progress_value)
                    st.metric("在线进度", f"{uptime_minutes:.0f} 分钟")
                else:
                    st.info("节点未激活")

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
        st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📈 系统统计")

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

            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 任务分布")
                task_dist = [
                    stats["tasks"]["completed"],
                    stats["tasks"]["failed"],
                    stats["tasks"]["total"] - stats["tasks"]["completed"] - stats["tasks"]["failed"]
                ]
                task_labels = ["已完成", "失败", "待处理"]

                fig = go.Figure(data=[go.Pie(labels=task_labels, values=task_dist, hole=0.4)])
                fig.update_layout(
                    height=300,
                    margin={"l": 0, "r": 0, "t": 0, "b": 0},
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("🖥️ 节点状态")
                node_dist = [
                    stats["nodes"]["idle"],
                    stats["nodes"]["busy"],
                    stats["nodes"]["offline"]
                ]
                node_labels = ["空闲", "忙碌", "离线"]

                fig = go.Figure(data=[go.Pie(labels=node_labels, values=node_dist, hole=0.4)])
                fig.update_layout(
                    height=300,
                    margin={"l": 0, "r": 0, "t": 0, "b": 0},
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)

            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.subheader("💰 Token经济")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总供应量", "1,000,000,000", "CMP")
            with col2:
                st.metric("流通量", f"{stats['tasks']['completed'] * 100:,}", "CMP")
            with col3:
                st.metric("活跃质押", f"{stats['nodes']['idle'] * 500:,}", "CMP")
            with col4:
                st.metric("任务奖励池", f"{max(0, 100000 - stats['tasks']['completed'] * 10):,}", "CMP")

            st.info("💡 完成任务可获得CMP奖励，质押CMP可提高任务优先级。")
        else:
            st.warning("无法获取系统统计信息")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab5:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📋 任务结果")
        st.info("任务完成后结果将显示在这里。")
        st.markdown('</div>', unsafe_allow_html=True)

else:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.info("🔐 请登录以使用平台。")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="footer">
    <p>✨ 闲置计算加速器 • 分布式计算平台 • 版本 2.0</p>
    <p>仅供研究和教育目的使用。</p>
</div>
""", unsafe_allow_html=True)
