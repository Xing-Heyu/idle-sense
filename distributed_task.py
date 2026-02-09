#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分布式任务处理模块
支持多节点协作处理大型任务
"""

import os
import sys
import json
import time
import hashlib
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class TaskChunk:
    """任务分片"""
    chunk_id: str
    parent_task_id: str
    code: str
    data: Any
    dependencies: List[str] = None
    status: str = "pending"  # pending, assigned, running, completed, failed
    assigned_node: str = None
    result: Any = None
    error: str = None
    created_at: float = None
    assigned_at: float = None
    completed_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class DistributedTask:
    """分布式任务"""
    task_id: str
    name: str
    description: str
    code_template: str
    data: Any
    chunk_size: int = 10  # 默认分片大小
    max_parallel_chunks: int = 5  # 最大并行分片数
    merge_code: str = None  # 合并结果的代码
    status: str = "pending"  # pending, chunking, executing, merging, completed, failed
    chunks: List[TaskChunk] = None
    result: Any = None
    error: str = None
    created_at: float = None
    started_at: float = None
    completed_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.chunks is None:
            self.chunks = []

class DistributedTaskManager:
    """分布式任务管理器"""
    
    def __init__(self, scheduler_url: str = "http://localhost:8000"):
        self.scheduler_url = scheduler_url
        self.tasks: Dict[str, DistributedTask] = {}
        self.chunk_results: Dict[str, Any] = {}
        self.lock = threading.Lock()
    
    def submit_distributed_task(self, name: str, description: str, code_template: str, 
                                data: Any, chunk_size: int = 10, 
                                max_parallel_chunks: int = 5, 
                                merge_code: str = None) -> str:
        """提交分布式任务"""
        # 生成任务ID
        task_id = self._generate_task_id(name)
        
        # 创建分布式任务
        task = DistributedTask(
            task_id=task_id,
            name=name,
            description=description,
            code_template=code_template,
            data=data,
            chunk_size=chunk_size,
            max_parallel_chunks=max_parallel_chunks,
            merge_code=merge_code
        )
        
        with self.lock:
            self.tasks[task_id] = task
        
        return task_id
    
    def create_task_chunks(self, task_id: str) -> bool:
        """创建任务分片"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            
            try:
                # 根据数据类型分片
                if isinstance(task.data, list):
                    chunks = self._chunk_list_data(task)
                elif isinstance(task.data, dict):
                    chunks = self._chunk_dict_data(task)
                elif hasattr(task.data, '__iter__'):
                    chunks = self._chunk_iterable_data(task)
                else:
                    # 无法分片的数据，作为单个任务
                    chunks = [self._create_single_chunk(task)]
                
                task.chunks = chunks
                task.status = "chunking"
                return True
                
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                return False
    
    def execute_distributed_task(self, task_id: str) -> bool:
        """执行分布式任务"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task or not task.chunks:
                return False
            
            task.status = "executing"
            task.started_at = time.time()
        
        try:
            # 提交所有分片任务到调度中心
            submitted_chunks = []
            for chunk in task.chunks:
                chunk_task_id = self._submit_chunk_to_scheduler(chunk)
                if chunk_task_id:
                    chunk.assigned_at = time.time()
                    submitted_chunks.append((chunk, chunk_task_id))
            
            # 等待所有分片完成
            completed_chunks = 0
            total_chunks = len(task.chunks)
            
            while completed_chunks < total_chunks:
                for chunk, scheduler_task_id in submitted_chunks:
                    if chunk.status == "pending":
                        # 检查分片任务状态
                        status, result = self._check_scheduler_task_status(scheduler_task_id)
                        if status == "completed":
                            chunk.status = "completed"
                            chunk.completed_at = time.time()
                            chunk.result = result
                            completed_chunks += 1
                        elif status == "failed":
                            chunk.status = "failed"
                            chunk.error = result
                            completed_chunks += 1
                
                time.sleep(1)  # 避免频繁查询
            
            # 合并结果
            if self._merge_chunk_results(task):
                task.status = "completed"
                task.completed_at = time.time()
                return True
            else:
                task.status = "failed"
                task.error = "Failed to merge chunk results"
                return False
                
        except Exception as e:
            with self.lock:
                task.status = "failed"
                task.error = str(e)
            return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取分布式任务状态"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            
            # 计算进度
            total_chunks = len(task.chunks)
            completed_chunks = sum(1 for chunk in task.chunks if chunk.status == "completed")
            failed_chunks = sum(1 for chunk in task.chunks if chunk.status == "failed")
            progress = (completed_chunks + failed_chunks) / total_chunks if total_chunks > 0 else 0
            
            return {
                "task_id": task.task_id,
                "name": task.name,
                "description": task.description,
                "status": task.status,
                "progress": progress,
                "total_chunks": total_chunks,
                "completed_chunks": completed_chunks,
                "failed_chunks": failed_chunks,
                "result": task.result,
                "error": task.error,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at
            }
    
    def get_task_result(self, task_id: str) -> Optional[Any]:
        """获取分布式任务结果"""
        with self.lock:
            task = self.tasks.get(task_id)
            if task and task.status == "completed":
                return task.result
            return None
    
    def _generate_task_id(self, name: str) -> str:
        """生成任务ID"""
        timestamp = str(int(time.time()))
        content = f"{name}_{timestamp}_{os.getpid()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _chunk_list_data(self, task: DistributedTask) -> List[TaskChunk]:
        """分片列表数据"""
        chunks = []
        data_list = task.data
        chunk_size = task.chunk_size
        
        for i in range(0, len(data_list), chunk_size):
            chunk_data = data_list[i:i + chunk_size]
            chunk_id = f"{task.task_id}_chunk_{i // chunk_size}"
            
            # 替换代码模板中的数据占位符
            code = task.code_template.replace("__DATA__", json.dumps(chunk_data))
            code = code.replace("__CHUNK_ID__", chunk_id)
            code = code.replace("__CHUNK_INDEX__", str(i // chunk_size))
            
            chunk = TaskChunk(
                chunk_id=chunk_id,
                parent_task_id=task.task_id,
                code=code,
                data=chunk_data
            )
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_dict_data(self, task: DistributedTask) -> List[TaskChunk]:
        """分片字典数据"""
        chunks = []
        data_dict = task.data
        items = list(data_dict.items())
        chunk_size = task.chunk_size
        
        for i in range(0, len(items), chunk_size):
            chunk_data = dict(items[i:i + chunk_size])
            chunk_id = f"{task.task_id}_chunk_{i // chunk_size}"
            
            # 替换代码模板中的数据占位符
            code = task.code_template.replace("__DATA__", json.dumps(chunk_data))
            code = code.replace("__CHUNK_ID__", chunk_id)
            code = code.replace("__CHUNK_INDEX__", str(i // chunk_size))
            
            chunk = TaskChunk(
                chunk_id=chunk_id,
                parent_task_id=task.task_id,
                code=code,
                data=chunk_data
            )
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_iterable_data(self, task: DistributedTask) -> List[TaskChunk]:
        """分片可迭代数据"""
        chunks = []
        data_iter = iter(task.data)
        chunk_size = task.chunk_size
        chunk_index = 0
        
        while True:
            chunk_data = []
            try:
                for _ in range(chunk_size):
                    chunk_data.append(next(data_iter))
            except StopIteration:
                pass
            
            if not chunk_data:
                break
            
            chunk_id = f"{task.task_id}_chunk_{chunk_index}"
            
            # 替换代码模板中的数据占位符
            code = task.code_template.replace("__DATA__", json.dumps(chunk_data))
            code = code.replace("__CHUNK_ID__", chunk_id)
            code = code.replace("__CHUNK_INDEX__", str(chunk_index))
            
            chunk = TaskChunk(
                chunk_id=chunk_id,
                parent_task_id=task.task_id,
                code=code,
                data=chunk_data
            )
            chunks.append(chunk)
            chunk_index += 1
        
        return chunks
    
    def _create_single_chunk(self, task: DistributedTask) -> TaskChunk:
        """创建单个分片（无法分片的数据）"""
        chunk_id = f"{task.task_id}_chunk_0"
        
        # 替换代码模板中的数据占位符
        code = task.code_template.replace("__DATA__", json.dumps(task.data))
        code = code.replace("__CHUNK_ID__", chunk_id)
        code = code.replace("__CHUNK_INDEX__", "0")
        
        return TaskChunk(
            chunk_id=chunk_id,
            parent_task_id=task.task_id,
            code=code,
            data=task.data
        )
    
    def _submit_chunk_to_scheduler(self, chunk: TaskChunk) -> Optional[str]:
        """提交分片任务到调度中心"""
        try:
            payload = {
                "code": chunk.code,
                "timeout": 300,
                "resources": {
                    "cpu": 1.0,
                    "memory": 512
                }
            }
            
            response = requests.post(
                f"{self.scheduler_url}/submit",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("task_id")
            else:
                print(f"Failed to submit chunk {chunk.chunk_id}: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error submitting chunk {chunk.chunk_id}: {e}")
            return None
    
    def _check_scheduler_task_status(self, task_id: str) -> Tuple[str, Any]:
        """检查调度中心任务状态"""
        try:
            response = requests.get(f"{self.scheduler_url}/status/{task_id}", timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                status = result.get("status", "unknown")
                
                if status == "completed":
                    return "completed", result.get("result", "")
                elif status == "failed":
                    return "failed", result.get("result", "执行失败")
                else:
                    return "pending", None
            else:
                return "failed", f"查询失败: {response.status_code}"
                
        except Exception as e:
            return "failed", f"查询异常: {str(e)}"
    
    def _merge_chunk_results(self, task: DistributedTask) -> bool:
        """合并分片结果"""
        try:
            # 收集所有成功完成的分片结果
            chunk_results = []
            for chunk in task.chunks:
                if chunk.status == "completed" and chunk.result is not None:
                    chunk_results.append(chunk.result)
            
            if not chunk_results:
                task.error = "没有成功完成的分片"
                return False
            
            # 如果有合并代码，使用合并代码合并结果
            if task.merge_code:
                # 创建临时执行环境
                merge_env = {
                    "__CHUNK_RESULTS__": chunk_results,
                    "__TASK_ID__": task.task_id,
                    "__TASK_NAME__": task.name
                }
                
                # 执行合并代码
                exec_result = {}
                exec(task.merge_code, merge_env, exec_result)
                task.result = exec_result.get("__MERGED_RESULT__", chunk_results)
            else:
                # 默认合并策略：简单拼接所有结果
                if all(isinstance(r, str) for r in chunk_results):
                    task.result = "\n".join(chunk_results)
                elif all(isinstance(r, list) for r in chunk_results):
                    task.result = []
                    for r in chunk_results:
                        task.result.extend(r)
                elif all(isinstance(r, dict) for r in chunk_results):
                    task.result = {}
                    for r in chunk_results:
                        task.result.update(r)
                else:
                    task.result = chunk_results
            
            return True
            
        except Exception as e:
            task.error = f"合并结果失败: {str(e)}"
            return False

# 预定义的分布式任务模板
DISTRIBUTED_TASK_TEMPLATES = {
    "map_reduce": {
        "name": "Map-Reduce任务",
        "description": "将大型数据集分片处理，然后合并结果",
        "code_template": """
# Map-Reduce 任务分片处理
# 数据: __DATA__
# 分片ID: __CHUNK_ID__
# 分片索引: __CHUNK_INDEX__

import json

# 获取当前分片数据
data = __DATA__
chunk_id = __CHUNK_ID__
chunk_index = __CHUNK_INDEX__

# 在这里实现你的Map逻辑
def map_function(data_item):
    # 示例：计算数据项的某种属性
    return data_item

# 处理当前分片
mapped_results = []
for item in data:
    result = map_function(item)
    mapped_results.append(result)

# 输出结果（会被收集到__CHUNK_RESULTS__中）
__result__ = {
    "chunk_id": chunk_id,
    "chunk_index": chunk_index,
    "mapped_results": mapped_results,
    "count": len(mapped_results)
}
print(f"分片 {chunk_id} 处理完成，处理了 {len(mapped_results)} 项数据")
""",
        "merge_code": """
# Merge-Reduce 合并结果
# 所有分片结果在: __CHUNK_RESULTS__

all_mapped_results = []
total_count = 0

for chunk_result in __CHUNK_RESULTS__:
    if isinstance(chunk_result, dict) and "mapped_results" in chunk_result:
        all_mapped_results.extend(chunk_result["mapped_results"])
        total_count += chunk_result["count"]

# 在这里实现你的Reduce逻辑
def reduce_function(all_results):
    # 示例：计算所有结果的统计信息
    return {
        "total_items": len(all_results),
        "summary": "所有分片处理完成"
    }

# 执行Reduce逻辑
final_result = reduce_function(all_mapped_results)

# 设置最终结果
__MERGED_RESULT__ = final_result
print(f"合并完成，总计处理 {total_count} 项数据")
"""
    },
    
    "parallel_search": {
        "name": "并行搜索任务",
        "description": "将搜索空间分片，并行搜索",
        "code_template": """
# 并行搜索任务分片
# 数据: __DATA__
# 分片ID: __CHUNK_ID__
# 分片索引: __CHUNK_INDEX__

import json

# 获取当前分片数据
search_space = __DATA__
chunk_id = __CHUNK_ID__
chunk_index = __CHUNK_INDEX__

# 在这里实现你的搜索逻辑
def search_function(search_item):
    # 示例：检查搜索项是否满足条件
    return search_item % 100 == 0  # 找出能被100整除的数

# 搜索当前分片
found_items = []
for item in search_space:
    if search_function(item):
        found_items.append(item)

# 输出结果
__result__ = {
    "chunk_id": chunk_id,
    "chunk_index": chunk_index,
    "found_items": found_items,
    "count": len(found_items)
}
print(f"分片 {chunk_id} 搜索完成，找到 {len(found_items)} 个匹配项")
""",
        "merge_code": """
# 并行搜索结果合并
# 所有分片结果在: __CHUNK_RESULTS__

all_found_items = []
total_found = 0

for chunk_result in __CHUNK_RESULTS__:
    if isinstance(chunk_result, dict) and "found_items" in chunk_result:
        all_found_items.extend(chunk_result["found_items"])
        total_found += chunk_result["count"]

# 可以对结果进行排序或其他处理
all_found_items.sort()

# 设置最终结果
__MERGED_RESULT__ = {
    "total_found": total_found,
    "found_items": all_found_items
}
print(f"搜索完成，总计找到 {total_found} 个匹配项")
"""
    },
    
    "data_processing": {
        "name": "数据处理任务",
        "description": "将大型数据集分片处理",
        "code_template": """
# 数据处理任务分片
# 数据: __DATA__
# 分片ID: __CHUNK_ID__
# 分片索引: __CHUNK_INDEX__

import json

# 获取当前分片数据
data = __DATA__
chunk_id = __CHUNK_ID__
chunk_index = __CHUNK_INDEX__

# 在这里实现你的数据处理逻辑
def process_function(data_item):
    # 示例：对数据项进行转换
    if isinstance(data_item, dict):
        # 处理字典类型数据
        return {"processed": True, "original": data_item}
    elif isinstance(data_item, (int, float)):
        # 处理数值类型数据
        return data_item * 2
    else:
        # 处理其他类型数据
        return str(data_item).upper()

# 处理当前分片
processed_results = []
for item in data:
    result = process_function(item)
    processed_results.append(result)

# 输出结果
__result__ = {
    "chunk_id": chunk_id,
    "chunk_index": chunk_index,
    "processed_results": processed_results,
    "count": len(processed_results)
}
print(f"分片 {chunk_id} 处理完成，处理了 {len(processed_results)} 项数据")
""",
        "merge_code": """
# 数据处理结果合并
# 所有分片结果在: __CHUNK_RESULTS__

all_processed_results = []
total_processed = 0

for chunk_result in __CHUNK_RESULTS__:
    if isinstance(chunk_result, dict) and "processed_results" in chunk_result:
        all_processed_results.extend(chunk_result["processed_results"])
        total_processed += chunk_result["count"]

# 设置最终结果
__MERGED_RESULT__ = {
    "total_processed": total_processed,
    "processed_results": all_processed_results
}
print(f"数据处理完成，总计处理 {total_processed} 项数据")
"""
    }
}

# 使用示例
if __name__ == "__main__":
    # 创建分布式任务管理器
    manager = DistributedTaskManager("http://localhost:8000")
    
    # 示例1: Map-Reduce任务
    print("示例1: Map-Reduce任务")
    map_reduce_data = list(range(1, 1001))  # 1到1000的数字
    
    task_id = manager.submit_distributed_task(
        name="数字统计",
        description="统计1到1000中能被100整除的数字",
        code_template=DISTRIBUTED_TASK_TEMPLATES["map_reduce"]["code_template"],
        data=map_reduce_data,
        chunk_size=100,
        max_parallel_chunks=5,
        merge_code=DISTRIBUTED_TASK_TEMPLATES["map_reduce"]["merge_code"]
    )
    
    # 创建分片
    if manager.create_task_chunks(task_id):
        print(f"任务 {task_id} 分片创建成功")
        
        # 执行任务
        if manager.execute_distributed_task(task_id):
            print(f"任务 {task_id} 执行成功")
            result = manager.get_task_result(task_id)
            print(f"结果: {result}")
        else:
            print(f"任务 {task_id} 执行失败")
    else:
        print(f"任务 {task_id} 分片创建失败")