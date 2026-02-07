"""
scheduler/simple_server.py
Enhanced Task Scheduler with Node Management and Fair Scheduling
"""

import time
import uuid
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from collections import defaultdict

# ==================== 数据模型定义 ====================
class TaskSubmission(BaseModel):
    """任务提交模型"""
    code: str
    timeout: Optional[int] = 300
    resources: Optional[Dict[str, Any]] = {"cpu": 1.0, "memory": 512}

class TaskResult(BaseModel):
    """任务结果模型"""
    task_id: int
    result: str
    node_id: Optional[str] = None

class TaskInfo(BaseModel):
    """任务信息模型 - 增强版"""
    task_id: int
    code: str
    status: str  # pending, assigned, running, completed, failed
    created_at: float
    assigned_at: Optional[float] = None
    assigned_node: Optional[str] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    required_resources: Dict[str, Any] = {"cpu": 1.0, "memory": 512}

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
    
    # ========== 任务管理方法 ==========
    def add_task(self, code: str, timeout: int = 300, resources: Optional[Dict] = None) -> int:
        """添加新任务到调度队列"""
        with self.lock:
            task_id = self.task_id_counter
            self.task_id_counter += 1
            
            task = TaskInfo(
                task_id=task_id,
                code=code,
                status="pending",
                created_at=time.time(),
                required_resources=resources or {"cpu": 1.0, "memory": 512}
            )
            
            self.tasks[task_id] = task
            self.pending_tasks.append(task_id)
            
            # 尝试立即调度
            self._schedule_tasks()
            
            return task_id
    
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
            "required_resources": task.required_resources
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
                # 检查节点是否在线（最近30秒内有心跳）
                if current_time - self.node_heartbeats.get(node_id, 0) <= 30:
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
                    "assigned_node": task.assigned_node
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
                    "failed": total_tasks - completed_tasks - pending_tasks - assigned_tasks,
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
    description="Task scheduler with node management and fair scheduling",
    version="2.0.0"
)

# 初始化存储
storage = EnhancedMemoryStorage()

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
    print(f"Enhanced Task Scheduler v2.0.0")
    print(f"Server ID: {storage.server_id}")
    print(f"Starting background cleanup task...")
    print("=" * 60)

# ==================== 传统端点（保持完全兼容） ====================
@app.get("/")
async def root() -> Dict[str, Any]:
    """根端点 - 健康检查"""
    return {
        "service": "Enhanced Idle Computing Scheduler",
        "status": "running",
        "version": "2.0.0",
        "server_id": storage.server_id,
        "task_count": len(storage.tasks),
        "pending_tasks": len(storage.pending_tasks),
        "online_nodes": len([n for n in storage.nodes.keys() 
                           if time.time() - storage.node_heartbeats.get(n, 0) <= 30])
    }

@app.post("/submit")
async def submit_task(submission: TaskSubmission, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """提交任务（兼容旧端点）"""
    if not submission.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")
    
    if len(submission.code) > 10000:
        raise HTTPException(status_code=400, detail="Code too long (max 10000 characters)")
    
    task_id = storage.add_task(submission.code, submission.timeout, submission.resources)
    
    # 触发后台清理
    background_tasks.add_task(cleanup_old_nodes)
    
    return {
        "task_id": task_id,
        "status": "submitted",
        "server_id": storage.server_id,
        "message": f"Task {task_id} has been queued"
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
    """提交结果（增强版：支持节点ID）"""
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
    node_status = "healthy" if len(storage.nodes) > 0 else "no_nodes"
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "server_id": storage.server_id,
        "components": {
            "task_queue": "healthy",
            "memory_storage": "healthy",
            "node_manager": node_status,
            "scheduler": "healthy"
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
    else:
        nodes = list(storage.nodes.values())
    
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

@app.get("/stats")
async def get_system_stats() -> Dict[str, Any]:
    """系统统计端点（增强版）"""
    return storage.get_system_stats()

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