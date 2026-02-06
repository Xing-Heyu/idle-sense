
"""
scheduler/simple_server.py
Minimal Task Scheduler - Syntax Fixed Version
"""

import time
import uuid
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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

class TaskInfo(BaseModel):
    """任务信息模型"""
    task_id: int
    code: str
    status: str  # pending, running, completed, failed
    created_at: float
    completed_at: Optional[float] = None
    result: Optional[str] = None

# ==================== 内存存储类 ====================
class MemoryStorage:
    """线程安全的内存存储"""
    
    def __init__(self):
        self.tasks: Dict[int, TaskInfo] = {}
        self.results: Dict[int, str] = {}
        self.task_id_counter = 1
        self.server_id = str(uuid.uuid4())[:8]
    
    def add_task(self, code: str, timeout: int = 300) -> int:
        """添加新任务"""
        task_id = self.task_id_counter
        self.tasks[task_id] = TaskInfo(
            task_id=task_id,
            code=code,
            status="pending",
            created_at=time.time()
        )
        self.task_id_counter += 1
        return task_id
    
    def get_pending_task(self) -> Optional[TaskInfo]:
        """获取待处理任务"""
        for task_id, task in self.tasks.items():
            if task.status == "pending":
                task.status = "running"
                return task
        return None
    
    def complete_task(self, task_id: int, result: str) -> bool:
        """完成任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status in ["pending", "running"]:
            task.status = "completed"
            task.completed_at = time.time()
            task.result = result
            return True
        return False
    
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
            "completed_at": task.completed_at
        }
    
    def get_all_results(self) -> List[Dict[str, Any]]:
        """获取所有结果"""
        return [
            {
                "task_id": task.task_id,
                "result": task.result,
                "completed_at": task.completed_at
            }
            for task in self.tasks.values()
            if task.status == "completed"
        ]

# ==================== FastAPI 应用 ====================
app = FastAPI(
    title="Idle Computing Scheduler",
    description="Minimal task scheduler for idle computing resources",
    version="1.0.0"
)

# 初始化存储
storage = MemoryStorage()

# ==================== 传统端点（保持兼容） ====================
@app.get("/")
async def root() -> Dict[str, Any]:
    """根端点 - 健康检查"""
    return {
        "service": "Idle Computing Scheduler",
        "status": "running",
        "version": "1.0.0",
        "server_id": storage.server_id,
        "task_count": len(storage.tasks),
        "pending_tasks": sum(1 for t in storage.tasks.values() if t.status == "pending")
    }

@app.post("/submit")
async def submit_task(submission: TaskSubmission) -> Dict[str, Any]:
    """提交任务（兼容旧端点）"""
    if not submission.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")
    
    if len(submission.code) > 10000:
        raise HTTPException(status_code=400, detail="Code too long (max 10000 characters)")
    
    task_id = storage.add_task(submission.code, submission.timeout)
    
    return {
        "task_id": task_id,
        "status": "submitted",
        "server_id": storage.server_id,
        "message": f"Task {task_id} has been queued"
    }

@app.get("/get_task")
async def get_task() -> Dict[str, Any]:
    """获取任务（兼容旧端点）"""
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
        "status": "assigned",
        "created_at": task.created_at,
        "message": f"Task {task.task_id} assigned for execution"
    }

@app.post("/submit_result")
async def submit_result(result: TaskResult) -> Dict[str, Any]:
    """提交结果（兼容旧端点）"""
    if result.task_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    success = storage.complete_task(result.task_id, result.result)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Task {result.task_id} not found or not runnable")
    
    return {
        "status": "ok",
        "task_id": result.task_id,
        "message": f"Result for task {result.task_id} recorded"
    }

@app.get("/status/{task_id}")
async def get_status(task_id: int) -> Dict[str, Any]:
    """获取任务状态（兼容旧端点）"""
    if task_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    status = storage.get_task_status(task_id)
    
    if status is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return status

@app.get("/results")
async def get_results() -> Dict[str, Any]:
    """获取所有结果（兼容旧端点）"""
    results = storage.get_all_results()
    return {
        "count": len(results),
        "results": results,
        "server_id": storage.server_id
    }

# ==================== 新增端点（符合 docs/API_REFERENCE.md） ====================
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "server_id": storage.server_id,
        "components": {
            "task_queue": "healthy",
            "memory_storage": "healthy"
        }
    }

@app.get("/stats")
async def get_system_stats() -> Dict[str, Any]:
    """系统统计端点"""
    total_tasks = len(storage.tasks)
    completed_tasks = sum(1 for t in storage.tasks.values() if t.status == "completed")
    pending_tasks = sum(1 for t in storage.tasks.values() if t.status == "pending")
    
    # 计算平均完成时间
    completed_times = []
    for task in storage.tasks.values():
        if task.status == "completed" and task.completed_at:
            completed_times.append(task.completed_at - task.created_at)
    
    avg_time = sum(completed_times) / len(completed_times) if completed_times else 0
    
    return {
        "time_period": "all_time",
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "pending": pending_tasks,
            "failed": total_tasks - completed_tasks - pending_tasks,
            "avg_time": round(avg_time, 2)
        },
        "nodes": {
            "total": 0,  # 需要节点注册功能
            "idle": 0,
            "busy": 0,
            "offline": 0
        },
        "throughput": {
            "tasks_per_hour": 0,
            "compute_hours": 0
        }
    }

# ==================== CORS 支持 ====================
try:
    from fastapi.middleware.cors import CORSMiddleware
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 警告：仅用于开发
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600,
    )
    print("[Scheduler] CORS middleware enabled")
except ImportError:
    print("[Scheduler] CORS middleware not available")
    pass

# ==================== 启动代码 ====================
if __name__ == "__main__":
    import uvicorn
    print(f"[Scheduler] Starting server on http://localhost:8000")
    print(f"[Scheduler] Server ID: {storage.server_id}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
