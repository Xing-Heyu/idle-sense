"""
scheduler/simple_server.py
极简调度中心 - 最终验证版
"""

from fastapi import FastAPI
from typing import List, Dict
import time

app = FastAPI()

# 内存存储
tasks: List[Dict] = []
results: Dict[int, Dict] = {}
task_id_counter = 1

@app.get("/")
def root():
    return {"service": "调度中心", "status": "运行中"}

@app.post("/submit")
def submit_task(code: str):
    """提交任务"""
    global task_id_counter
    
    task = {
        "task_id": task_id_counter,
        "code": code,
        "status": "pending",
        "created_at": time.time()
    }
    
    tasks.append(task)
    task_id_counter += 1
    
    print(f"[调度中心] 任务 {task['task_id']} 已提交")
    return {"task_id": task["task_id"], "status": "submitted"}

@app.get("/get_task")
def get_task():
    """获取一个任务"""
    用于任务中的任务：
        if task["status"] == "pending":
            task["status"] = "running"
            print(f"[调度中心] 任务 {task['task_id']} 已分配")
            return {
                "task_id": task["task_id"],
                "code": task["code"],
                "status": "assigned"
            }
    
    return {"task_id": None, "code": None, "status": "no_tasks"}

@app.post("/submit_result")
def submit_result(task_id: int, result: str):
    """提交任务结果"""
    # 更新任务状态
    用于任务中的任务：
        if task["task_id"] == task_id:
任务["状态"] = "已完成"
任务["完成时间"]= 时间.时间()
            break
    
    # 保存结果
结果[任务ID] = {
        "task_id": task_id,
        "result": result,
        "completed_at": 时间。时间()
    }
    
    print(f"[调度中心] 任务 {task_id} 已完成")
    return {"status": "ok"}

@app.get("/status/{task_id}")
def get_status(task_id: int):
    """获取任务状态"""
    用于任务中的任务：
        if task["task_id"] == task_id:
            return {
                "task_id": task_id,
                "status": task["status"],
                "result": results.get(task_id, {}).get("result")
            }
    return {"error": "任务不存在"}

@app.get("/results")
def get_results():
    """获取所有结果"""
    return list(results.values())
