"""
scheduler/simple_server.py
Minimal Task Scheduler - Final Verified Version
"""

import time
import uuid
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 📝 修复：定义数据模型，增强类型安全
class TaskSubmission(BaseModel):
    code: str

class TaskResult(BaseModel):
    task_id: int
    result: str

class TaskInfo(BaseModel):
    task_id: int
    code: str
    status: str
    created_at: float
    completed_at: Optional[float] = None
    result: Optional[str] = None

# 📝 修复：使用更安全的唯一标识符
app = FastAPI(
    title="Idle Computing Scheduler",
    description="Minimal task scheduler for idle computing resources",
    version="1.0.0"
)

# 📝 修改：改进内存存储结构
class MemoryStorage:
    """Thread-safe(ish) memory storage for tasks"""
    def __init__(self):
        self.tasks: Dict[int, TaskInfo] = {}
        self.task_id_counter = 1
        self.server_id = str(uuid.uuid4())[:8]
    
    def add_task(self, code: str) -> int:
        """Add a new task and return its ID"""
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
        """Get a pending task and mark it as running"""
        for task_id, task in self.tasks.items():
            if task.status == "pending":
                task.status = "running"
                return task
        return None
    
    def complete_task(self, task_id: int, result: str) -> bool:
        """Mark a task as completed with result"""
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
        """Get task status and result if available"""
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
        """Get all completed tasks"""
        return [
            {
                "task_id": task.task_id,
                "result": task.result,
                "completed_at": task.completed_at
            }
            for task in self.tasks.values()
            if task.status == "completed"
        ]

# 初始化存储
storage = MemoryStorage()

@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint for health check"""
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
    """Submit a new task for execution"""
    if not submission.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")
    
    # 📝 修复：限制代码长度（简单安全措施）
    if len(submission.code) > 10000:
        raise HTTPException(status_code=400, detail="Code too long (max 10000 characters)")
    
    task_id = storage.add_task(submission.code)
    print(f"[Scheduler] Task {task_id} submitted (server: {storage.server_id})")
    
    return {
        "task_id": task_id,
        "status": "submitted",
        "server_id": storage.server_id,
        "message": f"Task {task_id} has been queued"
    }

@app.get("/get_task")
async def get_task() -> Dict[str, Any]:
    """Get a pending task for execution"""
    task = storage.get_pending_task()
    
    if task is None:
        return {
            "task_id": None,
            "code": None,
            "status": "no_tasks",
            "message": "No pending tasks available"
        }
    
    print(f"[Scheduler] Task {task.task_id} assigned to worker")
    return {
        "task_id": task.task_id,
        "code": task.code,
        "status": "assigned",
        "created_at": task.created_at,
        "message": f"Task {task.task_id} assigned for execution"
    }

@app.post("/submit_result")
async def submit_result(result: TaskResult) -> Dict[str, Any]:
    """Submit result for a completed task"""
    if result.task_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    success = storage.complete_task(result.task_id, result.result)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Task {result.task_id} not found or not runnable")
    
    print(f"[Scheduler] Task {result.task_id} completed")
    return {
        "status": "ok",
        "task_id": result.task_id,
        "message": f"Result for task {result.task_id} recorded"
    }

@app.get("/status/{task_id}")
async def get_status(task_id: int) -> Dict[str, Any]:
    """Get status of a specific task"""
    if task_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    status = storage.get_task_status(task_id)
    
    if status is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return status

@app.get("/results")
async def get_results() -> Dict[str, Any]:
    """Get all completed task results"""
    results = storage.get_all_results()
    return {
        "count": len(results),
        "results": results,
        "server_id": storage.server_id
    }

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "server_id": storage.server_id,
        "memory_usage_mb": len(str(storage.tasks)) / (1024 * 1024)  # 粗略估计
    }

# 📝 修复：添加CORS支持，生产环境应限制来源
try:
    from fastapi.middleware.cors import CORSMiddleware
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # WARNING: For development only
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

# 📝 新增：启动代码示例
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
