"""
scheduler/simple_server.py
Enhanced Task Scheduler with Node Management, User Management and Fair Scheduling
"""

import time
import uuid
import threading
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Body
from pydantic import BaseModel
from collections import defaultdict

# 导入安全沙箱
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
from sandbox import CodeSandbox
from user_management.local_authorization import authorization_manager

# ==================== 用户管理数据模型 ====================
class User(BaseModel):
    """用户模型"""
    user_id: str
    username: str
    email: str
    created_at: str
    is_active: bool = True

class UserQuota(BaseModel):
    """用户资源配额"""
    user_id: str
    daily_tasks_limit: int = 100
    concurrent_tasks_limit: int = 5
    cpu_quota: float = 10.0
    memory_quota: int = 4096
    daily_usage: int = 0
    current_tasks: int = 0

# ==================== 任务数据模型定义 ====================
class TaskSubmission(BaseModel):
    """任务提交模型"""
    code: str
    timeout: Optional[int] = 300
    resources: Optional[Dict[str, Any]] = {"cpu": 1.0, "memory": 512}
    user_id: Optional[str] = None  # 新增用户ID参数

class TaskResult(BaseModel):
    """任务结果模型"""
    task_id: int
    result: str
    node_id: Optional[str] = None

class TaskInfo(BaseModel):
    """任务信息模型 - 增强版"""
    task_id: int
    code: str
    status: str  # pending, assigned, running, completed, failed, deleted
    created_at: float
    assigned_at: Optional[float] = None
    assigned_node: Optional[str] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    required_resources: Dict[str, Any] = {"cpu": 1.0, "memory": 512}
    user_id: Optional[str] = None  # 新增：关联用户ID

class NodeRegistration(BaseModel):
    """节点注册模型"""
    node_id: str
    capacity: Dict[str, Any]  # {"cpu": 4.0, "memory": 8192, "disk": 100000}
    tags: Optional[Dict[str, Any]] = {}  # 标签：{"gpu": true, "os": "windows"}

class NodeHeartbeat(BaseModel):
    """节点心跳模型"""
    node_id: str
    current_load: Dict[str, Any]  # {"cpu_usage": 0.3, "memory_usage": 2048}
    is_idle: bool
    available_resources: Dict[str, Any]  # 计算后的可用资源

# ==================== 用户管理类 ====================
class SimpleAuthManager:
    """简化版用户认证管理器 - 开源版本"""
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.user_quotas: Dict[str, UserQuota] = {}
        self.sessions: Dict[str, str] = {}  # session_id -> user_id
        
    def register_user(self, username: str, email: str) -> Dict[str, Any]:
        """注册新用户 - 开源版本简化注册"""
        # 检查用户名和邮箱是否已存在
        if any(u.username == username for u in self.users.values()):
            return {"success": False, "error": "用户名已存在"}
            
        if any(u.email == email for u in self.users.values()):
            return {"success": False, "error": "邮箱已存在"}
            
        # 创建用户
        user = User(
            user_id=str(uuid.uuid4()),
            username=username,
            email=email,
            created_at=datetime.now().isoformat()
        )
        
        # 创建无限制配额
        quota = UserQuota(user_id=user.user_id)
        
        self.users[user.user_id] = user
        self.user_quotas[user.user_id] = quota
        
        return {
            "success": True, 
            "user_id": user.user_id,
            "user": user.dict(),
            "quota": quota.dict()
        }
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        return self.users.get(user_id)
    
    def get_quota_by_user_id(self, user_id: str) -> Optional[UserQuota]:
        """获取用户配额"""
        return self.user_quotas.get(user_id)
    
    def create_session(self, user_id: str) -> str:
        """创建会话"""
        import secrets
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = user_id
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[str]:
        """验证会话"""
        return self.sessions.get(session_id)

class SimpleQuotaManager:
    """简化版配额管理器"""
    def __init__(self):
        self.quotas: Dict[str, UserQuota] = {}
        self.last_reset_date = datetime.now().date()
        
    def check_quota(self, user_id: str) -> Dict[str, Any]:
        """检查用户配额"""
        quota = self.quotas.get(user_id)
        if not quota:
            return {"allowed": False, "error": "用户不存在"}
            
        # 每日重置检查
        self._reset_daily_usage_if_needed(quota)
        
        if quota.daily_usage >= quota.daily_tasks_limit:
            return {"allowed": False, "error": "每日任务配额已用完"}
            
        if quota.current_tasks >= quota.concurrent_tasks_limit:
            return {"allowed": False, "error": "并发任务数已达上限"}
            
        return {"allowed": True, "quota": quota.dict()}
    
    def consume_quota(self, user_id: str) -> bool:
        """消耗配额"""
        quota = self.quotas.get(user_id)
        if not quota:
            return False
            
        if quota.daily_usage >= quota.daily_tasks_limit:
            return False
            
        if quota.current_tasks >= quota.concurrent_tasks_limit:
            return False
            
        quota.daily_usage += 1
        quota.current_tasks += 1
        return True
    
    def release_quota(self, user_id: str):
        """释放配额（任务完成时调用）"""
        quota = self.quotas.get(user_id)
        if quota and quota.current_tasks > 0:
            quota.current_tasks -= 1
    
    def _reset_daily_usage_if_needed(self, quota: UserQuota):
        """如果需要则重置每日使用量"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            quota.daily_usage = 0
            self.last_reset_date = today

# ==================== 内存存储类 - 增强版 ====================
class EnhancedMemoryStorage:
    """线程安全的内存存储，支持节点管理和公平调度"""
    
    def __init__(self):
        # 任务存储
        self.tasks: Dict[int, TaskInfo] = {}
        self.task_id_counter = 1
        
        # 节点管理
        self.nodes: Dict[str, Dict] = {}  # node_id -> 节点信息
        self.node_heartbeats: Dict[str, float] = {}  # node_id -> 最后心跳时间
        
        # 调度队列
        self.pending_tasks: List[int] = []  # 待调度任务ID列表
        self.assigned_tasks: Dict[str, List[int]] = defaultdict(list)  # node_id -> 任务ID列表
        
        self.server_id = str(uuid.uuid4())[:8]
        self.lock = threading.RLock()
        
        # 调度器统计
        self.scheduler_stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "nodes_registered": 0,
            "nodes_dropped": 0,
            "last_schedule_time": time.time()
        }
    def stop_node(self, node_id: str) -> Dict[str, Any]:

        with self.lock:
            if node_id not in self.nodes:
                return {"success": False, "error": "节点不存在"}
        
        # 重新分配该节点的任务
            if node_id in self.assigned_tasks:
                for task_id in self.assigned_tasks[node_id]:
                    task = self.tasks.get(task_id)
                    if task and task.status == "assigned":
                        task.status = "pending"
                        task.assigned_node = None
                        task.assigned_at = None
                        self.pending_tasks.append(task_id)
            
                del self.assigned_tasks[node_id]
        
        # 移除节点
            del self.nodes[node_id]
            if node_id in self.node_heartbeats:
                del self.node_heartbeats[node_id]
        
            self.scheduler_stats["nodes_dropped"] += 1
        
            return {"success": True, "message": f"节点 {node_id} 已停止"}
    # ========== 任务管理方法 ==========
    def add_task(self, code: str, timeout: int = 300, resources: Optional[Dict] = None, user_id: Optional[str] = None) -> int:
        """添加新任务到调度队列"""
        with self.lock:
            task_id = self.task_id_counter
            self.task_id_counter += 1
            
            task = TaskInfo(
                task_id=task_id,
                code=code,
                status="pending",
                created_at=time.time(),
                required_resources=resources or {"cpu": 1.0, "memory": 512},
                user_id=user_id  # 关联用户ID
            )
            
            self.tasks[task_id] = task
            self.pending_tasks.append(task_id)
            
            # 尝试立即调度
            self._schedule_tasks()
            
            return task_id
    
    def delete_task(self, task_id: int) -> Dict[str, Any]:
        """删除任务"""
        with self.lock:
            if task_id not in self.tasks:
                return {"success": False, "error": "任务不存在"}
            
            task = self.tasks[task_id]
            
            # 只能删除pending或assigned状态的任务
            if task.status not in ["pending", "assigned"]:
                return {"success": False, "error": f"只能删除pending或assigned状态的任务，当前状态: {task.status}"}
            
            # 从相应队列中移除
            if task.status == "pending" and task_id in self.pending_tasks:
                self.pending_tasks.remove(task_id)
            elif task.status == "assigned" and task.assigned_node:
                if task_id in self.assigned_tasks[task.assigned_node]:
                    self.assigned_tasks[task.assigned_node].remove(task_id)
            
            # 标记为已删除
            task.status = "deleted"
            
            return {"success": True, "message": f"任务 {task_id} 已删除"}
    
    def get_pending_task(self) -> Optional[TaskInfo]:
        """获取待处理任务 - 传统FIFO方法（保持兼容）"""
        with self.lock:
            for task_id in list(self.pending_tasks):
                task = self.tasks.get(task_id)
                if task and task.status == "pending":
                    task.status = "running"
                    self.pending_tasks.remove(task_id)
                    return task
            return None
    
    def get_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        """
        为特定节点获取最适合的任务
        实现公平调度算法
        """
        with self.lock:
            # 检查节点是否存在且在线
            node_info = self.nodes.get(node_id)
            if not node_info or not self._is_node_online(node_id):
                return None
            
            # 获取节点的可用资源
            available_resources = node_info.get("available_resources", {})
            
            # 寻找最适合的任务
            best_task = None
            best_score = -1
            
            for task_id in list(self.pending_tasks):
                task = self.tasks.get(task_id)
                if not task or task.status != "pending":
                    continue
                
                # 检查资源是否满足
                if self._can_node_handle_task(node_info, task):
                    # 计算匹配分数
                    score = self._calculate_match_score(node_info, task)
                    
                    if score > best_score:
                        best_score = score
                        best_task = task
            
            if best_task:
                # 分配任务给节点
                best_task.status = "assigned"
                best_task.assigned_node = node_id
                best_task.assigned_at = time.time()
                self.pending_tasks.remove(best_task.task_id)
                self.assigned_tasks[node_id].append(best_task.task_id)
                
                # 更新节点负载（估算）
                if "current_load" not in node_info:
                    node_info["current_load"] = {"cpu_usage": 0.0, "memory_usage": 0}
                
                # 增加负载估算
                node_info["current_load"]["cpu_usage"] += best_task.required_resources.get("cpu", 1.0)
                node_info["current_load"]["memory_usage"] += best_task.required_resources.get("memory", 512)
                
                self.scheduler_stats["tasks_processed"] += 1
                self.scheduler_stats["last_schedule_time"] = time.time()
            
            return best_task
    
    def complete_task(self, task_id: int, result: str, node_id: Optional[str] = None) -> bool:
        """完成任务并释放节点资源"""
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            if task.status not in ["pending", "assigned", "running"]:
                return False
            
            # 更新任务状态
            task.status = "completed"
            task.completed_at = time.time()
            task.result = result
            
            # 如果知道是哪个节点完成的，释放资源
            actual_node_id = node_id or task.assigned_node
            if actual_node_id and actual_node_id in self.nodes:
                # 从节点的已分配任务列表中移除
                if task_id in self.assigned_tasks[actual_node_id]:
                    self.assigned_tasks[actual_node_id].remove(task_id)
                
                # 减少节点负载估算
                node_info = self.nodes[actual_node_id]
                if "current_load" in node_info:
                    node_info["current_load"]["cpu_usage"] = max(0, 
                        node_info["current_load"]["cpu_usage"] - task.required_resources.get("cpu", 1.0))
                    node_info["current_load"]["memory_usage"] = max(0,
                        node_info["current_load"]["memory_usage"] - task.required_resources.get("memory", 512))
            
            return True
    
    def get_task_status(self, task_id: int) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "task_id": task.task_id,
            "status": task.status,
            "result": task.result,
            "created_at": task.created_at,
            "assigned_at": task.assigned_at,
            "assigned_node": task.assigned_node,
            "completed_at": task.completed_at,
            "required_resources": task.required_resources,
            "user_id": task.user_id  # 新增用户ID
        }
    
    # ========== 节点管理方法 ==========
    def register_node(self, registration: NodeRegistration) -> bool:
        """注册新节点"""
        with self.lock:
            node_id = registration.node_id
            
            # 如果节点已存在，更新信息
            if node_id in self.nodes:
                self.nodes[node_id].update({
                    "capacity": registration.capacity,
                    "tags": registration.tags,
                    "registered_at": time.time(),
                    "last_heartbeat": time.time()
                })
            else:
                # 新节点
                self.nodes[node_id] = {
                    "capacity": registration.capacity,
                    "tags": registration.tags,
                    "registered_at": time.time(),
                    "last_heartbeat": time.time(),
                    "current_load": {"cpu_usage": 0.0, "memory_usage": 0},
                    "available_resources": registration.capacity.copy()
                }
                self.scheduler_stats["nodes_registered"] += 1
            
            self.node_heartbeats[node_id] = time.time()
            return True
    
    def update_node_heartbeat(self, heartbeat: NodeHeartbeat) -> bool:
        """更新节点心跳"""
        with self.lock:
            node_id = heartbeat.node_id
            
            if node_id not in self.nodes:
                return False
            
            # 更新节点状态
            self.nodes[node_id].update({
                "last_heartbeat": time.time(),
                "current_load": heartbeat.current_load,
                "is_idle": heartbeat.is_idle,
                "available_resources": heartbeat.available_resources
            })
            
            self.node_heartbeats[node_id] = time.time()
            return True
    
    def get_available_nodes(self) -> List[Dict[str, Any]]:
        """获取所有在线的可用节点"""
        with self.lock:
            available_nodes = []
            current_time = time.time()
            
            for node_id, node_info in self.nodes.items():
                # 检查节点是否在线（使用统一的在线判断逻辑）
                if self._is_node_online(node_id):
                    available_nodes.append({
                        "node_id": node_id,
                        **node_info
                    })
            
            return available_nodes
    
    def cleanup_dead_nodes(self, timeout_seconds: int = 60):
        """清理超时未心跳的节点"""
        with self.lock:
            current_time = time.time()
            dead_nodes = []
            
            for node_id, last_heartbeat in self.node_heartbeats.items():
                if current_time - last_heartbeat > timeout_seconds:
                    dead_nodes.append(node_id)
            
            for node_id in dead_nodes:
                # 重新分配该节点的任务
                if node_id in self.assigned_tasks:
                    for task_id in self.assigned_tasks[node_id]:
                        task = self.tasks.get(task_id)
                        if task and task.status == "assigned":
                            task.status = "pending"
                            task.assigned_node = None
                            task.assigned_at = None
                            self.pending_tasks.append(task_id)
                    
                    del self.assigned_tasks[node_id]
                
                # 移除节点
                if node_id in self.nodes:
                    del self.nodes[node_id]
                if node_id in self.node_heartbeats:
                    del self.node_heartbeats[node_id]
                
                self.scheduler_stats["nodes_dropped"] += 1
            
            return len(dead_nodes)
    
    # ========== 调度算法辅助方法 ==========
    def _schedule_tasks(self):
        """尝试调度待处理的任务"""
        with self.lock:
            if not self.pending_tasks:
                return
            
            available_nodes = self.get_available_nodes()
            if not available_nodes:
                return
            
            # 为每个可用节点尝试分配一个任务
            for node_info in available_nodes:
                if self.pending_tasks:  # 检查是否还有待处理任务
                    self.get_task_for_node(node_info["node_id"])
    
    def _is_node_online(self, node_id: str) -> bool:
        """检查节点是否在线"""
        current_time = time.time()
        last_heartbeat = self.node_heartbeats.get(node_id, 0)
        
        # 对于通过API激活的本地节点，可以给予稍微长一点的超时时间
        # 因为它们可能不会像常规节点那样频繁发送心跳
        node_info = self.nodes.get(node_id, {})
        tags = node_info.get("tags", {})
        
        if tags.get("auto_activated"):
            # API激活的节点允许最多60秒无心跳
            return current_time - last_heartbeat <= 60
        else:
            # 常规节点30秒超时
            return current_time - last_heartbeat <= 30
    
    def _can_node_handle_task(self, node_info: Dict, task: TaskInfo) -> bool:
        """检查节点是否能处理任务"""
        # 获取可用资源
        available = node_info.get("available_resources", {})
        required = task.required_resources
        
        # 检查关键资源
        if "cpu" in required and "cpu" in available:
            if required["cpu"] > available.get("cpu", 0):
                return False
        
        if "memory" in required and "memory" in available:
            if required["memory"] > available.get("memory", 0):
                return False
        
        return True
    
    def _calculate_match_score(self, node_info: Dict, task: TaskInfo) -> float:
        """
        计算节点与任务的匹配分数
        分数越高，匹配度越好
        """
        score = 0.0
        available = node_info.get("available_resources", {})
        required = task.required_resources
        
        # 1. 资源匹配度（越高越好）
        if "cpu" in required and "cpu" in available:
            cpu_ratio = min(1.0, available.get("cpu", 0) / max(1.0, required["cpu"]))
            score += cpu_ratio * 0.4  # CPU权重40%
        
        if "memory" in required and "memory" in available:
            mem_ratio = min(1.0, available.get("memory", 0) / max(1, required["memory"]))
            score += mem_ratio * 0.3  # 内存权重30%
        
        # 2. 节点空闲状态（空闲更好）
        if node_info.get("is_idle", False):
            score += 0.2  # 空闲状态权重20%
        
        # 3. 节点负载（负载越低越好）
        current_load = node_info.get("current_load", {})
        cpu_load = current_load.get("cpu_usage", 0) / max(1.0, node_info.get("capacity", {}).get("cpu", 1))
        score += (1.0 - min(1.0, cpu_load)) * 0.1  # 负载权重10%
        
        return score
    
    # ========== 统计方法 ==========
    def get_all_results(self) -> List[Dict[str, Any]]:
        """获取所有结果"""
        with self.lock:
            return [
                {
                    "task_id": task.task_id,
                    "result": task.result,
                    "completed_at": task.completed_at,
                    "assigned_node": task.assigned_node,
                    "user_id": task.user_id  # 新增用户ID
                }
                for task in self.tasks.values()
                if task.status == "completed"
            ]
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        with self.lock:
            total_tasks = len(self.tasks)
            completed_tasks = sum(1 for t in self.tasks.values() if t.status == "completed")
            pending_tasks = len(self.pending_tasks)
            assigned_tasks = sum(len(tasks) for tasks in self.assigned_tasks.values())
            deleted_tasks = sum(1 for t in self.tasks.values() if t.status == "deleted")
            
            # 计算平均完成时间
            completed_times = []
            for task in self.tasks.values():
                if task.status == "completed" and task.completed_at and task.assigned_at:
                    completed_times.append(task.completed_at - task.assigned_at)
            
            avg_time = sum(completed_times) / len(completed_times) if completed_times else 0
            
            # 节点统计
            online_nodes = sum(1 for node_id in self.nodes.keys() 
                             if self._is_node_online(node_id))
            total_nodes = len(self.nodes)
            
            return {
                "time_period": "all_time",
                "tasks": {
                    "total": total_tasks,
                    "completed": completed_tasks,
                    "pending": pending_tasks,
                    "assigned": assigned_tasks,
                    "deleted": deleted_tasks,  # 新增删除任务统计
                    "failed": total_tasks - completed_tasks - pending_tasks - assigned_tasks - deleted_tasks,
                    "avg_completion_time": round(avg_time, 2)
                },
                "nodes": {
                    "total": total_nodes,
                    "online": online_nodes,
                    "offline": total_nodes - online_nodes,
                    "idle": sum(1 for n in self.nodes.values() if n.get("is_idle", False))
                },
                "scheduler": self.scheduler_stats
            }

# ==================== FastAPI 应用 ====================
app = FastAPI(
    title="Enhanced Idle Computing Scheduler",
    description="Task scheduler with node management, user management and fair scheduling",
    version="2.1.0"  # 版本号更新
)

# 初始化存储和用户管理
storage = EnhancedMemoryStorage()
auth_manager = SimpleAuthManager()
quota_manager = SimpleQuotaManager()
sandbox = CodeSandbox()  # 安全沙箱实例

# ==================== 后台任务 ====================
def cleanup_old_nodes():
    """定期清理失效的节点"""
    try:
        cleaned = storage.cleanup_dead_nodes(timeout_seconds=60)
        if cleaned > 0:
            print(f"[Cleanup] Removed {cleaned} dead nodes")
    except Exception as e:
        print(f"[Cleanup Error] {e}")

@app.on_event("startup")
def startup_event():
    """启动时初始化"""
    print("=" * 60)
    print(f"Enhanced Task Scheduler v2.1.0")
    print(f"Server ID: {storage.server_id}")
    print(f"User Management: Enabled")
    print(f"Task Deletion: Enabled")
    print(f"Starting background cleanup task...")
    print("=" * 60)

# ==================== 用户管理API端点 ====================
@app.post("/api/users/register")
async def register_user(username: str, email: str, agree_folder_usage: bool, user_confirmed_authorization: bool = False):
    """用户注册接口 - 必须同意文件夹使用协议并确认授权"""
    
    # 强制要求用户同意文件夹使用协议
    if not agree_folder_usage:
        raise HTTPException(status_code=400, detail="【本地操作授权】必须同意文件夹使用协议才能使用本系统")
    
    # 强制要求用户确认授权（合规要求）
    if not user_confirmed_authorization:
        raise HTTPException(status_code=400, detail="【本地操作授权】必须确认本地操作授权才能使用本系统")
    
    # 先进行用户注册
    result = auth_manager.register_user(username, email, agree_folder_usage)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    user_id = result["user_id"]
    
    # 构建文件夹路径信息
    target_paths = {
        "user_data": f"node_data/user_data/{user_id}",
        "temp_data": f"node_data/temp_data/{user_id}"
    }
    
    # 请求文件夹创建授权
    authorization_request = authorization_manager.request_folder_creation_authorization(
        user_id=user_id,
        username=username,
        target_paths=target_paths
    )
    
    # 初始化配额
    quota_manager.quotas[user_id] = UserQuota(user_id=user_id)
    
    # 创建会话
    session_id = auth_manager.create_session(user_id)
    
    return {
        "success": True,
        "session_id": session_id,
        "user": result["user"],
        "quota": result["quota"],
        "folder_agreement": result["folder_agreement"],
        "authorization_required": True,
        "authorization_request": authorization_request,
        "message": "注册成功！请确认本地文件夹创建授权。"
    }


@app.post("/api/users/confirm-authorization")
async def confirm_authorization(
    x_session_id: str = Header(...),
    operation_details: Dict[str, Any] = Body(...),
    user_agreed: bool = Body(...)
):
    """确认本地操作授权"""
    user_id = auth_manager.validate_session(x_session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="未授权")
    
    # 确认授权
    authorization_result = authorization_manager.confirm_authorization(
        user_id=user_id,
        operation_details=operation_details,
        user_agreed=user_agreed
    )
    
    if not authorization_result["authorized"]:
        return {
            "success": False,
            "message": authorization_result["message"],
            "authorization_log": authorization_result["log_entry"]
        }
    
    return {
        "success": True,
        "message": authorization_result["message"],
        "authorization_log": authorization_result["log_entry"],
        "disclaimer": "【本地文件操作免责声明】所有本地操作均由您主动授权发起，操作结果由您自行负责。"
    }

@app.get("/api/users/quota")
async def get_user_quota(x_session_id: str = Header(...)):
    """获取用户配额"""
    user_id = auth_manager.validate_session(x_session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="未授权")
    
    quota_result = quota_manager.check_quota(user_id)
    if not quota_result["allowed"]:
        raise HTTPException(status_code=403, detail=quota_result["error"])
    
    return quota_result

# ==================== 任务删除API端点 ====================
@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务API"""
    result = storage.delete_task(task_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

# ==================== 传统端点（修改） ====================
@app.get("/")
async def root() -> Dict[str, Any]:
    """根端点 - 健康检查"""
    return {
        "service": "Enhanced Idle Computing Scheduler",
        "status": "running",
        "version": "2.1.0",
        "server_id": storage.server_id,
        "task_count": len(storage.tasks),
        "pending_tasks": len(storage.pending_tasks),
        "online_nodes": len([n for n in storage.nodes.keys() 
                           if storage._is_node_online(n)]),
        "user_management": "enabled",  # 新增用户管理状态
        "task_deletion": "enabled"     # 新增任务删除状态
    }

@app.post("/submit")
async def submit_task(submission: TaskSubmission, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """提交任务（开源版本无限制 + 安全沙箱检查）"""
    if not submission.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")
    
    if len(submission.code) > 10000:
        raise HTTPException(status_code=400, detail="Code too long (max 10000 characters)")
    
    # 代码安全检查
    safety_check = sandbox.check_code_safety(submission.code)
    if not safety_check['safe']:
        raise HTTPException(status_code=400, detail=f"代码安全检查失败: {safety_check['error']}")
    
    task_id = storage.add_task(submission.code, submission.timeout, submission.resources, submission.user_id)
    
    # 触发后台清理
    background_tasks.add_task(cleanup_old_nodes)
    
    return {
        "task_id": task_id,
        "status": "submitted",
        "server_id": storage.server_id,
        "message": f"Task {task_id} has been queued",
        "safety_check": "通过"
    }

@app.get("/get_task")
async def get_task(node_id: Optional[str] = None) -> Dict[str, Any]:
    """获取任务（增强版：支持节点感知）"""
    if node_id:
        # 节点感知的任务获取（新功能）
        task = storage.get_task_for_node(node_id)
    else:
        # 传统FIFO获取（保持兼容）
        task = storage.get_pending_task()
    
    if task is None:
        return {
            "task_id": None,
            "code": None,
            "status": "no_tasks",
            "message": "No pending tasks available"
        }
    
    return {
        "task_id": task.task_id,
        "code": task.code,
        "status": "assigned" if node_id else "assigned",
        "created_at": task.created_at,
        "assigned_node": task.assigned_node,
        "message": f"Task {task.task_id} assigned for execution"
    }

@app.post("/submit_result")
async def submit_result(result: TaskResult) -> Dict[str, Any]:
    """提交结果（增强版：支持节点ID和配额释放）"""
    if result.task_id not in storage.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 完成任务
    success = storage.complete_task(result.task_id, result.result, result.node_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to complete task")
    
    # 释放配额
    task = storage.tasks[result.task_id]
    if task.user_id:
        quota_manager.release_quota(task.user_id)
    
    return {
        "success": True,
        "task_id": result.task_id,
        "message": f"Task {result.task_id} completed successfully"
    }
    if result.task_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    success = storage.complete_task(result.task_id, result.result, result.node_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Task {result.task_id} not found or not runnable")
    
    return {
        "status": "ok",
        "task_id": result.task_id,
        "message": f"Result for task {result.task_id} recorded"
    }

@app.get("/status/{task_id}")
async def get_status(task_id: int) -> Dict[str, Any]:
    """获取任务状态（增强版：包含更多信息）"""
    if task_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    status = storage.get_task_status(task_id)
    
    if status is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return status

@app.get("/results")
async def get_results() -> Dict[str, Any]:
    """获取所有结果（增强版：包含节点信息）"""
    results = storage.get_all_results()
    return {
        "count": len(results),
        "results": results,
        "server_id": storage.server_id
    }

# ==================== 新增端点（节点管理和增强功能） ====================
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查端点（增强版）"""
    # 计算节点统计信息
    total_nodes = len(storage.nodes)
    online_nodes = sum(1 for node_id in storage.nodes.keys() 
                      if storage._is_node_online(node_id))
    
    node_status = "healthy" if total_nodes > 0 else "no_nodes"
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "server_id": storage.server_id,
        "components": {
            "task_queue": "healthy",
            "memory_storage": "healthy",
            "node_manager": node_status,
            "scheduler": "healthy"
        },
        "nodes": {
            "online": online_nodes,
            "total": total_nodes
        }
    }

@app.post("/api/nodes/register")
async def register_node(registration: NodeRegistration) -> Dict[str, Any]:
    """注册新节点"""
    success = storage.register_node(registration)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to register node")
    
    return {
        "status": "registered",
        "node_id": registration.node_id,
        "message": f"Node {registration.node_id} registered successfully",
        "server_time": time.time()
    }

@app.post("/api/nodes/{node_id}/heartbeat")
async def update_heartbeat(node_id: str, heartbeat: NodeHeartbeat) -> Dict[str, Any]:
    """更新节点心跳"""
    if heartbeat.node_id != node_id:
        raise HTTPException(status_code=400, detail="Node ID mismatch")
    
    success = storage.update_node_heartbeat(heartbeat)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    # 触发任务调度（如果节点空闲且有任务）
    if heartbeat.is_idle and storage.pending_tasks:
        # 在后台触发调度
        pass
    
    return {
        "status": "updated",
        "node_id": node_id,
        "timestamp": time.time(),
        "message": f"Heartbeat for node {node_id} recorded"
    }

@app.get("/api/nodes")
async def list_nodes(online_only: bool = True) -> Dict[str, Any]:
    """列出所有节点"""
    if online_only:
        nodes = storage.get_available_nodes()
        # 为在线节点添加在线状态标记
        enhanced_nodes = []
        for node in nodes:
            node_copy = node.copy()
            node_copy["is_online"] = True
            enhanced_nodes.append(node_copy)
        nodes = enhanced_nodes
    else:
        # 返回所有节点，为每个节点添加在线状态
        all_nodes = list(storage.nodes.values())
        enhanced_nodes = []
        for node in all_nodes:
            node_copy = node.copy()
            node_id = node.get("node_id")
            if node_id:
                node_copy["is_online"] = storage._is_node_online(node_id)
            else:
                node_copy["is_online"] = False
            enhanced_nodes.append(node_copy)
        nodes = enhanced_nodes
    
    return {
        "count": len(nodes),
        "nodes": nodes,
        "online_only": online_only,
        "timestamp": time.time()
    }

@app.get("/api/nodes/{node_id}/tasks")
async def get_node_tasks(node_id: str) -> Dict[str, Any]:
    """获取节点分配的任务"""
    # 注意：这个实现依赖于内部数据结构，需要storage暴露相应方法
    # 这里简化实现
    return {
        "node_id": node_id,
        "assigned_tasks": [],  # 实际应从storage获取
        "timestamp": time.time()
    }

@app.post("/api/nodes/activate-local")
async def activate_local_node(config: dict = Body(...)) -> Dict[str, Any]:
    """激活本地节点 - 为当前用户创建一个本地计算节点"""
    try:
        # 生成唯一的本地节点ID
        import uuid
        node_id = f"local-{uuid.uuid4().hex[:8]}-{int(time.time())}"
        
        # 使用传入的配置或者默认配置
        cpu_limit = config.get("cpu_limit", 1.0)
        memory_limit = config.get("memory_limit", 512)
        storage_limit = config.get("storage_limit", 1024)
        
        # 创建节点容量信息
        capacity = {
            "cpu": cpu_limit,
            "memory": memory_limit,
            "disk": storage_limit
        }
        
        # 注册节点
        registration = NodeRegistration(
            node_id=node_id,
            capacity=capacity,
            tags={
                "type": "local",
                "platform": "local-web-activated",
                "owner": "user-web",
                "auto_activated": True  # 标记为自动激活的节点
            }
        )
        
        success = storage.register_node(registration)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to register local node")
        
        # 立即发送心跳以确保节点在线（模拟节点行为）
        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 0.0, "memory_usage": 0},
            is_idle=True,  # 标记为空闲状态，便于接收任务
            available_resources=capacity  # 设置可用资源
        )
        
        storage.update_node_heartbeat(heartbeat)
        
        # 立即尝试调度任务，如果有待处理的任务
        storage._schedule_tasks()
        
        # 确保节点立即变为在线状态
        # 由于刚刚更新了心跳，节点应该立即在线
        
        return {
            "success": True,
            "node_id": node_id,
            "message": "Local node activated successfully",
            "capacity": capacity,
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate local node: {str(e)}")

@app.get("/stats")
async def get_system_stats() -> Dict[str, Any]:
    """系统统计端点（增强版）"""
    return storage.get_system_stats()

@app.post("/api/nodes/{node_id}/stop")
async def stop_node_api(node_id: str) -> Dict[str, Any]:
    """停止指定节点"""
    result = storage.stop_node(node_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result



# ==================== CORS 支持 ====================
try:
    from fastapi.middleware.cors import CORSMiddleware
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 警告：仅用于开发
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600,
    )
    print("[Enhanced Scheduler] CORS middleware enabled")
except ImportError:
    print("[Enhanced Scheduler] CORS middleware not available")
    pass

# ==================== 启动代码 ====================
if __name__ == "__main__":
    import uvicorn
    import signal
    import sys
    import os
    import time
    
    print(f"[Enhanced Scheduler] Starting server on http://localhost:8000")
    print(f"[Enhanced Scheduler] Server ID: {storage.server_id}")
    print(f"[Enhanced Scheduler] Features: Node Management, Fair Scheduling, Health Checks")
    
    # 信号处理：优雅退出
    def signal_handler(signum, frame):
        print("\n[Enhanced Scheduler] Received shutdown signal")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 修复：确保服务器持续运行
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True,
            timeout_keep_alive=5
        )
    except KeyboardInterrupt:
        print("\n[Enhanced Scheduler] Server stopped by user")
    except Exception as e:
        print(f"[Enhanced Scheduler] Error: {e}")
        print("[Enhanced Scheduler] Server will restart in 5 seconds...")
        time.sleep(5)
        # 重新启动服务器
        os.execv(sys.executable, ['python'] + sys.argv)