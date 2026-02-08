"""
web_interface.py
闲置计算加速器 - 网页控制界面
修复版：适配新版调度中心API
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

# 工具函数 - 增强错误处理
def check_scheduler_health():
    """检查调度中心是否在线"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        else:
            # 尝试获取健康端点
            try:
                health_response = requests.get(f"{SCHEDULER_URL}/health", timeout=3)
                if health_response.status_code == 200:
                    return True, health_response.json()
            except:
                pass
            return False, {"error": f"HTTP {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return False, {"error": "无法连接到调度中心"}
    except Exception as e:
        return False, {"error": str(e)}

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
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}: {response.text}"}
    except requests.exceptions.ConnectionError:
        return False, {"error": "无法连接到调度中心"}
    except Exception as e:
        return False, {"error": str(e)}

def get_task_status(task_id):
    """获取任务状态"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/status/{task_id}", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}"}
    except:
        return False, {"error": "请求失败"}

def delete_task(task_id):
    """删除任务"""
    try:
        response = requests.delete(f"{SCHEDULER_URL}/api/tasks/{task_id}", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}: {response.text}"}
    except requests.exceptions.ConnectionError:
        return False, {"error": "无法连接到调度中心"}
    except Exception as e:
        return False, {"error": str(e)}

def get_all_nodes():
    """获取所有节点信息 - 修复版：使用新版API"""
    try:
        # 先尝试新版API
        response = requests.get(f"{SCHEDULER_URL}/api/nodes", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # 转换数据结构以兼容原有界面
            nodes = []
            for node in data.get("nodes", []):
                nodes.append({
                    "node_id": node.get("node_id", "unknown"),
                    "status": "online" if node.get("is_online", True) else "offline",
                    "platform": node.get("platform", "unknown"),
                    "idle_since": None,  # 新版API暂无此字段
                    "resources": {
                        "cpu_cores": node.get("capacity", {}).get("cpu", "N/A"),
                        "memory_mb": node.get("capacity", {}).get("memory", "N/A")
                    },
                    "completed_tasks": 0,  # 新版API暂无此字段
                    "total_compute_time": 0  # 新版API暂无此字段
                })
            return True, {
                "nodes": nodes,
                "total_nodes": len(nodes),
                "total_idle": sum(1 for n in nodes if n.get("status") == "online")
            }
        
        # 如果新版API失败，尝试旧端点（兼容性）
        response = requests.get(f"{SCHEDULER_URL}/nodes", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        
        return False, {"error": f"HTTP {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return False, {"error": "无法连接到调度中心"}
    except Exception as e:
        return False, {"error": str(e)}

def get_system_stats():
    """获取系统统计"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # 转换数据结构以兼容原有界面
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
        else:
            return False, {"error": f"HTTP {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return False, {"error": "无法连接到调度中心"}
    except Exception as e:
        return False, {"error": str(e)}

def get_all_results():
    """获取所有任务结果"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/results", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}"}
    except:
        return False, {"error": "请求失败"}

# 页面标题
st.title("⚡ 闲置计算加速器")
st.markdown("利用个人电脑闲置算力的分布式计算平台")

# 侧边栏
with st.sidebar:
    st.header("控制面板")
    
    # 用户登录状态
    st.subheader("用户状态")
    
    # 检查用户是否已登录
    if 'user_session' not in st.session_state:
        st.session_state.user_session = None
    
    if st.session_state.user_session:
        st.success("✅ 已登录")
        st.caption(f"用户: {st.session_state.user_session.get('username', '未知')}")
        
        if st.button("🚪 退出登录"):
            st.session_state.user_session = None
            st.rerun()
    else:
        st.warning("🔒 未登录")
        st.caption("登录后可享受完整功能")
        
        # 用户注册/登录
        with st.expander("用户管理", expanded=False):
            tab_login, tab_register = st.tabs(["登录", "注册"])
            
            with tab_register:
                st.markdown("### 新用户注册")
                
                reg_username = st.text_input("用户名", key="reg_username")
                reg_email = st.text_input("邮箱", key="reg_email")
                
                # 文件夹使用协议
                st.markdown("### 本地操作授权")
                
                # 强制用户阅读并同意
                with st.container():
                    st.markdown("#### 文件夹使用协议")
                    st.markdown("""
                    使用本系统需要同意在您的设备上创建以下文件夹：
                    - **用户数据文件夹**: `node_data/user_data/{您的用户ID}`
                    - **临时数据文件夹**: `node_data/temp_data/{您的用户ID}`
                    
                    所有操作均由您主动授权发起，操作结果由您自行负责。
                    """)
                    
                    agree_folder = st.checkbox("□ 我已阅读并同意文件夹使用协议", key="agree_folder")
                    
                    st.markdown("#### 本地操作授权确认")
                    st.markdown("""
                    【本地文件操作免责声明】
                    1. 所有本地文件夹/文件操作均需用户主动点击授权后执行
                    2. 系统不会在后台进行任何未告知的本地文件操作
                    3. 操作结果及后续风险由用户自行承担责任
                    """)
                    
                    confirm_auth = st.checkbox("□ 我已确认本地操作授权", key="confirm_auth")
                
                # 显示具体的文件夹路径（增强用户体验）
                import os
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                user_data_path = os.path.join(project_root, "node_data", "user_data", "{您的用户ID}")
                temp_data_path = os.path.join(project_root, "node_data", "temp_data", "{您的用户ID}")
                
                st.markdown("#### 具体操作路径")
                st.code(f"""
用户数据文件夹: {user_data_path}
临时数据文件夹: {temp_data_path}
""", language="text")
                
                # 独立的授权确认弹窗（模拟实现）
                show_authorization_modal = st.checkbox("🔒 点击此处查看并确认本地操作授权", key="show_auth_modal")
                
                if show_authorization_modal:
                    with st.container():
                        st.markdown("---")
                        st.markdown("### 🔒 【本地操作授权确认】")
                        st.markdown("**此操作需要您明确授权才能继续**")
                        
                        # 授权弹窗内容
                        st.markdown(f"""
#### 操作详情
- **操作类型**: 文件夹创建
- **目标路径**: 
  - `{user_data_path}`
  - `{temp_data_path}`
- **操作设备**: 您的本地计算机

#### 授权声明
所有操作均由您主动授权发起，确认授权后系统将执行以下操作：
1. 在您的设备上创建上述文件夹
2. 仅在此次授权范围内执行操作
3. 不会进行任何未告知的额外操作

#### 风险提示
操作结果及后续风险由您自行承担责任。
""")
                        
                        # 强制用户手动确认
                        auth_confirmed = st.checkbox("✅ 我已阅读并确认授权本次本地操作", key="final_auth_confirm")
                        
                        if not auth_confirmed:
                            st.warning("⚠️ 请确认授权后才能继续注册")
                        
                        st.markdown("---")
                
                if st.button("📝 注册", type="primary", use_container_width=True):
                    if not reg_username or not reg_email:
                        st.error("请填写用户名和邮箱")
                    elif not agree_folder:
                        st.error("必须同意文件夹使用协议")
                    elif not confirm_auth:
                        st.error("必须确认本地操作授权")
                    elif show_authorization_modal and not auth_confirmed:
                        st.error("请完成本地操作授权确认")
                    else:
                        with st.spinner("注册中..."):
                            # 调用注册API
                            try:
                                response = requests.post(
                                    f"{SCHEDULER_URL}/api/users/register",
                                    json={
                                        "username": reg_username,
                                        "email": reg_email,
                                        "agree_folder_usage": True,
                                        "user_confirmed_authorization": True
                                    }
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    if result["success"]:
                                        st.session_state.user_session = {
                                            "session_id": result["session_id"],
                                            "user": result["user"],
                                            "username": reg_username
                                        }
                                        
                                        # 显示详细的成功信息
                                        st.success("✅ 注册成功！")
                                        
                                        # 显示文件夹创建确认
                                        user_id = result["user"]["user_id"]
                                        actual_user_path = os.path.join(project_root, "node_data", "user_data", user_id)
                                        actual_temp_path = os.path.join(project_root, "node_data", "temp_data", user_id)
                                        
                                        st.markdown("### 📁 文件夹创建确认")
                                        st.markdown(f"""
**已根据您的授权创建以下文件夹：**
- 用户数据文件夹: `{actual_user_path}`
- 临时数据文件夹: `{actual_temp_path}`

**操作记录已保存至本地日志，供您核查。**
""")
                                        
                                        st.info("💡 您现在可以开始使用系统的完整功能了！")
                                        
                                        # 延迟跳转，让用户有时间阅读确认信息
                                        time.sleep(3)
                                        st.rerun()
                                    else:
                                        st.error(f"注册失败: {result.get('error', '未知错误')}")
                                else:
                                    st.error(f"注册失败: HTTP {response.status_code}")
                            except Exception as e:
                                st.error(f"注册请求失败: {e}")
            
            with tab_login:
                st.info("当前版本暂只支持注册新用户")
                st.markdown("请使用注册功能创建新账户")
                
                # 添加文件夹管理功能（已登录用户可见）
                if st.session_state.user_session:
                    st.markdown("---")
                    st.markdown("### 📁 文件夹管理")
                    
                    user_id = st.session_state.user_session.get("user", {}).get("user_id")
                    if user_id:
                        user_data_path = os.path.join(project_root, "node_data", "user_data", user_id)
                        temp_data_path = os.path.join(project_root, "node_data", "temp_data", user_id)
                        
                        st.markdown(f"""
**您的文件夹路径：**
- 用户数据文件夹: `{user_data_path}`
- 临时数据文件夹: `{temp_data_path}`
""")
                        
                        # 文件夹操作选项
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🔍 查看文件夹", use_container_width=True):
                                st.info(f"文件夹位置: {user_data_path}")
                                st.info("您可以通过文件管理器手动访问这些文件夹")
                        
                        with col2:
                            if st.button("🗑️ 删除文件夹", use_container_width=True, type="secondary"):
                                st.warning("⚠️ 此操作将删除您的所有数据")
                                delete_confirm = st.checkbox("确认删除所有用户数据")
                                if delete_confirm:
                                    st.error("删除功能暂未实现，请手动删除文件夹")
                        
                        # 操作日志查看
                        if st.button("📋 查看操作日志", use_container_width=True):
                            log_file = os.path.join(project_root, "node_data", "logs", "local_operations.log")
                            if os.path.exists(log_file):
                                st.success("操作日志文件存在")
                                st.code(f"日志位置: {log_file}")
                            else:
                                st.info("暂无操作日志记录")
    
    st.divider()
    
    # 调度中心状态
    st.subheader("调度中心状态")
    health_ok, health_info = check_scheduler_health()
    
    if health_ok:
        st.success(f"✅ 在线 (v{health_info.get('version', '1.0.0')})")
        # 显示任务队列信息
        try:
            # 获取统计信息显示队列状态
            stats_ok, stats = get_system_stats()
            if stats_ok:
                pending = stats.get("tasks", {}).get("total", 0) - stats.get("tasks", {}).get("completed", 0)
                st.caption(f"待处理任务: {pending}")
                st.caption(f"在线节点: {stats.get('nodes', {}).get('online', 0)}")
        except:
            st.caption("状态: 运行中")
    else:
        st.error("❌ 离线")
        if "error" in health_info:
            st.caption(f"错误: {health_info['error']}")
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
        ["简单计算", "数据处理", "模拟计算", "读取用户数据", "自定义"]
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
print(f"与真实π的误差: {abs(pi_estimate - math.pi):.6f}")""",
        
        "读取用户数据": """# 读取用户数据文件夹中的文件示例

# 方法1：使用系统提供的函数读取文件
try:
    # 读取用户数据文件夹中的文件
    file_content = read_user_file("my_data.txt")
    print(f"成功读取文件内容:\n{file_content}")
except Exception as e:
    print(f"读取文件失败: {e}")
    print("请确保在user_data文件夹中放置了my_data.txt文件")

# 方法2：检查用户文件夹中的文件列表
print("\\n用户文件夹中的文件:")
user_files = list_user_files()
for file in user_files:
    print(f"- {file}")

# 方法3：使用用户文件夹路径进行计算
print(f"\\n用户文件夹路径: {USER_FOLDER}")
print(f"临时文件夹路径: {TEMP_FOLDER}")

# 示例：如果用户提供了数据文件，就使用用户数据
if user_file_exists("dataset.csv"):
    print("检测到用户数据文件，将使用用户数据进行计算")
    # 这里可以添加处理用户数据的代码
else:
    print("未检测到用户数据文件，使用默认数据进行计算")
    # 这里可以添加使用默认数据的代码
"""
    }
    
    if example_code != "自定义":
        st.code(examples[example_code], language="python")
    
    st.divider()
    
    # 快速操作
    st.subheader("快速操作")
    if st.button("🔄 手动刷新", use_container_width=True):
        st.session_state.last_refresh = datetime.now()
        st.rerun()
    
    if st.button("📋 查看所有结果", use_container_width=True):
        success, results = get_all_results()
        if success and results.get("results"):
            st.session_state.results_data = results
            # 切换到任务监控标签页的逻辑可以在这里添加
        elif not success:
            st.error(f"获取结果失败: {results.get('error', '未知错误')}")

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
    
    # 获取并显示所有结果
    if st.button("🔄 刷新任务列表", key="refresh_tasks"):
        st.rerun()
    
    success, results = get_all_results()
    if success and results.get("results"):
        results_list = results["results"]
        
        if results_list:
            st.subheader("已完成的任务")
            
            # 创建结果表格
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
                st.dataframe(
                    results_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # 选择任务查看详情
                selected_task_id = st.selectbox(
                    "选择任务查看完整结果",
                    [r["任务ID"] for r in results_data]
                )
                
                if selected_task_id:
                    # 找到完整结果
                    full_result = None
                    for result in results_list:
                        if str(result.get("task_id")) == str(selected_task_id):
                            full_result = result
                            break
                    
                    if full_result and full_result.get("result"):
                        st.subheader(f"任务 {selected_task_id} 的完整结果")
                        st.code(full_result["result"], language="text")
        else:
            st.info("暂无已完成的任务")
    elif not success:
        st.warning(f"获取任务结果失败: {results.get('error', '未知错误')}")
    
    # 任务历史（已提交但可能未完成）
    if st.session_state.task_history:
        st.subheader("任务历史记录")
        
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
        
        # 任务删除功能
        st.subheader("🗑️ 任务删除")
        
        # 获取所有任务状态以确定哪些可以删除
        deletable_tasks = []
        for task_id in history_df["task_id"].tolist():
            success, task_info = get_task_status(task_id)
            if success and task_info.get("status") in ["pending", "assigned", "running"]:
                deletable_tasks.append({
                    "task_id": task_id,
                    "status": task_info.get("status", "unknown")
                })
        
        if deletable_tasks:
            # 创建选择框
            task_options = {f"任务{task['task_id']} (状态: {task['status']})": task['task_id'] 
                          for task in deletable_tasks}
            selected_task_label = st.selectbox("选择要删除的任务", list(task_options.keys()))
            selected_task_id = task_options[selected_task_label]
            
            # 删除确认
            if st.button("🗑️ 删除选中任务", type="secondary"):
                with st.spinner("删除中..."):
                    delete_response = delete_task(selected_task_id)
                    
                    if delete_response[0]:  # success
                        st.success("✅ 任务删除成功！")
                        # 从历史记录中移除已删除的任务
                        st.session_state.task_history = [
                            task for task in st.session_state.task_history 
                            if task["task_id"] != selected_task_id
                        ]
                        st.rerun()  # 刷新页面
                    else:
                        st.error(f"❌ 删除失败: {delete_response[1].get('error', '未知错误')}")
        else:
            st.info("暂无可以删除的任务（只有待处理、已分配或运行中的任务可以删除）")
        
        st.divider()
        
        # 选择任务查看实时状态
        if not history_df.empty:
            selected_task = st.selectbox(
                "查看任务实时状态",
                history_df["task_id"].tolist(),
                key="task_status_select"
            )
            
            if selected_task:
                with st.spinner("获取任务状态中..."):
                    success, task_info = get_task_status(selected_task)
                    
                    if success:
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            status = task_info.get("status", "unknown")
                            status_color = {
                                "pending": "🟡",
                                "running": "🔵", 
                                "completed": "🟢",
                                "failed": "🔴",
                                "assigned": "🟠",
                                "deleted": "🔘"
                            }.get(status, "⚪")
                            st.metric("状态", f"{status_color} {status}")
                        
                        with col2:
                            if task_info.get("created_at"):
                                created = datetime.fromtimestamp(task_info["created_at"])
                                st.metric("创建时间", created.strftime("%H:%M:%S"))
                        
                        with col3:
                            if task_info.get("assigned_node"):
                                st.metric("分配节点", task_info["assigned_node"])
                        
                        with col4:
                            if task_info.get("completed_at"):
                                completed = datetime.fromtimestamp(task_info["completed_at"])
                                duration = task_info["completed_at"] - task_info["created_at"]
                                st.metric("执行时间", f"{duration:.1f}秒")
                        
                        # 显示结果
                        if task_info.get("result"):
                            st.subheader("执行结果")
                            st.code(task_info["result"], language="text")
                        
                        # 资源需求信息
                        if task_info.get("required_resources"):
                            st.info(f"资源需求: CPU={task_info['required_resources'].get('cpu', 1.0)}核心, "
                                  f"内存={task_info['required_resources'].get('memory', 512)}MB")
                    else:
                        st.warning(f"无法获取任务详情: {task_info.get('error', '未知错误')}")
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
            st.metric("在线节点", idle_nodes)
        with col3:
            st.metric("离线节点", total_nodes - idle_nodes)
        
        # 节点列表
        st.subheader("节点列表")
        
        for i, node in enumerate(nodes):
            node_id = node.get("node_id", f"node_{i}")
            node_status = node.get("status", "unknown")
            
            # 状态颜色
            status_color = {
                "online": "🟢",
                "offline": "🔴",
                "busy": "🟡"
            }.get(node_status, "⚪")
            
            with st.expander(f"{status_color} {node_id} - {node_status}", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**基本信息**")
                    st.write(f"状态: `{node_status}`")
                    st.write(f"平台: `{node.get('platform', 'N/A')}`")
                    
                    if node.get("idle_since"):
                        idle_since = datetime.fromisoformat(node["idle_since"].replace('Z', '+00:00'))
                        st.write(f"闲置开始: `{idle_since.strftime('%H:%M:%S')}`")
                    else:
                        st.write(f"最后活跃: `刚刚`")
                
                with col2:
                    st.write("**资源配置**")
                    resources = node.get("resources", {})
                    st.write(f"CPU核心: `{resources.get('cpu_cores', 'N/A')}`")
                    st.write(f"内存: `{resources.get('memory_mb', 'N/A')} MB`")
                
                # 节点贡献（新版API暂无此信息）
                if node.get("completed_tasks"):
                    st.write(f"已完成任务: `{node.get('completed_tasks', 0)}`")
                    st.write(f"总计算时间: `{node.get('total_compute_time', 0)}` 秒")
    else:
        if not success:
            st.error(f"获取节点信息失败: {nodes_info.get('error', '未知错误')}")
        else:
            st.info("暂无节点在线，请启动节点客户端")

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
            completed = tasks.get("completed", 0)
            total = tasks.get("total", 1)
            success_rate = (completed / total * 100) if total > 0 else 0
            st.metric("成功率", f"{success_rate:.1f}%")
        
        with col3:
            avg_time = tasks.get("avg_time", 0)
            st.metric("平均用时", f"{avg_time:.1f}秒")
        
        with col4:
            throughput = stats.get("throughput", {})
            compute_hours = throughput.get("compute_hours", 0)
            st.metric("计算时数", f"{compute_hours:.1f}")
        
        # 调度器统计
        scheduler_stats = stats.get("scheduler", {})
        if scheduler_stats:
            st.subheader("调度器统计")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("已处理任务", scheduler_stats.get("tasks_processed", 0))
            
            with col2:
                st.metric("失败任务", scheduler_stats.get("tasks_failed", 0))
            
            with col3:
                st.metric("注册节点", scheduler_stats.get("nodes_registered", 0))
            
            with col4:
                st.metric("失效节点", scheduler_stats.get("nodes_dropped", 0))
        
        # 可视化图表
        st.subheader("性能图表")
        
        # 创建图表
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("任务状态分布", "节点状态分布", "调度器统计", "资源利用率"),
            specs=[[{"type": "pie"}, {"type": "pie"}],
                   [{"type": "bar"}, {"type": "scatter"}]]
        )
        
        # 任务状态饼图
        if tasks:
            completed_tasks = tasks.get("completed", 0)
            failed_tasks = tasks.get("failed", 0)
            total_tasks = tasks.get("total", 0)
            pending_tasks = max(0, total_tasks - completed_tasks - failed_tasks)
            
            if total_tasks > 0:
                task_labels = ["完成", "失败", "进行中"]
                task_values = [completed_tasks, failed_tasks, pending_tasks]
                fig.add_trace(
                    go.Pie(labels=task_labels, values=task_values, hole=.3),
                    row=1, col=1
                )
        
        # 节点状态饼图
        nodes_info = stats.get("nodes", {})
        if nodes_info:
            idle_nodes = nodes_info.get("idle", 0)
            busy_nodes = nodes_info.get("busy", 0)
            offline_nodes = nodes_info.get("offline", 0)
            total_nodes = idle_nodes + busy_nodes + offline_nodes
            
            if total_nodes > 0:
                node_labels = ["闲置", "忙碌", "离线"]
                node_values = [idle_nodes, busy_nodes, offline_nodes]
                fig.add_trace(
                    go.Pie(labels=node_labels, values=node_values, hole=.3),
                    row=1, col=2
                )
        
        # 调度器统计柱状图
        if scheduler_stats:
            scheduler_labels = ["处理任务", "失败任务", "注册节点", "失效节点"]
            scheduler_values = [
                scheduler_stats.get("tasks_processed", 0),
                scheduler_stats.get("tasks_failed", 0),
                scheduler_stats.get("nodes_registered", 0),
                scheduler_stats.get("nodes_dropped", 0)
            ]
            fig.add_trace(
                go.Bar(x=scheduler_labels, y=scheduler_values),
                row=2, col=1
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
        st.error(f"获取统计信息失败: {stats.get('error', '未知错误')}")

# 页脚
st.divider()
st.caption("闲置计算加速器 v2.0.0 | 开源免费项目 | 适配新版调度中心API")

# 自动刷新逻辑
if st.session_state.auto_refresh:
    time_since_refresh = (datetime.now() - st.session_state.last_refresh).seconds
    if time_since_refresh >= REFRESH_INTERVAL:
        # 在后台触发刷新
        st.session_state.last_refresh = datetime.now()
        st.rerun()