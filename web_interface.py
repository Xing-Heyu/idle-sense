"""
web_interface.py
闲置计算加速器 - 网页控制界面
最终修复完整版
修复内容：
1. 修复所有语法错误（缩进、函数调用等）
2. 保持所有原版功能不变
3. 优化代码结构但不改变业务逻辑
"""

import streamlit as st
import requests
import time
import json
import os
import hashlib
import ctypes
import sys
import functools
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==================== 模块导入 ====================

try:
    from distributed_task import DistributedTaskManager, DISTRIBUTED_TASK_TEMPLATES
    DISTRIBUTED_TASK_AVAILABLE = True
except ImportError:
    DISTRIBUTED_TASK_AVAILABLE = False
    print("Warning: distributed_task module not available")

try:
    from file_drop_and_recovery import create_file_drop_task_interface, FileDropManager
    FILE_DROP_AVAILABLE = True
except ImportError:
    FILE_DROP_AVAILABLE = False
    print("Warning: file_drop_and_recovery module not available")

# ==================== 页面配置 ====================

st.set_page_config(
    page_title="闲置计算加速器",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 配置
SCHEDULER_URL = "http://localhost:8000"
REFRESH_INTERVAL = 30
# ==================== 持久化登录恢复（必须放最前面）====================
if 'user_session' not in st.session_state:
    st.markdown("""
    <script>
    // 页面加载时从 localStorage 读取登录态
    const savedSession = localStorage.getItem('idle_accelerator_session');
    if (savedSession) {
        try {
            const sessionData = JSON.parse(savedSession);
            // 通过 URL 参数传递给 Streamlit
            const url = new URL(window.location.href);
            url.searchParams.set('restore_session', JSON.stringify(sessionData));
            window.history.replaceState({}, '', url);
        } catch(e) {}
    }
    </script>
    """, unsafe_allow_html=True)
    
    # 从 URL 参数恢复 session_state
    import json
    restore_data = st.query_params.get_all('restore_session')
    if restore_data:
        try:
            session_data = json.loads(restore_data[0])
            st.session_state.user_session = session_data
            # 清除 URL 参数，避免刷新重复恢复
            st.query_params.clear()
        except:
            pass
# ===================================================================
# ==================== 优化工具函数 ====================

def safe_api_call(func, *args, default=None, **kwargs):
    """统一的API调用包装器"""
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

def cache_result(ttl=30):
    """带过期时间的缓存装饰器"""
    def decorator(func):
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            current_time = time.time()
            
            if key in cache:
                result, timestamp = cache[key]
                if current_time - timestamp < ttl:
                    return result
            
            result = func(*args, **kwargs)
            cache[key] = (result, current_time)
            return result
        return wrapper
    return decorator

# ==================== 用户管理类 ====================

class UserManager:
    """用户管理类 - 统一管理用户数据操作"""
    
    def __init__(self):
        self.users_dir = self._get_users_dir()
    
    def _get_users_dir(self):
        """获取本地用户目录路径"""
        users_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_users")
        os.makedirs(users_dir, exist_ok=True)
        return users_dir
    
    def validate_username(self, username):
        """验证用户名格式"""
        import re
        
        if len(username) > 20:
            return False, "用户名长度不能超过20个字符"
        
        pattern = r'^[\u4e00-\u9fa5a-zA-Z0-9]+$'
        if not re.match(pattern, username):
            return False, "用户名只能包含中文、英文和数字"
        
        return True, "用户名格式正确"
    
    def check_username_availability(self, username):
        """检查用户名是否可用"""
        users = self.list_users()
        existing_usernames = [user['username'] for user in users]
        
        if username not in existing_usernames:
            return username
        
        counter = 1
        while True:
            new_username = f"{username}_{counter}"
            if new_username not in existing_usernames:
                return new_username
            counter += 1
            if counter > 999:
                import random
                return f"{username}_{random.randint(1000, 9999)}"
    
    def save_user(self, user_id, username, folder_location="project"):
        """保存本地用户信息"""
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
        """获取本地用户信息"""
        user_file = os.path.join(self.users_dir, f"{user_id}.json")
        
        if os.path.exists(user_file):
            with open(user_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def update_user_login(self, user_id):
        """更新用户最后登录时间"""
        user_info = self.get_user(user_id)
        if user_info:
            user_info["last_login"] = datetime.now().isoformat()
            
            user_file = os.path.join(self.users_dir, f"{user_id}.json")
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(user_info, f, ensure_ascii=False, indent=2)
            
            return True
        return False
    
    def list_users(self):
        """列出所有本地用户"""
        users = []
        
        if os.path.exists(self.users_dir):
            for file_name in os.listdir(self.users_dir):
                if file_name.endswith('.json'):
                    user_id = file_name[:-5]
                    user_info = self.get_user(user_id)
                    if user_info:
                        users.append(user_info)
        
        return users

# ==================== 权限和文件夹管理 ====================

class PermissionManager:
    """权限管理类"""
    
    @staticmethod
    def is_admin():
        """检查管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    @staticmethod
    def check_write_permission(path):
        """检查写入权限"""
        try:
            test_file = os.path.join(path, ".permission_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return True
        except (PermissionError, OSError):
            return False
    
    @staticmethod
    def ensure_directory_with_permission(path):
        """确保目录存在且有写入权限"""
        try:
            os.makedirs(path, exist_ok=True)
        except PermissionError:
            return False, "权限不足，无法创建文件夹"
        
        if not PermissionManager.check_write_permission(path):
            return False, "权限不足，无法写入文件"
        
        return True, "权限检查通过"

class FolderManager:
    """文件夹管理类"""
    
    @staticmethod
    def get_base_path(folder_location):
        """根据用户选择获取基础路径"""
        if folder_location == "project":
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")
        elif folder_location == "c":
            return "C:\\idle-sense-system-data"
        elif folder_location == "d":
            return "D:\\idle-sense-system-data"
        else:
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")
    
    @staticmethod
    def create_folder_structure(base_path, user_id):
        """创建三层平级文件夹结构"""
        folders = {
            "user_system_dir": os.path.join(base_path, "user_system (系统专用-请勿修改)", user_id),
            "user_data_dir": os.path.join(base_path, "user_data (您的数据文件-主要工作区)"),
            "temp_data_dir": os.path.join(base_path, "temp_data (临时文件-自动清理)"),
            "docs_dir": os.path.join(base_path, "user_system (系统专用-请勿修改)", user_id, "docs (说明文档)")
        }
        
        return folders
    
    @staticmethod
    def create_system_files(folders, user_id, username):
        """创建系统文件"""
        system_info = {
            "user_id": user_id,
            "username": username,
            "purpose": "此文件包含闲置计算加速器系统运行所需的信息，请勿删除"
        }
        
        system_file_path = os.path.join(folders["user_system_dir"], "system_info.json")
        with open(system_file_path, "w", encoding="utf-8") as f:
            json.dump(system_info, f, ensure_ascii=False, indent=2)
        
        return system_file_path
    
    @staticmethod
    def create_user_docs(folders):
        """创建用户文档"""
        docs_created = []
        
        # 用户协议
        user_agreement_path = os.path.join(folders["docs_dir"], "用户协议.md")
        with open(user_agreement_path, "w", encoding="utf-8") as f:
            f.write("""# 闲置计算加速器用户协议

## 重要声明

欢迎使用闲置计算加速器系统！在使用本系统前，请仔细阅读以下条款：

## 1. 服务内容

本系统是一个开源的闲置计算资源利用平台，允许用户：
- 提交计算任务到闲置设备
- 共享闲置计算资源
- 查看任务执行结果

## 2. 用户责任

- 用户需对提交的任务内容负责
- 不得提交违法、有害或恶意代码
- 遵守当地法律法规

## 3. 隐私保护

- 本系统为开源项目，数据存储在用户本地
- 系统仅访问用户明确授权的文件夹
- 不会收集用户个人信息

## 4. 免责声明

- 本系统按"原样"提供，不提供任何明示或暗示的保证
- 用户使用系统所产生的任何后果由用户自行承担
- 开发者不对因使用系统造成的任何损失承担责任

## 5. 协议修改

本协议可能随时更新，更新后的协议将在系统中公布。

## 6. 同意条款

使用本系统即表示您同意遵守以上条款。

---
最后更新时间：2024年
""")
        docs_created.append(user_agreement_path)
        
        # 安全说明
        security_guide_path = os.path.join(folders["docs_dir"], "安全说明和使用指南.md")
        with open(security_guide_path, "w", encoding="utf-8") as f:
            f.write(f"""# 安全说明和使用指南

## 文件夹结构说明

您的数据存储在以下位置：
- 系统文件夹: `{folders['user_system_dir'].split('user_system')[0]}`
- 用户系统文件夹: `{folders['user_system_dir']}`
- 用户数据文件夹: `{folders['user_data_dir']}`
- 临时数据文件夹: `{folders['temp_data_dir']}`

## 权限说明

### 系统权限范围
- 系统只能读写您授权创建的文件夹内容
- 系统无法访问您电脑上的其他文件
- 所有操作都在您的明确授权下进行

### 文件夹用途
- **用户系统文件夹**: 存放用户ID等系统数据，平时不常用
- **用户数据文件夹**: 存放您不会删除的个人文件，系统可读取
- **临时数据文件夹**: 存放任务执行时的临时文件，会定期清理
- **文档文件夹**: 存放系统说明文档

## 如何让系统读取您的文件

如果您需要系统处理您的文件：
1. 将文件放入用户数据文件夹
2. 在任务代码中指定文件路径
3. 系统将能够访问和处理这些文件

## 安全注意事项

1. **文件安全**: 
   - 请勿在用户数据文件夹中存放敏感信息
   - 定期备份重要文件

2. **任务安全**:
   - 只运行您信任的代码
   - 避免处理来源不明的文件

3. **系统安全**:
   - 定期检查系统更新
   - 如发现异常行为，请立即停止使用并联系开发者

## 文件管理

### 系统管理的文件
- `system_info.json`: 系统运行必需信息，请勿删除
- 临时数据文件夹中的文件: 系统会定期清理

### 用户管理的文件
- 用户数据文件夹中的文件: 由您完全控制
- 文档文件夹中的文件: 可随时查看

## 常见问题

**Q: 系统能访问我电脑上的其他文件吗？**
A: 不能。系统只能访问您明确授权创建的文件夹。

**Q: 临时文件会被保留多久？**
A: 临时文件会在任务完成后24小时内自动清理。

**Q: 如何彻底退出系统？**
A: 关闭网页界面即可，所有本地数据保留。

---
如有更多问题，请查看项目文档或联系开发者。
""")
        docs_created.append(security_guide_path)
        
        return docs_created

# ==================== 文件夹创建辅助函数 ====================

def create_folders_with_script(user_id, username, folder_location):
    """通过脚本创建文件夹 - 保持原版逻辑"""
    import subprocess
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "create_folders.py")
        cmd = [
            sys.executable,
            script_path,
            "--user-id", user_id,
            "--username", username,
            "--folder-location", folder_location,
            "--output", temp_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            script_result = json.load(f)
        
        script_result["script_exit_code"] = result.returncode
        script_result["script_stdout"] = result.stdout
        script_result["script_stderr"] = result.stderr
        
        return script_result
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "脚本执行超时",
            "suggestion": "请检查系统响应或重试"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"脚本执行失败: {str(e)}",
            "suggestion": "请检查脚本文件是否存在或权限是否足够"
        }
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass

def create_folders_with_retry(user_id, username, folder_location, max_retries=2):
    """带重试机制的文件夹创建"""
    import time
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            time.sleep(1)
        
        result = create_folders_with_script(user_id, username, folder_location)
        
        if result["success"]:
            return result
        
        if attempt < max_retries:
            print(f"文件夹创建失败，尝试第 {attempt + 1} 次重试...")
            continue
    
    return {
        "success": False,
        "error": f"文件夹创建失败，已重试 {max_retries} 次",
        "suggestion": "请检查系统权限或选择其他位置",
        "last_error": result.get("error", "未知错误")
    }

# ==================== 初始化管理器和分布式任务 ====================

user_manager = UserManager()
permission_manager = PermissionManager()
folder_manager = FolderManager()

if DISTRIBUTED_TASK_AVAILABLE:
    try:
        distributed_task_manager = DistributedTaskManager(SCHEDULER_URL)
    except:
        distributed_task_manager = None
        DISTRIBUTED_TASK_AVAILABLE = False
else:
    distributed_task_manager = None

# ==================== 初始化session state ====================

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

# ==================== 修复的核心API函数 ====================


def check_scheduler_health():
    """检查调度中心是否在线 - 修复节点显示为0的问题"""
    # 优先使用健康端点
    success, health_data = safe_api_call(requests.get, f"{SCHEDULER_URL}/health", timeout=3)
    
    if not success:
        success, root_data = safe_api_call(requests.get, SCHEDULER_URL, timeout=3)
        if success:
            return True, {"status": "online", "nodes": {"online": 0, "total": 0}}
        return False, health_data
    
    # 获取节点详情
    success, nodes_data = safe_api_call(requests.get, f"{SCHEDULER_URL}/api/nodes",  
                                       params={"online_only": False}, timeout=4)
    
    if success:
        all_nodes = nodes_data.get("nodes", [])
        online_nodes = 0
        
        for node in all_nodes:
            # 健壮的在线状态判断
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
        
        # ✅ 只更新 health_data 里的 nodes.online，不整体覆盖
        if "nodes" not in health_data:
            health_data["nodes"] = {}
        health_data["nodes"]["online"] = online_nodes
        health_data["nodes"]["total"] = len(all_nodes)
    else:
        # 失败时也不覆盖，只设默认值
        if "nodes" not in health_data:
            health_data["nodes"] = {}
        health_data["nodes"]["online"] = 0
        health_data["nodes"]["total"] = 0
    
    # 返回结果
    return True, health_data

# 删除缓存装饰器 - 实时获取节点信息
def get_all_nodes():
    """获取所有节点信息 - 修复在线状态判断"""
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
        
        # 使用状态字段判断是否在线可用
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
            "capacity": node.get("capacity", {}),
            "tags": node.get("tags", {}),
            "owner": node.get("tags", {}).get("user_id", "未知")
        })
    
    return True, {
        "nodes": processed_nodes,
        "total_nodes": len(processed_nodes),
        "online_nodes": online_count,
        "idle_nodes": idle_count,
        "busy_nodes": online_count - idle_count
    }

# ==================== 保持原版的API函数 ====================

def submit_task(code, timeout=300, cpu=1.0, memory=512):
    user_id = None
    if st.session_state.user_session:
        user_id = st.session_state.user_session.get("user_id")
    """提交任务到调度中心"""
    payload = {
        "code": code,
        "timeout": timeout,
        "resources": {"cpu": cpu, "memory": memory},
        "user_id": user_id
    }
    return safe_api_call(requests.post, f"{SCHEDULER_URL}/submit", json=payload, timeout=10)

def get_task_status(task_id):
    """获取任务状态"""
    return safe_api_call(requests.get, f"{SCHEDULER_URL}/status/{task_id}", timeout=5)

def delete_task(task_id):
    """删除任务"""
    return safe_api_call(requests.delete, f"{SCHEDULER_URL}/api/tasks/{task_id}", timeout=5)

def submit_distributed_task(name, description, code_template, data, chunk_size=10, 
                           max_parallel_chunks=5, merge_code=None):
    """提交分布式任务"""
    if not DISTRIBUTED_TASK_AVAILABLE:
        return False, {"error": "分布式任务处理模块不可用"}
    
    try:
        task_id = distributed_task_manager.submit_distributed_task(
            name=name,
            description=description,
            code_template=code_template,
            data=data,
            chunk_size=chunk_size,
            max_parallel_chunks=max_parallel_chunks,
            merge_code=merge_code
        )
        
        if distributed_task_manager.create_task_chunks(task_id):
            import threading
            def execute_task():
                distributed_task_manager.execute_distributed_task(task_id)
            
            thread = threading.Thread(target=execute_task, daemon=True)
            thread.start()
            
            return True, {"task_id": task_id, "message": "分布式任务已提交"}
        else:
            return False, {"error": "创建任务分片失败"}
            
    except Exception as e:
        return False, {"error": str(e)}

def get_distributed_task_status(task_id):
    """获取分布式任务状态"""
    if not DISTRIBUTED_TASK_AVAILABLE:
        return False, {"error": "分布式任务处理模块不可用"}
    
    try:
        status = distributed_task_manager.get_task_status(task_id)
        if status:
            return True, status
        else:
            return False, {"error": "任务不存在"}
    except Exception as e:
        return False, {"error": str(e)}

def get_distributed_task_result(task_id):
    """获取分布式任务结果"""
    if not DISTRIBUTED_TASK_AVAILABLE:
        return False, {"error": "分布式任务处理模块不可用"}
    
    try:
        result = distributed_task_manager.get_task_result(task_id)
        if result is not None:
            return True, {"result": result}
        else:
            return False, {"error": "任务未完成或结果不可用"}
    except Exception as e:
        return False, {"error": str(e)}

def get_system_stats():
    """获取系统统计"""
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
    """获取所有任务结果"""
    return safe_api_call(requests.get, f"{SCHEDULER_URL}/results", timeout=5)

def stop_node(node_id: str):
    """停止指定节点"""
    return safe_api_call(requests.post, f"{SCHEDULER_URL}/api/nodes/{node_id}/stop", timeout=5)




# ==================== 页面标题和样式 ====================

st.title("⚡ 闲置计算加速器")
st.markdown("利用个人电脑闲置算力的分布式计算平台")
# ==================== 侧边栏 ====================

with st.sidebar:
    st.header("控制面板")
    
    # 调试模式
    if st.button("🐛 调试模式"):
        st.session_state.debug_mode = not st.session_state.debug_mode
        st.rerun()
    
    if st.session_state.debug_mode:
        st.warning("🔧 调试模式已启用")
        st.subheader("API测试")
        if st.button("测试健康端点"):
            success, data = safe_api_call(requests.get, f"{SCHEDULER_URL}/health", timeout=3)
            if success:
                st.json(data)
            else:
                st.error(data.get("error"))
        st.divider()
    
    # 系统状态
    st.subheader("📊 系统状态")
    health_ok, health_info = check_scheduler_health()
    
    if health_ok:
        st.success("🟢 调度器在线")
        
        # 创建局部刷新容器
        node_metric = st.empty()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 初始显示
            online = health_info.get("nodes", {}).get("online", 0)
            node_metric.metric("可用节点", online)
        
        with col2:
            if st.button("🔄", help="刷新状态"):
                # 只刷新节点数
                fresh_ok, fresh_info = check_scheduler_health()
                if fresh_ok:
                    fresh_online = fresh_info.get("nodes", {}).get("online", 0)
                    node_metric.metric("可用节点", fresh_online)
                    st.success("✅ 已刷新")
                else:
                    st.error("❌ 调度器离线")
    else:
        st.error("🔴 调度器离线")
        st.code("请运行: python scheduler/simple_server.py")
    
    st.divider()
    
    # 用户状态
    st.subheader("👤 用户状态")
if st.session_state.user_session:
    st.success(f"✅ {st.session_state.user_session.get('username', '用户')}")
    if st.button("🚪 退出登录"):
    # 先清除 localStorage，再清除 session_state，最后刷新
        st.markdown("<script>localStorage.removeItem('idle_accelerator_session');</script>", unsafe_allow_html=True)
        st.session_state.user_session = None
        st.query_params.clear()
        st.rerun()
else:
    st.warning("🔒 未登录")
    username = st.text_input("用户名", key="sidebar_username")
    
    if st.button("快速登录"):
        if username:
            import hashlib
            user_id = f"local_{hashlib.md5(username.encode()).hexdigest()[:8]}"
            
            # 写入本地用户文件（让本地登录也能识别）
            user_manager.save_user(user_id, username, "project")
            
            # 设置 session_state
            st.session_state.user_session = {
                "username": username,
                "user_id": user_id
            }
            
            st.success(f"✅ 欢迎 {username}")
            time.sleep(1)
            st.rerun() 
    # 节点激活功能
    st.divider()
    st.markdown("### 🚀 节点管理")
    
    col_start, col_stop = st.columns(2)
    
    with col_start:
        if st.button("▶️ 启动节点", help="启动本地计算节点", type="primary", key="sidebar_start_node_btn"):
            st.success("正在启动节点客户端...")
            
            cpu_share = st.session_state.get('share_cpu_value', 4.0)
            memory_share = st.session_state.get('share_memory_value', 8192)
            
            try:
                current_user_id = None
                if st.session_state.user_session:
                    current_user_id = st.session_state.user_session.get("user_id")

                response = requests.post(
                    f"{SCHEDULER_URL}/api/nodes/activate-local",
                    json={
                        "cpu_limit": cpu_share,
                        "memory_limit": memory_share,
                        "storage_limit": 102400,
                        "user_id": current_user_id  # ← 加上这一行
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    node_data = response.json()
                    node_id = node_data.get("node_id")
                    st.success(f"✅ 节点 {node_id} 已在调度器注册")
                    
                    import tempfile
                    temp_dir = tempfile.gettempdir()
                    node_id_file = os.path.join(temp_dir, "idle_sense_node_id.txt")
                    with open(node_id_file, 'w') as f:
                        f.write(node_id)
                    st.info(f"节点ID已保存: {node_id}")
                else:
                    st.error(f"节点注册失败: {response.status_code} - {response.text}")
            except Exception as e:
                st.error(f"节点注册失败: {e}")
            
            st.code("""
方法1: 使用批处理文件
双击运行 start_all.bat

方法2: 手动启动
1. 打开命令提示符
2. 切换到项目目录
3. 运行: python node/simple_client.py
            """, language="bash")
            
            st.info("✅ 节点已激活！系统将自动管理节点运行。")
    
    with col_stop:
        if st.button("⏹️ 停止节点", help="停止所有本地节点", type="secondary", key="sidebar_stop_node_btn"):
            try:
                # 获取所有节点列表
                success, nodes_info = get_all_nodes()
                if success and nodes_info.get("nodes"):
                    stopped_count = 0
                    for node in nodes_info["nodes"]:
                        node_id = node.get("node_id")
                        if node_id and node.get("is_online"):
                            stop_success, stop_result = stop_node(node_id)
                            if stop_success:
                                stopped_count += 1
                    
                    if stopped_count > 0:
                        st.success(f"✅ 已停止 {stopped_count} 个节点")
                    else:
                        st.info("ℹ️ 没有正在运行的节点")
                else:
                    st.info("ℹ️ 没有找到任何节点")
            except Exception as e:
                st.error(f"停止节点失败: {e}")
    
    # 资源分配滑块
    st.divider()
    st.markdown("### 💻 资源分配")
    st.info("通过滑块调整您愿意共享的计算资源")
    
    cpu_value = st.session_state.get('share_cpu_value', 4.0)
    memory_value = st.session_state.get('share_memory_value', 8192)
    
    cpu_share = st.slider("共享CPU核心数", 0.5, 16.0, cpu_value, 0.5, 
                       help="拖动调整您愿意共享的CPU核心数")
    st.session_state.share_cpu_value = cpu_share
    
    memory_share = st.slider("共享内存大小(MB)", 512, 32768, memory_value, 512, 
                         help="拖动调整您愿意共享的内存大小")
    st.session_state.share_memory_value = memory_share
    
    st.success(f"您将共享: {cpu_share} 核心 CPU, {memory_share}MB 内存")

# ==================== 主界面 ====================

# 定义默认的task_type变量
task_type_default = "单节点任务"

# 只有当用户已登录时才显示主界面
if st.session_state.user_session:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 提交任务", "📊 任务监控", "🖥️ 节点管理", "📈 系统统计", "📋 任务结果"])

    with tab1:
        st.header("提交计算任务")
        
        # 定义task_type变量
        task_type = task_type_default
        
        # 现在使用这个变量
        task_type = st.radio("选择任务类型", ["单节点任务", "分布式任务"], horizontal=True, 
                            disabled=not DISTRIBUTED_TASK_AVAILABLE)
        
        if task_type == "分布式任务" and not DISTRIBUTED_TASK_AVAILABLE:
            st.error("❌ 分布式任务处理模块不可用，请确保已安装distributed_task.py")
        
        # 分布式任务配置
        if task_type == "分布式任务" and DISTRIBUTED_TASK_AVAILABLE:
            st.info("🚀 **分布式任务** 可以利用多个节点的计算资源并行处理大型任务，大幅提升处理效率")
            
            st.subheader("分布式任务配置")
            
            template_name = st.selectbox(
                "选择任务类型",
                options=list(DISTRIBUTED_TASK_TEMPLATES.keys()),
                format_func=lambda x: DISTRIBUTED_TASK_TEMPLATES[x]["name"],
                help="选择预定义的任务类型，或自定义任务"
            )
            
            if template_name in DISTRIBUTED_TASK_TEMPLATES:
                st.info(DISTRIBUTED_TASK_TEMPLATES[template_name]["description"])
            
            col1, col2 = st.columns(2)
            
            with col1:
                task_name = st.text_input("任务名称", value=f"分布式任务_{int(time.time())}")
                chunk_size = st.number_input(
                    "分片大小（每组数据数量）", 
                    min_value=1, 
                    max_value=1000, 
                    value=10, 
                    step=1
                )
        
            with col2:
                task_description = st.text_input("任务描述", value="使用多节点协作处理大型任务")
                max_parallel_chunks = st.number_input(
                    "最大并行节点数", 
                    min_value=1, 
                    max_value=50, 
                    value=5, 
                    step=1
                )
            
            # 数据输入
            st.subheader("任务数据")
            data_input_method = st.radio("数据输入方式", ["手动输入", "从文件上传"], horizontal=True)
            
            task_data = None
            if data_input_method == "手动输入":
                data_type = st.selectbox("数据类型", ["数字列表", "文本列表", "键值对"])
                
                if data_type == "数字列表":
                    data_input = st.text_area("输入数字列表，用逗号分隔", value="1,2,3,4,5,6,7,8,9,10")
                    try:
                        task_data = [int(x.strip()) for x in data_input.split(",")]
                    except:
                        st.error("输入格式错误，请输入数字并用逗号分隔")
            
                elif data_type == "文本列表":
                    data_input = st.text_area("输入文本列表，每行一项", value="苹果\n香蕉\n橙子\n葡萄\n西瓜")
                    task_data = [line.strip() for line in data_input.split("\n") if line.strip()]
                
                elif data_type == "键值对":
                    data_input = st.text_area("输入键值对，每行一个，用冒号分隔", 
                                             value="名称:闲置计算加速器\n版本:2.0\n类型:分布式计算")
                    task_data = {}
                    for line in data_input.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            task_data[key.strip()] = value.strip()
            
            else:
                uploaded_file = st.file_uploader("上传JSON文件", type=["json"])
                if uploaded_file:
                    try:
                        content = uploaded_file.read().decode("utf-8")
                        task_data = json.loads(content)
                        st.success(f"文件上传成功，包含 {len(task_data) if isinstance(task_data, (list, dict)) else 1} 项数据")
                    except Exception as e:
                        st.error(f"文件解析失败: {e}")
            
            # 通用任务选项
            st.markdown("---")
            st.subheader("🎯 通用任务处理")
            st.info("💡 **通用任务** 可以处理任何类型的计算任务，不限于预设模板")
            
            use_custom_task = st.checkbox("使用通用任务（自定义处理逻辑）", help="不使用预设模板，完全自定义任务处理方式")
            
            if use_custom_task:
                st.subheader("自定义任务配置")
                
                custom_map_code = st.text_area(
                    "数据处理代码（每个节点执行的代码）",
                    value="""
# 在这里编写每个节点要执行的代码
# __DATA__ 变量包含分配给这个节点的数据片段
# __CHUNK_ID__ 变量是当前数据片段的ID
# __CHUNK_INDEX__ 变量是当前数据片段的索引

# 示例：处理数据
results = []
for item in __DATA__:
    # 在这里处理每个数据项
    processed_item = item * 2  # 示例：将每个数字乘以2
    results.append(processed_item)

# 设置结果（必须设置这个变量）
__result__ = {
    "chunk_id": __CHUNK_ID__,
    "chunk_index": __CHUNK_INDEX__,
    "processed_data": results,
    "count": len(results)
}
print(f"处理了 {len(results)} 项数据")
""",
                    height=200,
                    help="这段代码将在每个节点上运行，处理分配给该节点的数据片段"
                )
            
                custom_merge_code = st.text_area(
                    "结果合并代码（合并所有节点的结果）",
                    value="""
# 在这里编写合并所有节点结果的代码
# __CHUNK_RESULTS__ 变量包含所有节点返回的结果列表

# 示例：合并所有节点的处理结果
all_results = []
total_count = 0

for chunk_result in __CHUNK_RESULTS__:
    if isinstance(chunk_result, dict) and "processed_data" in chunk_result:
        all_results.extend(chunk_result["processed_data"])
        total_count += chunk_result["count"]

# 设置最终合并结果（必须设置这个变量）
__MERGED_RESULT__ = {
    "total_processed": total_count,
    "all_data": all_results
}
print(f"合并完成，总共处理了 {total_count} 项数据")
""",
                    height=200,
                    help="这段代码将合并所有节点返回的结果"
                )
            
            # 代码模板显示
            if not use_custom_task and template_name in DISTRIBUTED_TASK_TEMPLATES:
                with st.expander("查看任务代码模板", expanded=False):
                    st.code(DISTRIBUTED_TASK_TEMPLATES[template_name]["code_template"], language="python")
                    
                    if "merge_code" in DISTRIBUTED_TASK_TEMPLATES[template_name]:
                        st.subheader("合并代码模板")
                        st.code(DISTRIBUTED_TASK_TEMPLATES[template_name]["merge_code"], language="python")
            
            # 提交按钮
            if st.button("🚀 提交分布式任务", type="primary", use_container_width=True):
                if not task_name or not task_description:
                    st.error("请填写任务名称和描述")
                elif task_data is None:
                    st.error("请输入或上传任务数据")
                else:
                    with st.spinner("提交分布式任务中..."):
                        if use_custom_task:
                            code_template = custom_map_code
                            merge_code = custom_merge_code
                        else:
                            code_template = DISTRIBUTED_TASK_TEMPLATES[template_name]["code_template"]
                            merge_code = DISTRIBUTED_TASK_TEMPLATES[template_name].get("merge_code")
                        
                        success, result = submit_distributed_task(
                            name=task_name,
                            description=task_description,
                            code_template=code_template,
                            data=task_data,
                            chunk_size=chunk_size,
                            max_parallel_chunks=max_parallel_chunks,
                            merge_code=merge_code
                        )
                        
                        if success:
                            task_id = result.get("task_id")
                            st.success(f"✅ 分布式任务提交成功！任务ID: `{task_id}`")
                            
                            st.session_state.task_history.append({
                                "task_id": task_id,
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "status": "submitted",
                                "code_preview": f"{task_name} (分布式任务)",
                                "type": "分布式任务"
                            })
                            
                            with st.expander("任务详情", expanded=True):
                                col1, col2, col3 = st.columns(3)
                                with col1: st.metric("任务ID", task_id)
                                with col2: st.metric("分片大小", chunk_size)
                                with col3: st.metric("最大并行分片", max_parallel_chunks)
                                st.metric("数据项数量", len(task_data) if isinstance(task_data, (list, dict)) else 1)
                                task_type_desc = "自定义任务" if use_custom_task else template_name
                                st.info(f"任务类型: {task_type_desc}")
                        else:
                            st.error(f"❌ 提交失败: {result.get('error', '未知错误')}")
        
        # 单节点任务配置
        else:
            st.info("💡 **提示**: 单节点任务也可以在本地IDE中运行，分布式任务更能发挥系统优势")
            st.subheader("单节点任务配置")
            
            with st.expander("任务配置", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    timeout = st.number_input("超时时间(秒)", min_value=10, max_value=7200, value=300, step=10)
                    cpu_request = st.slider("CPU需求(核心)", 0.5, 32.0, 4.0, 0.5)
                
                with col2:
                    memory_request = st.slider("内存需求(MB)", 512, 65536, 4096, 512)
            
            # 代码编辑器
            with st.expander("Python代码", expanded=True):    
                code = st.text_area(
                    "输入Python代码",
                    value="",
                    height=300,
                    label_visibility="collapsed",
                    placeholder="# 在这里直接写你的代码，无需任何框架\nprint('Hello world')"
                )
            
            # 提交按钮
            if st.button("🚀 提交单节点任务", use_container_width=True):
                if not code.strip():
                    st.error("请输入Python代码")
                else:
                    with st.spinner("提交任务中..."):
                        cpu_request = min(max(cpu_request, 0.1), 16.0)
                        memory_request = min(max(memory_request, 64), 16384)
                        
                        success, result = submit_task(code, timeout, cpu_request, memory_request)
                        
                        if success:
                            task_id = result.get("task_id")
                            st.success(f"✅ 任务提交成功！任务ID: `{task_id}`")
                            
                            st.session_state.task_history.append({
                                "task_id": task_id,
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "status": "submitted",
                                "code_preview": code[:100] + ("..." if len(code) > 100 else ""),
                                "type": "单节点任务"
                            })
                            
                            with st.expander("任务详情", expanded=True):
                                col1, col2, col3 = st.columns(3)
                                with col1: st.metric("任务ID", task_id)
                                with col2: st.metric("超时时间", f"{timeout}秒")
                                with col3: st.metric("资源需求", f"CPU: {cpu_request}, 内存: {memory_request}MB")
                        else:
                            st.error(f"❌ 提交失败: {result.get('error', '未知错误')}")

    with tab2:
        st.header("任务监控")
        
        if st.button("🔄 刷新任务列表", key="refresh_tasks"): st.rerun()
        
        task_monitor_type = st.radio("监控任务类型", ["所有任务", "单节点任务", "分布式任务"], horizontal=True)
        
        success, results = get_all_results()
        if success and results.get("results"):
            results_list = results["results"]
            
            if results_list:
                st.subheader("已完成的任务")
                
                results_data = []
                for result in results_list:
                    task_type = "单节点任务"
                    task_id = result.get("task_id", "N/A")
                    
                    if st.session_state.task_history:
                        for task in st.session_state.task_history:
                            if task.get("task_id") == str(task_id) and task.get("type") == "分布式任务":
                                task_type = "分布式任务"
                                break
                    
                    if task_monitor_type == "所有任务" or \
                       (task_monitor_type == "单节点任务" and task_type == "单节点任务") or \
                       (task_monitor_type == "分布式任务" and task_type == "分布式任务"):
                        
                        results_data.append({
                            "任务ID": task_id,
                            "任务类型": task_type,
                            "完成时间": datetime.fromtimestamp(result.get("completed_at", time.time())).strftime("%H:%M:%S") if result.get("completed_at") else "N/A",
                            "执行节点": result.get("assigned_node", "未知"),
                            "结果预览": (result.get("result", "无结果")[:50] + "...") if result.get("result") and len(result.get("result", "")) > 50 else (result.get("result", "无结果") or "无结果")
                        })
                
                if results_data:
                    results_df = pd.DataFrame(results_data)
                    st.dataframe(results_df, use_container_width=True, hide_index=True)
                    
                    selected_task_id = st.selectbox("选择任务查看完整结果", [r["任务ID"] for r in results_data])
                    
                    if selected_task_id:
                        full_result = None
                        task_type = "单节点任务"
                        
                        for result in results_list:
                            if str(result.get("task_id")) == str(selected_task_id):
                                full_result = result
                                break
                        
                        if st.session_state.task_history:
                            for task in st.session_state.task_history:
                                if task.get("task_id") == str(selected_task_id):
                                    task_type = task.get("type", "单节点任务")
                                    break
                        
                        if full_result and full_result.get("result"):
                            st.subheader(f"任务 {selected_task_id} 的完整结果")
                            st.code(full_result["result"], language="text")
                            
                            if task_type == "分布式任务" and DISTRIBUTED_TASK_AVAILABLE:
                                st.subheader("分布式任务详情")
                                
                                status_success, status_info = get_distributed_task_status(selected_task_id)
                                if status_success:
                                    col1, col2, col3 = st.columns(3)
                                    with col1: st.metric("总分片数", status_info.get("total_chunks", 0))
                                    with col2: st.metric("已完成分片", status_info.get("completed_chunks", 0))
                                    with col3: st.metric("失败分片", status_info.get("failed_chunks", 0))
                                    
                                    progress = status_info.get("progress", 0)
                                    st.progress(progress)
                                    st.write(f"任务进度: {progress:.1%}")
                                else:
                                    st.warning(f"无法获取分布式任务状态: {status_info.get('error', '未知错误')}")
                else:
                    st.info(f"没有找到{task_monitor_type}的已完成任务")
            else:
                st.info("暂无已完成的任务")
        elif not success:
            st.warning(f"获取任务结果失败: {results.get('error', '未知错误')}")
        
        # 任务历史
        if st.session_state.task_history:
            st.subheader("任务历史记录")
            
            history_df = pd.DataFrame(st.session_state.task_history)
            
            if task_monitor_type != "所有任务":
                filtered_history = history_df[history_df["type"] == task_monitor_type]
            else:
                filtered_history = history_df
            
            if not filtered_history.empty:
                st.dataframe(filtered_history, use_container_width=True, hide_index=True)
                
                # 任务删除功能
                st.subheader("🗑️ 任务删除")
                
                deletable_tasks = []
                for task_id in history_df["task_id"].tolist():
                    success, task_info = get_task_status(task_id)
                    if success and task_info.get("status") in ["pending", "assigned", "running"]:
                        deletable_tasks.append({
                            "task_id": task_id,
                            "status": task_info.get("status", "unknown")
                        })
                
                if deletable_tasks:
                    task_options = {f"任务{task['task_id']} (状态: {task['status']})": task['task_id'] 
                                  for task in deletable_tasks}
                    selected_task_label = st.selectbox("选择要删除的任务", list(task_options.keys()))
                    selected_task_id = task_options[selected_task_label]
                    
                    if st.button("🗑️ 删除选中任务", type="secondary"):
                        with st.spinner("删除中..."):
                            delete_response = delete_task(selected_task_id)
                            
                            if delete_response[0]:
                                st.success("✅ 任务删除成功！")
                                st.session_state.task_history = [
                                    task for task in st.session_state.task_history 
                                    if task["task_id"] != selected_task_id
                                ]
                                st.rerun()
                            else:
                                st.error(f"❌ 删除失败: {delete_response[1].get('error', '未知错误')}")
                else:
                    st.info("暂无可以删除的任务")
                
                st.divider()
                
                # 任务状态查看
                if not history_df.empty:
                    selected_task = st.selectbox("查看任务实时状态", history_df["task_id"].tolist(), key="task_status_select")
                    
                    if selected_task:
                        with st.spinner("获取任务状态中..."):
                            success, task_info = get_task_status(selected_task)
                            
                            if success:
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    status = task_info.get("status", "unknown")
                                    status_color = {
                                        "pending": "🟡", "running": "🔵", "completed": "🟢",
                                        "failed": "🔴", "assigned": "🟠", "deleted": "🔘"
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
                                
                                if task_info.get("result"):
                                    with st.expander("执行结果", expanded=False):
                                        st.code(task_info["result"], language="text")
                                
                                if task_info.get("required_resources"):
                                    st.info(f"资源需求: CPU={task_info['required_resources'].get('cpu', 1.0)}核心, "
                                          f"内存={task_info['required_resources'].get('memory', 512)}MB")
                            else:
                                st.warning(f"无法获取任务详情: {task_info.get('error', '未知错误')}")
        else:
            st.info("暂无任务历史，请先提交任务")

    with tab3:
        st.header("计算节点管理")
        
        # 节点激活功能
        st.subheader("🚀 节点激活")
        st.markdown("**启动计算节点以参与分布式计算**")
        
        try:
            health_ok, health_info = check_scheduler_health()
            if health_ok:
                idle_nodes = health_info.get("nodes", {}).get("online", 0)
                if idle_nodes > 0:
                    st.success(f"✅ 当前有 {idle_nodes} 个节点在线")
                else:
                    st.warning("⚠️ 没有节点在线，请启动节点客户端")
            else:
                st.error("🔴 调度器离线，请先启动调度器")
        except Exception as e:
            st.error(f"检查节点状态失败: {e}")
        
        st.markdown("### 如何启动节点")
        col1, col2 = st.columns(2)
        
        try:
            import subprocess
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node", "simple_client.py")
            subprocess.Popen([sys.executable, script_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            st.success("✅ 节点客户端启动命令已发送")
            st.info("请检查是否弹出了新的命令行窗口")
        except Exception as e:
            st.error(f"自动启动失败: {e}")
            st.info("请手动启动节点客户端")
        
        with col2:
            st.info("""
### 节点启动说明
1. 确保调度器正在运行
2. 双击运行 start_all.bat
3. 等待节点注册成功
4. 刷新页面查看节点状态
            """)
        
        st.markdown("---")
        
        # 节点列表
        st.subheader("节点列表")
        
        try:
            success, nodes_info = get_all_nodes()
            
            if success and nodes_info.get("nodes"):
                nodes = nodes_info["nodes"]
                
                st.metric("总节点数", len(nodes))
                
                for i, node in enumerate(nodes):
                    with st.expander(f"节点 {i+1}: {node.get('node_id', 'unknown')}", expanded=True):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**状态**: {node.get('status', 'unknown')}")
                            st.write(f"**平台**: {node.get('platform', 'unknown')}")
                            st.write(f"**所有者**: {node.get('owner', '未知')}")
                        
                        with col2:
                            capacity = node.get('capacity', {})
                            st.write(f"**CPU**: {capacity.get('cpu', 'N/A')} 核心")
                            st.write(f"**内存**: {capacity.get('memory', 'N/A')} MB")
            else:
                if not success:
                    st.error(f"获取节点信息失败: {nodes_info.get('error', '未知错误')}")
                else:
                    st.info("暂无节点在线")
        except Exception as e:
            st.error(f"节点管理出错: {e}")

    with tab4:
        st.header("系统统计")
        
        success, stats = get_system_stats()
        
        if success:
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
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("已处理任务", scheduler_stats.get("tasks_processed", 0))
                
                with col2:
                    st.metric("失败任务", scheduler_stats.get("tasks_failed", 0))
            
            # 可视化图表
            st.subheader("性能图表")
            
            # 正确的图表创建方式
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=("任务状态分布", "调度器统计", "资源利用率", "系统性能"),
                specs=[[{"type": "pie"}, {"type": "bar"}],
                       [{"type": "scatter"}, {"type": "indicator"}]]
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
                        go.Pie(
                            labels=task_labels, 
                            values=task_values, 
                            hole=.3,
                            pull=[0.1, 0.1, 0.1],
                            rotation=45,
                            textinfo='label+percent',
                            textposition='outside',
                            marker=dict(line=dict(color='#FFFFFF', width=2))
                        ),
                        row=1, col=1
                    )
            
            # 调度器统计柱状图
            if scheduler_stats:
                scheduler_labels = ["处理任务", "失败任务"]
                scheduler_values = [
                    scheduler_stats.get("tasks_processed", 0),
                    scheduler_stats.get("tasks_failed", 0)
                ]
                fig.add_trace(
                    go.Bar(x=scheduler_labels, y=scheduler_values),
                    row=1, col=2
                )
            
            fig.update_layout(
                title_text="系统监控仪表盘",
                template="plotly_dark",
                height=600,
                showlegend=True,
            )
            
            # 正确的更新图表方式
            fig.update_traces(
                selector=dict(type='pie'),
                marker=dict(line=dict(color='#FFFFFF', width=2))
            )
            
            fig.update_traces(
                selector=dict(type='bar'),
                marker=dict(line=dict(color='#FFFFFF', width=1))
            )
            
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.subheader("📋 任务结果")
            success, results = get_all_results()
            if success and results.get("results"):
                results_list = results["results"]
                if st.session_state.user_session:
                    user_id = st.session_state.user_session.get("user_id")
                    user_tasks = []
                    for result in results_list:
                        task_user_id = result.get("user_id")
                        if task_user_id == user_id:
                            user_tasks.append(result)


                    if user_tasks:
                        recent_tasks = user_tasks[-5:]
                        for task in reversed(recent_tasks):
                            task_id = task.get("task_id", "N/A")
                            result_preview = task.get("result", "无结果")
                            assigned_node = task.get("assigned_node", "未知节点")
                            completed_at = task.get("completed_at")

                            if completed_at:
                                time_str = datetime.fromtimestamp(completed_at).strftime("%H:%M:%S")
                            else:
                                time_str = "未知时间"
                            with st.expander(f"任务 {task_id} - {time_str}", expanded=False):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**执行节点**: {assigned_node}")
                                with col2:
                                    st.write(f"**完成时间**: {time_str}")
                                st.text_area("结果", value=result_preview, height=150, key=f"result_{task_id}")                
                    else:
                        st.info("您还没有完成的任务")
                else:
                    st.info("用户信息获取失败")                    
            else:
                st.warning("无法获取任务结果")                        
            # 原始数据
            with st.expander("查看原始数据"):
                st.json(stats)
        else:
            st.error(f"获取统计信息失败: {stats.get('error', '未知错误')}")
    with tab5:
        st.header("📋 您的任务结果")
        st.markdown("查看您提交的所有任务执行结果")
        user_id = None
        if st.session_state.user_session:
            user_id = st.session_state.user_session.get("user_id") 
        if not user_id:
            st.warning("请先登录查看任务结果")
        else:
            success, results = get_all_results()
            if success and results.get("results"):
                results_list = results["results"]
                user_tasks = []
                for result in results_list:
                    task_user_id = result.get("user_id")
                    if task_user_id == user_id:
                        user_tasks.append(result)
                if user_tasks:
                    st.success(f"找到 {len(user_tasks)} 个您的任务")
                    col1, col2 = st.columns(2)
                    with col1:
                        search_term = st.text_input("🔍 搜索任务ID或内容", "")
                    with col2:
                        show_limit = st.slider("显示数量", 1, 20, 5)
                    filtered_tasks = user_tasks
                    if search_term:
                        filtered_tasks = []
                        for task in user_tasks:
                            task_id_str = str(task.get("task_id", ""))
                            result_text = task.get("result", "")
                            if search_term in task_id_str or search_term.lower() in result_text.lower():
                                filtered_tasks.append(task)        
                    for task in reversed(filtered_tasks[-show_limit:]):  # 最新的在前
                        task_id = task.get("task_id", "N/A")
                        result_preview = task.get("result", "无结果")
                        assigned_node = task.get("assigned_node", "未知节点")
                        completed_at = task.get("completed_at")
                        if completed_at:
                            time_str = datetime.fromtimestamp(completed_at).strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            time_str = "未知时间"
                        with st.container():
                            st.markdown(f"### 任务 {task_id}")
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.write(f"**执行节点**: {assigned_node}")
                            with col_b:
                                st.write(f"**完成时间**: {time_str}")
                            with col_c:
                                # 下载结果按钮
                                if st.button("📥 下载结果", key=f"download_{task_id}"):
                                    st.download_button(
                                        label="下载结果文件",
                                        data=result_preview,
                                        file_name=f"task_{task_id}_result.txt",
                                        mime="text/plain",
                                        key=f"real_download_{task_id}"
                                    )
                            # 结果预览
                            with st.expander("查看结果", expanded=False):
                                st.text_area("", value=result_preview, height=200, key=f"result_{task_id}")
                            
                            st.markdown("---")
                else:
                    st.info("您还没有完成的任务")
                    st.markdown("去提交您的第一个任务吧！")
            else:
                st.warning("无法获取任务结果")

else:
    # 用户未登录时显示注册/登录界面
    st.warning("🔒 请先登录或注册以使用系统功能")
    
    tab_login, tab_register = st.tabs(["登录", "注册"])
    
    with tab_login:
        st.markdown("### 本地用户登录")
        st.caption("输入您的用户名或用户ID进行登录")
        
        login_username = st.text_input("用户名或用户ID", key="login_username")
        
        if st.button("🔐 本地登录", key="local_login_button"):
            if not login_username:
                st.error("请输入用户名或用户ID")
            else:
                local_users = user_manager.list_users()
                found_user = None
                
                for user in local_users:
                    if user['username'] == login_username or user['user_id'] == login_username:
                        found_user = user
                        break
                
                if found_user:
                    user_manager.update_user_login(found_user['user_id'])
                    
                    st.session_state.user_session = {
                        "session_id": f"local_{found_user['user_id']}_{datetime.now().timestamp()}",
                        "user_id": found_user['user_id'],
                        "username": found_user['username'],
                        "is_local": True
                    }
                    st.markdown(f"""
                    <script>
                    localStorage.setItem('idle_accelerator_session', JSON.stringify({{
                        user_id: '{found_user['user_id']}',
                        username: '{found_user['username']}',
                        is_local: true
                    }}));
                    </script>
                    """, unsafe_allow_html=True)
                    st.markdown(f"""
                    <script>
                    window.dispatchEvent(new CustomEvent('login-success', {{
                        detail: {{
                            user_id: '{found_user['user_id']}',
                            username: '{found_user['username']}',
                            is_local: true
                        }}
                    }}));
                    </script>
                    """, unsafe_allow_html=True)
                    st.success(f"✅ 登录成功！欢迎回来，{found_user['username']}")
                    st.info("🔄 页面将自动刷新...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 用户不存在，请先注册")
    
    with tab_register:
        st.markdown("### 本地用户注册")
        st.caption("注册后可直接使用本地登录")
        
        reg_username = st.text_input("用户名", key="reg_username", 
                                     help="用户名只能包含中文、英文和数字，长度不超过20个字符")
        
        if reg_username:
            is_valid, message = user_manager.validate_username(reg_username)
            if not is_valid:
                st.error(f"用户名格式错误: {message}")
            else:
                available_username = user_manager.check_username_availability(reg_username)
                if available_username != reg_username:
                    st.info(f"用户名 '{reg_username}' 已被使用，将自动调整为 '{available_username}'")
                    reg_username = available_username
        
        # 文件夹位置设置
        st.markdown("### 📁 文件夹位置设置")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**选择文件夹安装位置：**")
            folder_location = st.radio(
                "文件夹位置",
                ["项目目录", "C盘", "D盘"],
                index=0,
                format_func=lambda x: {
                    "项目目录": "项目目录 (推荐)",
                    "C盘": "C盘",
                    "D盘": "D盘"
                }.get(x, x)
            )
        
        with col2:
            if folder_location == "项目目录":
                st.info("📁 相对路径，便于管理")
            elif folder_location == "C盘":
                st.info("💾 系统盘，启动快")
            elif folder_location == "D盘":
                st.info("💾 数据盘，空间大")
        
        folder_value = {"项目目录": "project", "C盘": "c", "D盘": "d"}.get(folder_location, "project")
        
        # 用户协议和权限确认
        st.markdown("### 📋 用户协议与权限确认")
        st.markdown("""
        #### 🔒 系统权限说明
        
        **系统将获取以下权限：**
        - 在您选择的位置创建系统文件夹
        - 读写系统文件夹内的内容
        - 创建三层平级文件夹结构：用户系统文件夹、用户数据文件夹、临时数据文件夹
        
        **系统权限限制：**
        - 系统只能访问您授权创建的文件夹
        - 系统无法访问您电脑上的其他文件
        - 所有操作都在您的明确授权下进行
        
        **文件夹用途：**
        - **用户系统文件夹**: 存放用户ID等系统数据，平时不常用
        - **用户数据文件夹**: 存放您不会删除的个人文件，系统可读取
        - **临时数据文件夹**: 存放任务执行时的临时文件，会定期清理
        
        **了解更多：**
        - [用户协议](#) | [安全说明和使用指南](#)
        
        所有操作均由您主动授权发起，操作结果由您自行承担责任。
        """)
        
        agree_all = st.checkbox("✅ 我已阅读并同意用户协议，并确认系统权限获取", key="agree_all")
        
        # 注册按钮
        if st.button("🚀 本地注册", type="primary", disabled=not (reg_username and agree_all)):
            if not reg_username:
                st.error("请输入用户名")
            elif not agree_all:
                st.error("请同意用户协议并确认系统权限获取")
            else:
                # 本地注册逻辑
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # 步骤1: 验证用户名
                    status_text.text("正在验证用户名...")
                    progress_bar.progress(10)
                    is_valid, message = user_manager.validate_username(reg_username)
                    if not is_valid:
                        st.error(f"用户名格式错误: {message}")
                        progress_bar.empty()
                        status_text.empty()
                        st.stop()
                    
                    # 步骤2: 检查用户名可用性
                    status_text.text("检查用户名可用性...")
                    progress_bar.progress(20)
                    available_username = user_manager.check_username_availability(reg_username)
                    
                    # 步骤3: 生成本地用户ID
                    status_text.text("生成用户ID...")
                    progress_bar.progress(30)
                    import random
                    local_user_id = f"local_{hashlib.md5(f'{time.time()}_{random.randint(10000, 99999)}'.encode()).hexdigest()[:8]}"
                    
                    # 步骤4: 保存本地用户信息
                    status_text.text("保存用户信息...")
                    progress_bar.progress(40)
                    user_info = user_manager.save_user(local_user_id, available_username, folder_value)
                    
                    # 步骤5: 创建文件夹和系统信息文件
                    status_text.text("创建文件夹结构...")
                    progress_bar.progress(50)
                    st.info("🔧 正在创建文件夹，如需权限会弹出UAC提示，请点击'是'允许...")
                    
                    # 使用重试机制创建文件夹
                    result = create_folders_with_retry(local_user_id, available_username, folder_value)
                    
                    if result["success"]:
                        status_text.text("完成注册...")
                        progress_bar.progress(90)
                        
                        st.session_state.user_session = {
                            "session_id": f"local_{local_user_id}_{datetime.now().timestamp()}",
                            "user_id": local_user_id,
                            "username": available_username,
                            "is_local": True
                        }
                        st.markdown(f"""
                        <script>
                        localStorage.setItem('idle_accelerator_session', JSON.stringify({{
                            user_id: '{local_user_id}',
                            username: '{available_username}',
                            is_local: true
                        }}));
                        </script>
                        """, unsafe_allow_html=True)
                        st.markdown(f"""
                        <script>
                        window.dispatchEvent(new CustomEvent('login-success', {{
                            detail: {{
                                user_id: '{local_user_id}',
                                username: '{available_username}',
                                is_local: true
                            }}
                        }}));
                        </script>
                        """, unsafe_allow_html=True)
                        progress_bar.progress(100)
                        status_text.text("注册成功！")
                        
                        st.success("✅ 本地注册成功！")
                        
                        st.markdown("### 📁 文件夹创建确认")
                        st.markdown(f"""
**已根据您的授权创建以下文件夹和文件：**
- 系统文件夹: `{result.get('base_path', 'N/A')}`
- 用户系统文件夹: `{result.get('user_system_dir', 'N/A')}`
- 用户数据文件夹: `{result.get('user_data_dir', 'N/A')}`
- 临时数据文件夹: `{result.get('temp_data_dir', 'N/A')}`
- 文档文件夹: `{result.get('docs_dir', 'N/A')}`
- 系统信息文件: `{result.get('system_file', 'N/A')}`

**文件说明：**
- `system_info.json` 包含系统运行所需信息，请勿删除
- 用户系统文件夹存放用户ID等系统数据，平时不常用
- 用户数据文件夹用于存放您不会删除的个人文件
- 临时数据文件夹用于任务执行时的临时文件，会定期清理
- 文档文件夹包含用户协议和安全说明，可随时查看

**重要提示：**
- 系统只能访问您授权创建的文件夹内容
- 如需系统读取您的文件，请将文件放入用户数据文件夹
- 临时文件会在任务完成后24小时内自动清理
- 删除操作需您手动完成

**操作记录已保存至本地日志，供您核查。**
""")
                        
                        st.info("💡 您现在可以开始使用系统的完整功能了！")
                        time.sleep(2)
                        st.rerun()
                    else:
                        progress_bar.empty()
                        status_text.empty()
                        
                        st.error(f"❌ 文件夹创建失败")
                        st.error(f"错误：{result['error']}")
                        st.warning(f"建议：{result['suggestion']}")
                        
                        if st.button("🔄 重试创建文件夹", key="retry_folder_creation"):
                            st.rerun()
                        
                        if st.checkbox("显示技术详情", key="show_script_details"):
                            st.code(f"""
脚本退出代码: {result.get('script_exit_code', 'N/A')}
脚本输出: {result.get('script_stdout', 'N/A')}
脚本错误: {result.get('script_stderr', 'N/A')}
""", language="text")
                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"注册失败: {str(e)}")

# 页脚
st.divider()
st.caption("闲置计算加速器 v2.0 | 开源免费项目 | 适配新版调度中心API")

# 自动刷新
if st.session_state.auto_refresh:
    time.sleep(REFRESH_INTERVAL)
    st.rerun()
# ==============================================================   