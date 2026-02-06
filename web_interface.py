"""
web_interface.py
闲置计算加速器 - 网页控制界面
使用 Streamlit 构建，无需前端知识
"""

import streamlit as st
import requests
import time
import json
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(
    page_title="闲置计算加速器",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 配置
SCHEDULER_URL = "http://localhost:8000"
REFRESH_INTERVAL = 10  # 自动刷新间隔（秒）

# 初始化 session state
if 'task_history' not in st.session_state:
    st.session_state.task_history = []
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# 工具函数
def check_scheduler_health():
    """检查调度中心是否在线"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/", timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except:
        return False, None

def submit_task(code, timeout=300, cpu=1.0, memory=512):
    """提交任务到调度中心"""
    try:
        payload = {
            "code": code,
            "timeout": timeout,
            "resources": {
                "cpu": cpu,
                "memory": memory
            }
        }
        response = requests.post(
            f"{SCHEDULER_URL}/submit",
            json=payload,
            timeout=10
        )
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except Exception as e:
        return False, {"error": str(e)}

def get_task_status(task_id):
    """获取任务状态"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/status/{task_id}", timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except:
        return False, None

def get_all_nodes():
    """获取所有节点信息"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/nodes", timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except:
        return False, None

def get_system_stats():
    """获取系统统计"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/stats", timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except:
        return False, None

# 页面标题
st.title("⚡ 闲置计算加速器")
st.markdown("利用个人电脑闲置算力的分布式计算平台")

# 侧边栏
with st.sidebar:
    st.header("控制面板")
    
    # 调度中心状态
    st.subheader("调度中心状态")
    health_ok, health_info = check_scheduler_health()
    
    if health_ok:
        st.success(f"✅ 在线 (v{health_info.get('version', '1.0.0')})")
        st.caption(f"队列任务: {health_info.get('queue_size', 0)}")
        st.caption(f"运行时间: {health_info.get('uptime', 0)}秒")
    else:
        st.error("❌ 离线")
        st.caption("请确保调度中心正在运行")
    
    st.divider()
    
    # 自动刷新控制
    st.subheader("自动刷新")
    auto_refresh = st.checkbox("启用自动刷新", value=st.session_state.auto_refresh)
    st.session_state.auto_refresh = auto_refresh
    
    if auto_refresh:
        refresh_interval = st.slider("刷新间隔(秒)", 5, 60, REFRESH_INTERVAL)
        REFRESH_INTERVAL = refresh_interval
        
        # 自动刷新逻辑
        time_since_refresh = (datetime.now() - st.session_state.last_refresh).seconds
        if time_since_refresh >= REFRESH_INTERVAL:
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    
    st.divider()
    
    # 示例代码
    st.subheader("示例代码")
    example_code = st.selectbox(
        "选择示例",
        ["简单计算", "数据处理", "模拟计算", "自定义"]
    )
    
    examples = {
        "简单计算": """# 简单数学计算
result = 0
for i in range(1000000):
    result += i * 0.001
print(f"计算结果: {result:.2f}")""",
        
        "数据处理": """# 数据处理示例
import random

# 生成测试数据
data = [random.randint(1, 1000) for _ in range(10000)]

# 计算统计信息
mean = sum(data) / len(data)
variance = sum((x - mean) ** 2 for x in data) / len(data)
std_dev = variance ** 0.5

print(f"数据量: {len(data)}")
print(f"平均值: {mean:.2f}")
print(f"标准差: {std_dev:.2f}")
print(f"最大值: {max(data)}")
print(f"最小值: {min(data)}")""",
        
        "模拟计算": """# 蒙特卡洛模拟计算π
import random
import math

num_points = 1000000
points_inside = 0

for _ in range(num_points):
    x = random.random()
    y = random.random()
    
    if math.sqrt(x**2 + y**2) <= 1:
        points_inside += 1

pi_estimate = 4 * points_inside / num_points
print(f"π的估计值: {pi_estimate}")
print(f"与真实π的误差: {abs(pi_estimate - math.pi):.6f}")"""
    }
    
    if example_code != "自定义":
        st.code(examples[example_code], language="python")

# 主界面 - 标签页布局
tab1, tab2, tab3, tab4 = st.tabs(["📝 提交任务", "📊 任务监控", "🖥️ 节点管理", "📈 系统统计"])

# 标签页1: 提交任务
with tab1:
    st.header("提交计算任务")
    
    # 任务配置
    col1, col2 = st.columns(2)
    
    with col1:
        timeout = st.number_input("超时时间(秒)", min_value=10, max_value=3600, value=300, step=10)
        cpu_request = st.slider("CPU需求(核心)", 0.1, 8.0, 1.0, 0.1)
    
    with col2:
        memory_request = st.number_input("内存需求(MB)", min_value=64, max_value=8192, value=512, step=64)
    
    # 代码编辑器
    st.subheader("Python代码")
    if example_code != "自定义" and example_code in examples:
        default_code = examples[example_code]
    else:
        default_code = """# 在这里输入你的Python代码
# 任务执行结果将通过print()输出
# 或者赋值给 __result__ 变量

print("Hello from idle computer!")

# 示例：计算斐波那契数列
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(20)
print(f"斐波那契数列第20项: {result}")"""
    
    code = st.text_area(
        "输入Python代码",
        value=default_code,
        height=300,
        label_visibility="collapsed"
    )
    
    # 提交按钮
    if st.button("🚀 提交任务", type="primary", use_container_width=True):
        if not code.strip():
            st.error("请输入Python代码")
        else:
            with st.spinner("提交任务中..."):
                success, result = submit_task(code, timeout, cpu_request, memory_request)
                
                if success:
                    task_id = result.get("task_id")
                    st.success(f"✅ 任务提交成功！任务ID: `{task_id}`")
                    
                    # 添加到历史记录
                    st.session_state.task_history.append({
                        "task_id": task_id,
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "status": "submitted",
                        "code_preview": code[:100] + ("..." if len(code) > 100 else "")
                    })
                    
                    # 显示任务详情
                    with st.expander("任务详情", expanded=True):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("任务ID", task_id)
                        with col2:
                            st.metric("超时时间", f"{timeout}秒")
                        with col3:
                            st.metric("资源需求", f"CPU: {cpu_request}, 内存: {memory_request}MB")
                else:
                    st.error(f"❌ 提交失败: {result.get('error', '未知错误')}")

# 标签页2: 任务监控
with tab2:
    st.header("任务监控")
    
    # 任务历史
    if st.session_state.task_history:
        st.subheader("任务历史")
        
        # 转换为DataFrame显示
        history_df = pd.DataFrame(st.session_state.task_history)
        st.dataframe(
            history_df,
            column_config={
                "task_id": "任务ID",
                "time": "提交时间",
                "status": "状态",
                "code_preview": "代码预览"
            },
            use_container_width=True,
            hide_index=True
        )
        
        # 选择任务查看详情
        if not history_df.empty:
            selected_task = st.selectbox(
                "选择任务查看详情",
                history_df["task_id"].tolist()
            )
            
            if selected_task:
                with st.spinner("获取任务状态..."):
                    success, task_info = get_task_status(selected_task)
                    
                    if success:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            status_color = {
                                "pending": "🟡",
                                "running": "🔵", 
                                "completed": "🟢",
                                "failed": "🔴"
                            }.get(task_info.get("status", "pending"), "⚪")
                            st.metric("状态", f"{status_color} {task_info.get('status', 'unknown')}")
                        
                        with col2:
                            if task_info.get("created_at"):
                                created = datetime.fromtimestamp(task_info["created_at"])
                                st.metric("创建时间", created.strftime("%H:%M:%S"))
                        
                        with col3:
                            if task_info.get("completed_at"):
                                completed = datetime.fromtimestamp(task_info["completed_at"])
                                duration = task_info["completed_at"] - task_info["created_at"]
                                st.metric("执行时间", f"{duration:.1f}秒")
                        
                        # 显示结果
                        if task_info.get("result"):
                            st.subheader("执行结果")
                            st.code(task_info["result"], language="text")
                        
                        # 执行节点信息
                        if task_info.get("executed_on"):
                            st.info(f"执行节点: {task_info['executed_on']}")
                    else:
                        st.warning("无法获取任务详情")
    else:
        st.info("暂无任务历史，请先提交任务")

# 标签页3: 节点管理
with tab3:
    st.header("计算节点管理")
    
    success, nodes_info = get_all_nodes()
    
    if success and nodes_info.get("nodes"):
        nodes = nodes_info["nodes"]
        total_nodes = nodes_info.get("total_nodes", 0)
        idle_nodes = nodes_info.get("total_idle", 0)
        
        # 节点统计
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总节点数", total_nodes)
        with col2:
            st.metric("闲置节点", idle_nodes)
        with col3:
            st.metric("忙碌节点", total_nodes - idle_nodes)
        
        # 节点列表
        st.subheader("节点列表")
        
        for node in nodes:
            with st.expander(f"{node.get('node_id', '未知节点')} - {node.get('status', 'unknown')}", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**基本信息**")
                    st.write(f"状态: `{node.get('status', 'N/A')}`")
                    st.write(f"平台: `{node.get('platform', 'N/A')}`")
                    
                    if node.get("idle_since"):
                        idle_since = datetime.fromisoformat(node["idle_since"].replace('Z', '+00:00'))
                        st.write(f"闲置开始: `{idle_since.strftime('%H:%M:%S')}`")
                
                with col2:
                    st.write("**资源配置**")
                    resources = node.get("resources", {})
                    st.write(f"CPU核心: `{resources.get('cpu_cores', 'N/A')}`")
                    st.write(f"内存: `{resources.get('memory_mb', 'N/A')} MB`")
                
                # 节点贡献
                if node.get("completed_tasks"):
                    st.write(f"已完成任务: `{node.get('completed_tasks', 0)}`")
                    st.write(f"总计算时间: `{node.get('total_compute_time', 0)}` 秒")
    else:
        st.warning("暂无节点信息或调度中心离线")

# 标签页4: 系统统计
with tab4:
    st.header("系统统计")
    
    success, stats = get_system_stats()
    
    if success:
        # 关键指标
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            tasks = stats.get("tasks", {})
            st.metric("总任务数", tasks.get("total", 0))
        
        with col2:
            st.metric("成功率", f"{tasks.get('completed', 0) / max(tasks.get('total', 1), 1) * 100:.1f}%")
        
        with col3:
            st.metric("平均用时", f"{tasks.get('avg_time', 0):.1f}秒")
        
        with col4:
            throughput = stats.get("throughput", {})
            st.metric("计算时数", f"{throughput.get('compute_hours', 0):.1f}")
        
        # 可视化图表
        st.subheader("性能图表")
        
        # 创建图表
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("任务状态分布", "节点状态分布", "任务完成时间趋势", "资源利用率"),
            specs=[[{"type": "pie"}, {"type": "pie"}],
                   [{"type": "bar"}, {"type": "scatter"}]]
        )
        
        # 任务状态饼图
        if tasks:
            task_labels = ["完成", "失败", "进行中"]
            task_values = [
                tasks.get("completed", 0),
                tasks.get("failed", 0),
                max(tasks.get("total", 0) - tasks.get("completed", 0) - tasks.get("failed", 0), 0)
            ]
            fig.add_trace(
                go.Pie(labels=task_labels, values=task_values, hole=.3),
                row=1, col=1
            )
        
        # 节点状态饼图
        nodes_info = stats.get("nodes", {})
        if nodes_info:
            node_labels = ["闲置", "忙碌", "离线"]
            node_values = [
                nodes_info.get("idle", 0),
                nodes_info.get("busy", 0),
                nodes_info.get("offline", 0)
            ]
            fig.add_trace(
                go.Pie(labels=node_labels, values=node_values, hole=.3),
                row=1, col=2
            )
        
        # 更新布局
        fig.update_layout(
            height=600,
            showlegend=True,
            title_text="系统监控仪表盘",
            template="plotly_dark"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 原始数据
        with st.expander("查看原始数据"):
            st.json(stats)
    else:
        st.info("等待系统运行数据...")

# 页脚
st.divider()
st.caption("闲置计算加速器 v1.0.0 | 开源免费项目")
✨ 界面特点 1.  四标签页布局： ◦  📝 提交任务：代码编辑器+资源配置  ◦  📊 任务监控：实时状态+历史记录  ◦  🖥️ 节点管理：节点列表+状态监控  ◦  📈 系统统计：可视化图表+性能指标  
2.  交互功能： ◦  示例代码选择  ◦  自动刷新控制  ◦  任务历史记录  ◦  实时状态监控  ◦  可视化图表   
3.  用户体验： ◦  响应式布局  ◦  暗色主题  ◦  实时反馈  ◦  错误处理
🚀 启动方法 创建完成后，运行： bash 复制   下载    # 1. 安装streamlit（如果还没安装）
pip install streamlit

# 2. 确保调度中心正在运行
python scheduler/simple_server.py

# 3. 启动网页界面
streamlit run web_interface.py
