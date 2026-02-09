"""
web_interface.py
闲置计算加速器 - 网页控制界面
修复版：适配新版调度中心API + 分布式任务处理
"""

import streamlit as st
import requests
import time
import json
import os
import hashlib
import ctypes
import sys
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 导入分布式任务处理模块
try:
    from distributed_task import DistributedTaskManager, DISTRIBUTED_TASK_TEMPLATES
    DISTRIBUTED_TASK_AVAILABLE = True
except ImportError:
    DISTRIBUTED_TASK_AVAILABLE = False
    print("Warning: distributed_task module not available, distributed tasks disabled")

# 页面配置
st.set_page_config(
    page_title="闲置计算加速器",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 配置
SCHEDULER_URL = "http://localhost:8000"
REFRESH_INTERVAL = 30  # 降低自动刷新间隔（秒），减少闪烁

# 初始化分布式任务管理器
if DISTRIBUTED_TASK_AVAILABLE:
    distributed_task_manager = DistributedTaskManager(SCHEDULER_URL)
else:
    distributed_task_manager = None

# 初始化 session state
if 'task_history' not in st.session_state:
    st.session_state.task_history = []
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False  # 默认关闭自动刷新
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'user_session' not in st.session_state:
    st.session_state.user_session = None
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
if 'last_node_status' not in st.session_state:
    st.session_state.last_node_status = {'online': 0, 'total': 0}
if 'last_node_check_time' not in st.session_state:
    st.session_state.last_node_check_time = datetime.now()
# 添加缓存相关状态
if 'cache_data' not in st.session_state:
    st.session_state.cache_data = {}
if 'last_cache_cleanup' not in st.session_state:
    st.session_state.last_cache_cleanup = datetime.now()
if "session_id" not in st.session_state:
    # 生成唯一的会话ID
    st.session_state.session_id = hashlib.md5(f"{datetime.now().isoformat()}_{os.getpid()}".encode()).hexdigest()[:16]

# 页面关闭时清理缓存（通过JavaScript）
st.markdown("""
<script>
window.addEventListener('beforeunload', function() {
    // 通知服务器清理缓存
    navigator.sendBeacon('/cleanup_cache', JSON.stringify({
        session_id: window.location.search.split('session_id=')[1] || ''
    }));
});
</script>
""", unsafe_allow_html=True)

# 自定义CSS样式，修复白屏问题
st.markdown("""
<style>
    /* 主背景色 */
    .stApp {
        background-color: #0e1117 !important;
        color: #ffffff !important;
    }
    
    /* 主容器 */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        background-color: #1f242d !important;
        border-radius: 8px;
        margin: 0.5rem;
        padding: 1rem;
    }
    
    /* 修复标签页背景色 */
    .stTabs {
        background-color: #1f242d !important;
        border-radius: 8px;
        padding: 1rem;
    }
    
    .stTab {
        background-color: #2d333d !important;
        border-radius: 6px;
        padding: 1rem;
    }
    
    /* 按钮样式 */
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        font-size: 16px;
        background-color: #2b2d30 !important;
        color: white !important;
        border: 1px solid #444746 !important;
    }
    
    /* 输入框样式 */
    .stTextInput>div>div>input {
        border-radius: 5px;
        background-color: #2b2d30 !important;
        color: white !important;
        border: 1px solid #444746 !important;
    }
    
    /* 选择框样式 */
    .stSelectbox>div>div>select {
        border-radius: 5px;
        background-color: #2b2d30 !important;
        color: white !important;
        border: 1px solid #444746 !important;
    }
    
    /* 数据框样式 */
    .stDataFrame {
        background-color: #2d333d !important;
        border-radius: 6px;
    }
    
    /* 代码块样式 */
    .stCodeBlock {
        background-color: #0d1117 !important;
        border-radius: 6px;
    }
    
    /* 展开器样式 */
    .streamlit-expanderHeader {
        background-color: #2d333d !important;
        border-radius: 6px;
        margin-top: 0.5rem;
    }
    
    /* 标题和文本样式 */
    h1, h2, h3, h4, h5, h6, p, div, span, label {
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# 本地用户管理
def get_local_users_dir():
    """获取本地用户目录路径"""
    users_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_users")
    os.makedirs(users_dir, exist_ok=True)
    return users_dir

def generate_local_user_id():
    """生成本地用户ID"""
    import hashlib
    import time
    timestamp = str(time.time())
    user_id = f"local_{hashlib.md5(timestamp.encode()).hexdigest()[:8]}"
    return user_id

def validate_username(username):
    """验证用户名格式"""
    import re
    
    # 检查长度（20个字符以内）
    if len(username) > 20:
        return False, "用户名长度不能超过20个字符"
    
    # 检查是否只包含中文、英文、数字
    pattern = r'^[\u4e00-\u9fa5a-zA-Z0-9]+$'
    if not re.match(pattern, username):
        return False, "用户名只能包含中文、英文和数字"
    
    return True, "用户名格式正确"

def check_username_availability(username):
    """检查用户名是否可用，如果不可用则生成可用用户名"""
    users = list_local_users()
    existing_usernames = [user['username'] for user in users]
    
    if username not in existing_usernames:
        return username  # 用户名可用
    
    # 用户名已存在，添加后缀
    counter = 1
    while True:
        new_username = f"{username}_{counter}"
        if new_username not in existing_usernames:
            return new_username
        counter += 1
        # 防止无限循环
        if counter > 999:
            import random
            return f"{username}_{random.randint(1000, 9999)}"

def save_local_user(user_id, username, folder_location="project"):
    """保存本地用户信息"""
    users_dir = get_local_users_dir()
    user_file = os.path.join(users_dir, f"{user_id}.json")
    
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

def get_local_user(user_id):
    """获取本地用户信息"""
    users_dir = get_local_users_dir()
    user_file = os.path.join(users_dir, f"{user_id}.json")
    
    if os.path.exists(user_file):
        with open(user_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def update_local_user_login(user_id):
    """更新用户最后登录时间"""
    user_info = get_local_user(user_id)
    if user_info:
        user_info["last_login"] = datetime.now().isoformat()
        
        users_dir = get_local_users_dir()
        user_file = os.path.join(users_dir, f"{user_id}.json")
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_info, f, ensure_ascii=False, indent=2)
        
        return True
    return False

def list_local_users():
    """列出所有本地用户"""
    users_dir = get_local_users_dir()
    users = []
    
    if os.path.exists(users_dir):
        for file_name in os.listdir(users_dir):
            if file_name.endswith('.json'):
                user_id = file_name[:-5]  # 去掉.json后缀
                user_info = get_local_user(user_id)
                if user_info:
                    users.append(user_info)
    
    return users

# 设备ID生成和缓存管理
def generate_device_id():
    """生成设备唯一标识"""
    import hashlib
    import random
    
    # 基于时间戳和随机数生成设备ID
    device_info = f"{datetime.now().isoformat()}_{random.randint(10000, 99999)}"
    device_id = hashlib.md5(device_info.encode()).hexdigest()[:8]
    return device_id

def get_device_node_mapping():
    """获取设备到节点的映射"""
    if "device_node_mapping" not in st.session_state:
        st.session_state.device_node_mapping = {}
    return st.session_state.device_node_mapping

def update_device_mapping(device_id, node_id):
    """更新设备映射"""
    mapping = get_device_node_mapping()
    mapping[device_id] = node_id
    st.session_state.device_node_mapping = mapping

def get_node_by_device(device_id):
    """根据设备ID获取节点ID"""
    mapping = get_device_node_mapping()
    return mapping.get(device_id)

# 缓存管理和数据比较函数 - 使用临时缓存文件
def get_cache_file_path():
    """获取缓存文件路径"""
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"session_cache_{st.session_state.get('session_id', 'default')}.json")

def load_cache_data():
    """加载缓存数据"""
    try:
        cache_file = get_cache_file_path()
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"nodes_online_count": 0, "last_update_time": None, "health_status": False}

def save_cache_data(data):
    """保存缓存数据"""
    try:
        cache_file = get_cache_file_path()
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def cleanup_cache():
    """清理缓存文件"""
    try:
        cache_file = get_cache_file_path()
        if os.path.exists(cache_file):
            os.remove(cache_file)
    except:
        pass

def update_cache_and_check_change(new_data):
    """更新缓存并检查数据是否变化"""
    # 只保存最小必要的数据
    cache_data = {
        "nodes_online_count": new_data.get("nodes", {}).get("online", 0),
        "last_update_time": datetime.now().isoformat(),
        "health_status": new_data.get("health_status", False)
    }
    
    # 加载旧数据
    old_data = load_cache_data()
    
    # 检查关键数据是否变化
    changed = (
        old_data.get("nodes_online_count") != cache_data.get("nodes_online_count") or
        old_data.get("health_status") != cache_data.get("health_status")
    )
    
    # 保存新数据
    save_cache_data(cache_data)
    
    return changed

# 定期清理缓存（改为清理过期的会话缓存）
def cleanup_expired_cache():
    """清理过期的会话缓存文件"""
    try:
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
        if not os.path.exists(cache_dir):
            return True
        
        current_time = datetime.now()
        for file_name in os.listdir(cache_dir):
            if file_name.startswith("session_cache_") and file_name.endswith(".json"):
                file_path = os.path.join(cache_dir, file_name)
                # 检查文件修改时间，如果超过2小时则删除
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if (current_time - file_mod_time).seconds > 7200:  # 2小时
                    os.remove(file_path)
        
        st.session_state.last_cache_cleanup = current_time
        return True
    except Exception as e:
        return False

# 定期清理缓存
if (datetime.now() - st.session_state.last_cache_cleanup).seconds > 3600:
    cleanup_expired_cache()

def is_admin():
    """检查当前是否有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def request_admin_privileges():
    """请求管理员权限"""
    if is_admin():
        return True
    
    # 重新启动程序并请求管理员权限
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    return False

def check_write_permission(path):
    """检查指定路径是否有写入权限"""
    try:
        # 尝试创建测试文件
        test_file = os.path.join(path, ".permission_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return True
    except (PermissionError, OSError):
        return False

def ensure_directory_with_permission(path):
    """确保目录存在且有写入权限"""
    # 首先尝试创建目录
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        return False, "权限不足，无法创建文件夹"
    
    # 然后检查写入权限
    if not check_write_permission(path):
        return False, "权限不足，无法写入文件"
    
    return True, "权限检查通过"

def create_folders_with_retry(user_id, username, folder_location, max_retries=2):
    """带重试机制的文件夹创建"""
    import time
    
    for attempt in range(max_retries + 1):  # 包括初始尝试
        if attempt > 0:
            time.sleep(1)  # 重试前等待1秒
        
        result = create_folders_with_script(user_id, username, folder_location)
        
        if result["success"]:
            return result
        
        # 如果失败，记录错误并继续重试
        if attempt < max_retries:
            print(f"文件夹创建失败，尝试第 {attempt + 1} 次重试...")
            continue
    
    # 所有重试都失败
    return {
        "success": False,
        "error": f"文件夹创建失败，已重试 {max_retries} 次",
        "suggestion": "请检查系统权限或选择其他位置",
        "last_error": result.get("error", "未知错误")
    }

def create_folders_with_script(user_id, username, folder_location):
    import subprocess
    import tempfile
    
    # 创建临时文件用于接收脚本结果
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # 构建脚本命令
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "create_folders.py")
        cmd = [
            sys.executable,
            script_path,
            "--user-id", user_id,
            "--username", username,
            "--folder-location", folder_location,
            "--output", temp_path
        ]
        
        # 执行脚本
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30  # 30秒超时
        )
        
        # 读取脚本结果
        with open(temp_path, 'r', encoding='utf-8') as f:
            script_result = json.load(f)
        
        # 添加脚本执行信息
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
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass

def request_uac_permission_for_folder_creation(folder_path):
    """请求UAC权限以创建文件夹"""
    try:
        # 尝试直接创建文件夹
        os.makedirs(folder_path, exist_ok=True)
        
        # 测试写入权限
        test_file = os.path.join(folder_path, ".permission_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        
        return True, "权限获取成功", None
    except PermissionError as e:
        # 权限不足，尝试通过UAC请求权限
        try:
            # 使用Windows API请求权限
            import ctypes
            from ctypes import wintypes
            
            # 准备ShellExecute参数
            hwnd = None
            operation = "runas"  # 请求UAC提升
            exec_file = sys.executable
            params = f'"{os.path.join(os.path.dirname(__file__), "request_permission.py")}" "{folder_path}"'
            show_cmd = 1
            current_dir = None
            
            # 调用ShellExecute请求UAC权限
            result = ctypes.windll.shell32.ShellExecuteW(
                hwnd, operation, exec_file, params, current_dir, show_cmd
            )
            
            # 检查结果
            if result > 32:  # 成功
                return True, "权限请求已发送，请确认UAC提示", None
            else:
                return False, f"权限请求失败，错误代码: {result}", "请以管理员身份运行程序"
        except Exception as e:
            return False, f"权限请求异常: {str(e)}", "请以管理员身份运行程序"
    except Exception as e:
        return False, f"创建文件夹失败: {str(e)}", "请检查文件夹路径是否正确"

def create_system_info_file(user_id, username, folder_location):
    """创建系统信息文件和文件夹结构 - 包含权限检查"""
    # 只存储系统需要的最小信息
    system_info = {
        "user_id": user_id,
        "username": username,
        "purpose": "此文件包含闲置计算加速器系统运行所需的信息，请勿删除"
    }
    
    # 根据用户选择的文件夹位置确定路径
    if folder_location == "project":
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")
    elif folder_location == "c":
        base_path = "C:\\idle-sense-system-data"  # 使用醒目的项目名开头
    elif folder_location == "d":
        base_path = "D:\\idle-sense-system-data"  # 使用醒目的项目名开头
    else:
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")
    
    # 检查并确保有权限创建目录
    has_permission, message = ensure_directory_with_permission(base_path)
    if not has_permission:
        return {
            "success": False,
            "error": message,
            "suggestion": f"请以管理员身份运行程序，或选择其他位置创建文件夹。当前尝试位置：{base_path}"
        }
    
    # 创建三层平级文件夹结构
    user_system_dir = os.path.join(base_path, "user_system", user_id)  # 存放用户ID等系统数据
    user_data_dir = os.path.join(base_path, "user_data")               # 用户存放读写数据的地方
    temp_data_dir = os.path.join(base_path, "temp_data")               # 临时存放数据给别人调用
    docs_dir = os.path.join(user_system_dir, "docs")                   # 存放说明文档
    
    for dir_path in [user_system_dir, user_data_dir, temp_data_dir, docs_dir]:
        has_permission, message = ensure_directory_with_permission(dir_path)
        if not has_permission:
            return {
                "success": False,
                "error": message,
                "suggestion": f"无法创建子文件夹，请检查权限。当前尝试位置：{dir_path}"
            }
    
    # 创建系统信息文件（在user_system文件夹中）
    system_file_path = os.path.join(user_system_dir, "system_info.json")
    try:
        with open(system_file_path, "w", encoding="utf-8") as f:
            json.dump(system_info, f, ensure_ascii=False, indent=2)
    except PermissionError:
        return {
            "success": False,
            "error": "权限不足，无法创建系统信息文件",
            "suggestion": f"请检查对 {user_system_dir} 的写入权限"
        }
    
    # 创建用户协议文档
    user_agreement_path = os.path.join(docs_dir, "用户协议.md")
    try:
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
    except Exception as e:
        return {
            "success": False,
            "error": f"创建用户协议失败: {str(e)}",
            "suggestion": f"请检查对 {docs_dir} 的写入权限"
        }
    
    # 创建安全说明和使用指南文档
    security_guide_path = os.path.join(docs_dir, "安全说明和使用指南.md")
    try:
        with open(security_guide_path, "w", encoding="utf-8") as f:
            f.write(f"""# 安全说明和使用指南

## 文件夹结构说明

您的数据存储在以下位置：
- 系统文件夹: `{base_path}`
- 用户系统文件夹: `{user_system_dir}`
- 用户数据文件夹: `{user_data_dir}`
- 临时数据文件夹: `{temp_data_dir}`

## 权限说明

### 系统权限范围
- 系统只能读写您授权创建的文件夹内容
- 系统无法访问您电脑上的其他文件
- 所有操作都在您的明确授权下进行

### 文件夹用途
- **用户系统文件夹** (`{user_system_dir}`): 存放用户ID等系统数据，平时不常用
- **用户数据文件夹** (`{user_data_dir}`): 存放您不会删除的个人文件，系统可读取
- **临时数据文件夹** (`{temp_data_dir}`): 存放任务执行时的临时文件，会定期清理
- **文档文件夹** (`{docs_dir}`): 存放系统说明文档

## 如何让系统读取您的文件

如果您需要系统处理您的文件：
1. 将文件放入用户数据文件夹: `{user_data_dir}`
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
    except Exception as e:
        return {
            "success": False,
            "error": f"创建安全说明失败: {str(e)}",
            "suggestion": f"请检查对 {docs_dir} 的写入权限"
        }
    
    return {
        "success": True,
        "base_path": base_path,
        "user_system_dir": user_system_dir,
        "user_data_dir": user_data_dir,
        "temp_data_dir": temp_data_dir,
        "docs_dir": docs_dir,
        "system_file": system_file_path,
        "user_agreement": user_agreement_path,
        "security_guide": security_guide_path
    }

def read_system_info(user_id):
    """读取系统信息文件"""
    for location in ["project", "c", "d"]:
        if location == "project":
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")
        elif location == "c":
            base_path = "C:\\idle-sense-system-data"
        elif location == "d":
            base_path = "D:\\idle-sense-system-data"
        
        # 系统信息文件现在位于大文件夹根目录
        system_file_path = os.path.join(base_path, "idle_sense_system.json")
        
        if os.path.exists(system_file_path):
            with open(system_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    
    return None

# 工具函数 - 增强错误处理
def check_scheduler_health():
    """检查调度中心是否在线，并获取节点状态 - 优化版"""
    try:
        # 减少超时时间，更快检测连接问题
        response = requests.get(f"{SCHEDULER_URL}/", timeout=3)
        if response.status_code != 200:
            # 尝试获取健康端点
            try:
                health_response = requests.get(f"{SCHEDULER_URL}/health", timeout=2)
                if health_response.status_code != 200:
                    return False, {"error": f"HTTP {health_response.status_code}"}
            except:
                return False, {"error": "无法连接到调度中心"}
        
        # 简化健康检查和节点信息获取流程
        health_response = requests.get(f"{SCHEDULER_URL}/health", timeout=2)
        health_data = health_response.json() if health_response.status_code == 200 else {"status": "reachable"}
        
        # 仅获取一次所有节点信息，减少API调用
        try:
            nodes_response = requests.get(f"{SCHEDULER_URL}/api/nodes", params={"online_only": False}, timeout=4)
            if nodes_response.status_code == 200:
                nodes_data = nodes_response.json()
                all_nodes = nodes_data.get("nodes", [])
                online_nodes = sum(1 for node in all_nodes if node.get("status") == "online")
                
                # 添加节点统计信息
                health_data["nodes"] = {
                    "online": online_nodes,
                    "total": len(all_nodes)
                }
            else:
                health_data["nodes"] = {"online": 0, "total": 0}
        except Exception as e:
            health_data["nodes"] = {"online": 0, "total": 0}
        
        return True, health_data
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

def submit_distributed_task(name, description, code_template, data, chunk_size=10, 
                           max_parallel_chunks=5, merge_code=None):
    """提交分布式任务"""
    if not DISTRIBUTED_TASK_AVAILABLE:
        return False, {"error": "分布式任务处理模块不可用"}
    
    try:
        # 提交分布式任务
        task_id = distributed_task_manager.submit_distributed_task(
            name=name,
            description=description,
            code_template=code_template,
            data=data,
            chunk_size=chunk_size,
            max_parallel_chunks=max_parallel_chunks,
            merge_code=merge_code
        )
        
        # 创建任务分片
        if distributed_task_manager.create_task_chunks(task_id):
            # 在后台线程中执行任务
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

def get_all_nodes():
    """获取所有节点信息 - 优化版：减少API调用次数"""
    try:
        # 仅调用一次API获取所有节点，在本地处理在线状态
        response = requests.get(f"{SCHEDULER_URL}/api/nodes?online_only=false", timeout=5)
        if response.status_code == 200:
            data = response.json()
            nodes = []
            online_count = 0
            
            # 转换数据结构并在本地确定在线状态
            for node in data.get("nodes", []):
                node_id = node.get("node_id", "unknown")
                # 直接从节点信息获取状态
                status = node.get("status", "offline")
                is_online = status == "online"
                
                if is_online:
                    online_count += 1
                
                nodes.append({
                    "node_id": node_id,
                    "status": status,
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
                "total_idle": online_count
            }
        
        # 兼容性降级
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



def stop_node(node_id: str):
    """停止指定节点"""
    try:
        # 使用正确的停止节点API
        response = requests.post(f"{SCHEDULER_URL}/api/nodes/{node_id}/stop", timeout=5)
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
            
            with tab_login:
                st.markdown("### 本地用户登录")
                st.caption("输入您的用户名或用户ID进行登录")
                
                # 显示已注册的本地用户（可选）
                with st.expander("查看已注册用户", expanded=False):
                    local_users = list_local_users()
                    if local_users:
                        for user in local_users:
                            st.write(f"👤 {user['username']} (ID: {user['user_id']})")
                    else:
                        st.info("暂无已注册用户")
                
                login_username = st.text_input("用户名或用户ID", key="login_username")
                
                if st.button("🔐 本地登录", key="local_login_button"):
                    if not login_username:
                        st.error("请输入用户名或用户ID")
                    else:
                        # 本地登录逻辑
                        local_users = list_local_users()
                        found_user = None
                        
                        # 按用户名查找
                        for user in local_users:
                            if user['username'] == login_username or user['user_id'] == login_username:
                                found_user = user
                                break
                        
                        if found_user:
                            # 更新最后登录时间
                            update_local_user_login(found_user['user_id'])
                            
                            # 创建本地session
                            st.session_state.user_session = {
                                "session_id": f"local_{found_user['user_id']}_{datetime.now().timestamp()}",
                                "user": found_user,
                                "username": found_user['username'],
                                "is_local": True  # 标记为本地用户
                            }
                            
                            st.success(f"✅ 登录成功！欢迎回来，{found_user['username']}")
                            st.info("🔄 页面将自动刷新...")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ 用户不存在，请先注册")
                            st.info("💡 提示：如果您是新用户，请切换到'注册'标签页")
            
            # 当前版本暂只支持本地登录
            st.info("当前版本支持本地登录，请使用本地用户登录功能")
            
            with tab_register:
                st.markdown("### 本地用户注册")
                st.caption("注册后可直接使用本地登录")
                
                reg_username = st.text_input("用户名", key="reg_username", help="用户名只能包含中文、英文和数字，长度不超过20个字符")
                
                # 实时验证用户名
                if reg_username:
                    is_valid, message = validate_username(reg_username)
                    if not is_valid:
                        st.error(f"用户名格式错误: {message}")
                    else:
                        # 检查用户名是否可用
                        available_username = check_username_availability(reg_username)
                        if available_username != reg_username:
                            st.info(f"用户名 '{reg_username}' 已被使用，将自动调整为 '{available_username}'")
                            reg_username = available_username
                
                # 文件夹位置选择
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
                
                # 转换文件夹位置值
                folder_value = {"项目目录": "project", "C盘": "c", "D盘": "d"}.get(folder_location, "project")
                
                # 合并的用户协议和权限确认
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
                
                # 合并的勾选项
                agree_all = st.checkbox("✅ 我已阅读并同意用户协议，并确认系统权限获取", key="agree_all")
                
                # 注册按钮
                if st.button("🚀 本地注册", type="primary", disabled=not (reg_username and agree_all)):
                    if not reg_username:
                        st.error("请输入用户名")
                    elif not agree_all:
                        st.error("请同意用户协议并确认系统权限获取")
                    else:
                        # 本地注册逻辑
                        # 创建进度条
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        try:
                            # 步骤1: 验证用户名
                            status_text.text("正在验证用户名...")
                            progress_bar.progress(10)
                            is_valid, message = validate_username(reg_username)
                            if not is_valid:
                                st.error(f"用户名格式错误: {message}")
                                progress_bar.empty()
                                status_text.empty()
                                st.stop()  # 停止执行，而不是return
                            
                            # 步骤2: 检查用户名可用性
                            status_text.text("检查用户名可用性...")
                            progress_bar.progress(20)
                            available_username = check_username_availability(reg_username)
                            
                            # 步骤3: 生成本地用户ID
                            status_text.text("生成用户ID...")
                            progress_bar.progress(30)
                            local_user_id = generate_local_user_id()
                            
                            # 步骤4: 保存本地用户信息
                            status_text.text("保存用户信息...")
                            progress_bar.progress(40)
                            user_info = save_local_user(local_user_id, available_username, folder_value)
                            
                            # 步骤5: 创建文件夹和系统信息文件
                            status_text.text("创建文件夹结构...")
                            progress_bar.progress(50)
                            st.info("🔧 正在创建文件夹，如需权限会弹出UAC提示，请点击'是'允许...")
                            
                            # 使用重试机制创建文件夹
                            paths = create_folders_with_retry(local_user_id, available_username, folder_value)
                            
                            if paths["success"]:
                                # 步骤6: 创建用户会话
                                status_text.text("完成注册...")
                                progress_bar.progress(90)
                                
                                st.session_state.user_session = {
                                    "session_id": f"local_{local_user_id}_{datetime.now().timestamp()}",
                                    "user": user_info,
                                    "username": available_username,
                                    "is_local": True
                                }
                                
                                # 完成注册
                                progress_bar.progress(100)
                                status_text.text("注册成功！")
                                
                                st.success("✅ 本地注册成功！")
                                
                                # 显示文件夹创建确认
                                st.markdown("### 📁 文件夹创建确认")
                                st.markdown(f"""
**已根据您的授权创建以下文件夹和文件：**
- 系统文件夹: `{paths["base_path"]}`
- 用户系统文件夹: `{paths["user_system_dir"]}`
- 用户数据文件夹: `{paths["user_data_dir"]}`
- 临时数据文件夹: `{paths["temp_data_dir"]}`
- 文档文件夹: `{paths["docs_dir"]}`
- 系统信息文件: `{paths["system_file"]}`

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
                                # 文件夹创建失败
                                progress_bar.empty()
                                status_text.empty()
                                
                                st.error(f"❌ 文件夹创建失败")
                                st.error(f"错误：{paths['error']}")
                                st.warning(f"建议：{paths['suggestion']}")
                                
                                # 提供重试选项
                                if st.button("🔄 重试创建文件夹", key="retry_folder_creation"):
                                    st.rerun()
                                
                                # 显示技术详情（可选）
                                if st.checkbox("显示技术详情", key="show_script_details"):
                                    st.code(f"""
脚本退出代码: {paths.get('script_exit_code', 'N/A')}
脚本输出: {paths.get('script_stdout', 'N/A')}
脚本错误: {paths.get('script_stderr', 'N/A')}
""", language="text")
                                
                                # 提供备选方案
                                st.markdown("### 🔧 解决方案")
                                st.markdown("""
1. **重试操作**：点击上方"重试创建文件夹"按钮
2. **选择其他位置**：返回注册页面，选择"项目目录"位置
3. **手动创建文件夹**：在目标位置手动创建`idle-sense-system-data`文件夹
4. **检查脚本文件**：确认`create_folders.py`文件存在于程序目录
""")
                        except Exception as e:
                            progress_bar.empty()
                            status_text.empty()
                            st.error(f"注册失败: {str(e)}")
            
            # 显示本地用户统计
            with st.expander("📊 本地用户统计", expanded=False):
                local_users = list_local_users()
                st.metric("本地用户总数", len(local_users))
                
                if local_users:
                    st.write("**最近注册用户：**")
                    recent_users = sorted(local_users, key=lambda x: x.get('created_at', ''), reverse=True)[:3]
                    for user in recent_users:
                        created_at = user.get('created_at', '未知时间')
                        if created_at != '未知时间':
                            try:
                                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                created_at = dt.strftime('%Y-%m-%d %H:%M')
                            except:
                                pass
                        st.write(f"👤 {user['username']} - {created_at}")
            
            # 当前版本暂只支持本地登录
            st.info("💡 提示：当前版本支持本地用户注册和登录，无需网络连接")

# 用户已登录，显示主界面
if st.session_state.user_session:
    # 侧边栏状态显示
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📊 系统状态")
        
        # 检查调度器健康状态
        health_ok, health_info = check_scheduler_health()
        
        if health_ok:
            st.success("🟢 调度器在线")
            idle_nodes = health_info.get("nodes", {}).get("online", 0)
            st.metric("在线设备", idle_nodes)
            if idle_nodes > 0:
                st.success(f"✅ 有 {idle_nodes} 台设备在线，可以执行任务")
            else:
                st.warning("⚠️ 没有设备在线，请激活设备")
        else:
            st.error("🔴 调度器离线")
            st.info("请检查调度器服务是否正常运行")

# 主界面 - 标签页布局
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 提交任务", "📊 任务监控", "🖥️ 节点管理", "📈 系统统计", "📋 任务结果"])

# 标签页1: 提交任务
with tab1:
    st.header("提交计算任务")
    
    # 任务类型选择
    task_type = st.radio(
        "选择任务类型",
        ["分布式任务", "单节点任务"],
        horizontal=True,
        help="分布式任务由多个节点协作执行，充分利用闲置计算资源"
    )
    
    if task_type == "分布式任务":
        if not DISTRIBUTED_TASK_AVAILABLE:
            st.error("❌ 分布式任务处理模块不可用，请确保已安装distributed_task.py")
        else:
            st.info("🚀 **分布式任务** 可以利用多个节点的计算资源并行处理大型任务，大幅提升处理效率")
        st.markdown("""
        ### 🤔 什么是分布式任务？
        
        分布式任务就是将一个大任务拆分成多个小任务，让多台电脑同时处理，最后汇总结果。
        
        **简单比喻：**
        - **单节点任务**：像一个人独自完成1000道数学题
        - **分布式任务**：像10个人每人做100道题，最后汇总所有答案
        
        **优势：**
        - 速度快：10台电脑并行处理，理论上速度提升10倍
        - 能处理更大数据：单台电脑内存不够时，可以分散到多台处理
        - 容错性：某台电脑出问题，其他电脑继续工作
        """)
        st.subheader("分布式任务配置")
        
        # 分布式任务模板选择
        template_name = st.selectbox(
            "选择任务类型",
            options=list(DISTRIBUTED_TASK_TEMPLATES.keys()),
            format_func=lambda x: DISTRIBUTED_TASK_TEMPLATES[x]["name"],
            help="选择预定义的任务类型，或自定义任务"
        )
        
        # 显示模板描述
        if template_name in DISTRIBUTED_TASK_TEMPLATES:
            st.info(DISTRIBUTED_TASK_TEMPLATES[template_name]["description"])
        
        # 任务配置
        col1, col2 = st.columns(2)
        
        with col1:
            task_name = st.text_input("任务名称", value=f"分布式任务_{int(time.time())}")
            chunk_size = st.number_input(
                "分片大小（每组数据数量）", 
                min_value=1, 
                max_value=1000, 
                value=10, 
                step=1, 
                help="分片是指将大数据分成小块，每个节点处理一小块。例如：1000条数据，分片大小为100，则会分成10块，由10个节点并行处理"
            )
        
        with col2:
            task_description = st.text_input("任务描述", value="使用多节点协作处理大型任务")
            max_parallel_chunks = st.number_input(
                "最大并行节点数", 
                min_value=1, 
                max_value=50, 
                value=5, 
                step=1,
                help="同时执行任务的节点数量。例如：设置为5表示最多5个节点同时处理数据分片"
            )
        
        # 数据输入
        st.subheader("任务数据")
        data_input_method = st.radio(
            "数据输入方式",
            ["手动输入", "从文件上传"],
            horizontal=True
        )
        
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
        
        else:  # 从文件上传
            uploaded_file = st.file_uploader("上传JSON文件", type=["json"])
            if uploaded_file:
                try:
                    content = uploaded_file.read().decode("utf-8")
                    task_data = json.loads(content)
                    st.success(f"文件上传成功，包含 {len(task_data) if isinstance(task_data, (list, dict)) else 1} 项数据")
                except Exception as e:
                    st.error(f"文件解析失败: {e}")
        
        # 添加通用任务选项
        st.markdown("---")
        st.subheader("🎯 通用任务处理")
        st.info("💡 **通用任务** 可以处理任何类型的计算任务，不限于预设模板")
        
        # 通用任务选项
        use_custom_task = st.checkbox("使用通用任务（自定义处理逻辑）", help="不使用预设模板，完全自定义任务处理方式")
        
        if use_custom_task:
            st.subheader("自定义任务配置")
            
            st.markdown("""
            ### 📝 自定义任务说明
            
            自定义任务分为两部分：
            1. **数据处理代码**：每个节点如何处理分配给它的数据
            2. **结果合并代码**：如何将所有节点的处理结果合并
            
            ### 🔧 关键变量说明
            - `__DATA__`：系统自动分配给当前节点的数据片段
            - `__CHUNK_ID__`：当前数据片段的唯一标识符
            - `__CHUNK_INDEX__`：当前数据片段的序号（从0开始）
            - `__CHUNK_RESULTS__`：所有节点返回的结果列表（仅用于合并代码）
            - `__result__`：当前节点的处理结果（必须设置）
            - `__MERGED_RESULT__`：所有节点结果的最终合并结果（必须设置）
            """)
            
            # 自定义处理代码
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
                        # 根据是否使用自定义任务选择代码模板
                        if use_custom_task:
                            # 使用自定义代码
                            code_template = custom_map_code
                            merge_code = custom_merge_code
                        else:
                            # 使用预设模板
                            code_template = DISTRIBUTED_TASK_TEMPLATES[template_name]["code_template"]
                            merge_code = DISTRIBUTED_TASK_TEMPLATES[template_name].get("merge_code")
                        
                        # 提交分布式任务
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
                            
                            # 添加到历史记录
                            st.session_state.task_history.append({
                                "task_id": task_id,
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "status": "submitted",
                                "code_preview": f"{task_name} (分布式任务)",
                                "type": "分布式任务"
                            })
                            
                            # 显示任务详情
                            with st.expander("任务详情", expanded=True):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("任务ID", task_id)
                                with col2:
                                    st.metric("分片大小", chunk_size)
                                with col3:
                                    st.metric("最大并行分片", max_parallel_chunks)
                                
                                st.metric("数据项数量", len(task_data) if isinstance(task_data, (list, dict)) else 1)
                                
                                # 添加任务类型说明
                                task_type_desc = "自定义任务" if use_custom_task else template_name
                                st.info(f"任务类型: {task_type_desc}")
                        else:
                            st.error(f"❌ 提交失败: {result.get('error', '未知错误')}")
    
    else:  # 单节点任务
        st.info("💡 **提示**: 单节点任务也可以在本地IDE中运行，分布式任务更能发挥系统优势")
        st.subheader("单节点任务配置")
        
        # 简化的任务配置
        with st.expander("任务配置", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                timeout = st.number_input("超时时间(秒)", min_value=10, max_value=3600, value=300, step=10)
                cpu_request = st.slider("CPU需求(核心)", 0.1, 8.0, 1.0, 0.1)
            
            with col2:
                memory_request = st.number_input("内存需求(MB)", min_value=64, max_value=8192, value=512, step=64)
        
        # 代码编辑器
        with st.expander("Python代码", expanded=True):
            # 示例代码选择
            example_code = st.selectbox(
                "选择示例代码",
                ["自定义", "Hello World", "数学计算", "文件处理", "网络请求"],
                index=0
            )
            
            # 预定义示例代码
            examples = {
                "Hello World": 'print("Hello, World!")',
                "数学计算": '''
# 计算圆的面积
import math

radius = 5
area = math.pi * radius ** 2
print(f"半径为{radius}的圆的面积是: {area:.2f}")
''',
                "文件处理": '''
# 读取并处理文件
import os

# 创建一个示例文件
with open("example.txt", "w") as f:
    f.write("这是示例文本\\n第二行\\n第三行")
    
# 读取文件内容
with open("example.txt", "r") as f:
    content = f.read()
    lines = content.split("\\n")
    
print(f"文件共有{len(lines)}行")
print(f"第一行: {lines[0]}")
''',
                "网络请求": '''
# 发送HTTP请求
import requests
import json

try:
    # 获取IP地址信息
    response = requests.get("https://httpbin.org/ip", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"您的IP地址是: {data['origin']}")
    else:
        print(f"请求失败，状态码: {response.status_code}")
except Exception as e:
    print(f"请求出错: {e}")
'''
            }
            
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
        if st.button("🚀 提交单节点任务", use_container_width=True):
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
                            "code_preview": code[:100] + ("..." if len(code) > 100 else ""),
                            "type": "单节点任务"
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
    
    # 获取并显示所有结果 - 添加数据变化检测
    if st.button("🔄 刷新任务列表", key="refresh_tasks"):
        # 清除缓存，强制刷新
        cleanup_cache()
        st.rerun()
    
    # 任务类型选择
    task_monitor_type = st.radio(
        "监控任务类型",
        ["所有任务", "单节点任务", "分布式任务"],
        horizontal=True
    )
    
    success, results = get_all_results()
    if success and results.get("results"):
        results_list = results["results"]
        
        # 检查任务结果是否变化
        task_data = {
            'nodes': {
                'online': len(results.get("results", []))
            },
            'health_status': len(results.get("results", [])) > 0
        }
        task_data_changed = update_cache_and_check_change(task_data)
        
        if results_list:
            st.subheader("已完成的任务")
            
            # 创建结果表格
            results_data = []
            for result in results_list:
                # 获取任务类型
                task_type = "单节点任务"
                task_id = result.get("task_id", "N/A")
                
                # 检查是否是分布式任务
                if st.session_state.task_history:
                    for task in st.session_state.task_history:
                        if task.get("task_id") == str(task_id) and task.get("type") == "分布式任务":
                            task_type = "分布式任务"
                            break
                
                # 根据选择的类型过滤
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
                    task_type = "单节点任务"
                    
                    for result in results_list:
                        if str(result.get("task_id")) == str(selected_task_id):
                            full_result = result
                            break
                    
                    # 检查任务类型
                    if st.session_state.task_history:
                        for task in st.session_state.task_history:
                            if task.get("task_id") == str(selected_task_id):
                                task_type = task.get("type", "单节点任务")
                                break
                    
                    if full_result and full_result.get("result"):
                        st.subheader(f"任务 {selected_task_id} 的完整结果")
                        st.code(full_result["result"], language="text")
                        
                        # 如果是分布式任务，显示额外信息
                        if task_type == "分布式任务" and DISTRIBUTED_TASK_AVAILABLE:
                            st.subheader("分布式任务详情")
                            
                            # 获取分布式任务状态
                            status_success, status_info = get_distributed_task_status(selected_task_id)
                            if status_success:
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("总分片数", status_info.get("total_chunks", 0))
                                with col2:
                                    st.metric("已完成分片", status_info.get("completed_chunks", 0))
                                with col3:
                                    st.metric("失败分片", status_info.get("failed_chunks", 0))
                                
                                # 显示进度条
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
    
    # 任务历史（已提交但可能未完成）
    if st.session_state.task_history:
        st.subheader("任务历史记录")
        
        # 转换为DataFrame显示
        history_df = pd.DataFrame(st.session_state.task_history)
        
        # 根据选择的类型过滤
        if task_monitor_type != "所有任务":
            filtered_history = history_df[history_df["type"] == task_monitor_type]
        else:
            filtered_history = history_df
        
        if not filtered_history.empty:
            st.dataframe(
                filtered_history,
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
                        
                        # 显示任务详情 - 延迟加载大型结果
                        if task_info.get("result"):
                            with st.expander("执行结果", expanded=False):
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
        idle_nodes = nodes_info.get("total_idle", 0)
        
        # 检查节点信息是否变化 - 只关注在线节点数
        nodes_data = {
            "nodes": {
                "online": idle_nodes
            },
            "health_status": idle_nodes > 0
        }
        nodes_data_changed = update_cache_and_check_change(nodes_data)
        
        # 节点统计 - 只显示在线节点数
        st.metric("在线设备", idle_nodes)
        if idle_nodes > 0:
            st.success(f"✅ 有 {idle_nodes} 台设备在线，可以执行任务")
        else:
            st.warning("⚠️ 没有设备在线，请激活设备")
        
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
                    
                    # 显示设备ID（如果有）
                    device_id = node.get("device_id", "")
                    if device_id:
                        st.markdown(f"""
                        <div style="background-color: #f0f2f6; padding: 5px; border-radius: 3px; font-size: 0.8em; display: inline-block;">
                        📱 设备ID: {device_id}
                        </div>
                        """, unsafe_allow_html=True)
                    
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
        # 检查系统统计是否变化
        stats_data = {
            "nodes": {
                "online": stats.get("total_nodes", 0)
            },
            "health_status": stats.get("total_nodes", 0) > 0
        }
        stats_changed = update_cache_and_check_change(stats_data)
        
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
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("已处理任务", scheduler_stats.get("tasks_processed", 0))
            
            with col2:
                st.metric("失败任务", scheduler_stats.get("tasks_failed", 0))
        
        # 可视化图表
        st.subheader("性能图表")
        
        # 创建图表 - 去掉节点状态分布
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
                    go.Pie(labels=task_labels, values=task_values, hole=.3),
                    row=1, col=1
                )
        
        # 调度器统计柱状图 - 去掉节点相关统计
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

# 标签页5: 任务结果
with tab5:
    st.header("任务结果")
    
    # 任务结果展示区
    st.subheader("任务结果")
    if st.session_state.task_history:
        latest_task = st.session_state.task_history[-1]  # 获取最新任务
        latest_task_id = latest_task["task_id"]
        
        # 获取最新任务的状态
        with st.spinner(f"获取任务 {latest_task_id} 的状态..."):
            status_success, task_info = get_task_status(latest_task_id)
            
            if status_success and task_info:
                # 检查任务状态是否变化
                task_status_data = {
                    "nodes": {
                        "online": 1 if task_info.get("status") == "completed" else 0
                    },
                    "health_status": task_info.get("status") == "completed"
                }
                task_status_changed = update_cache_and_check_change(task_status_data)
                
                status = task_info.get("status", "unknown")
                if status == "completed":
                    st.success(f"✅ 任务 {latest_task_id} 已完成")
                    if task_info.get("result"):
                        st.code(task_info["result"], language="text")
                    else:
                        st.info("任务已完成但暂无结果")
                elif status in ["pending", "assigned", "running"]:
                    st.info(f"⏳ 任务 {latest_task_id} 状态: {status}")
                    if status == "running":
                        st.progress(70)  # 假设进度为70%
                elif status == "failed":
                    st.error(f"❌ 任务 {latest_task_id} 执行失败")
                    if task_info.get("result"):
                        st.code(task_info["result"], language="text")
                else:
                    st.warning(f"⚠️ 任务 {latest_task_id} 状态: {status}")
            else:
                st.warning(f"⚠️ 无法获取任务 {latest_task_id} 的状态")
    else:
        st.info("暂无任务记录，请先提交任务")

# 页脚
st.divider()
st.caption("闲置计算加速器 v2.0.0 | 开源免费项目 | 适配新版调度中心API")