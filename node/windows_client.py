#!/usr/bin/env python3
"""
Windows兼容的节点客户端
解决Windows控制台Unicode编码问题
"""

import requests
import time
import sys
import os
import signal
import threading
import json
import traceback
import platform
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime

# 尝试导入idle_sense库
try:
    from idle_sense import is_idle, get_idle_info
    IDLE_SENSE_AVAILABLE = True
except ImportError:
    IDLE_SENSE_AVAILABLE = False
    print("[WARNING] idle_sense library not available")

# 节点配置
NODE_CAPACITY = {
    "cpu": 4.0,  # CPU核心数
    "memory": 8192  # 内存MB
}

SERVER_URL = "http://localhost:8000"

class WindowsNodeClient:
    """Windows兼容的节点客户端"""
    
    def __init__(self):
        self.node_id = self._generate_node_id()
        self.server_url = SERVER_URL
        self.is_registered = False
        self.is_running = True
        self.error_count = 0
        self.max_errors = 10
        
        # 信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _generate_node_id(self) -> str:
        """生成节点ID"""
        hostname = platform.node() if hasattr(platform, 'node') else "unknown"
        timestamp = int(time.time())
        random_suffix = os.urandom(4).hex()
        return f"{hostname}-{timestamp}-{random_suffix}"
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        print("[INFO] Received shutdown signal")
        self.is_running = False
    
    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        system_info = {
            "hostname": platform.node() if hasattr(platform, 'node') else "unknown",
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "idle_sense_available": IDLE_SENSE_AVAILABLE,
            "capacity": NODE_CAPACITY.copy()
        }
        return system_info
    
    def _check_idle(self) -> Tuple[bool, Dict[str, Any]]:
        """检查系统是否闲置"""
        if IDLE_SENSE_AVAILABLE:
            try:
                idle_info = get_idle_info()
                is_idle = is_idle()
                return is_idle, idle_info
            except Exception as e:
                print(f"[ERROR] Idle detection failed: {e}")
        
        # 备用方案：总是返回非闲置状态
        idle_info = {
            "cpu_percent": 10.0,
            "memory_percent": 20.0,
            "idle_time": 0
        }
        return False, idle_info
    
    def _calculate_available_resources(self) -> Dict[str, float]:
        """计算可用资源"""
        is_idle_state, idle_info = self._check_idle()
        
        if is_idle_state:
            # 闲置状态：提供更多资源
            return {
                "cpu": NODE_CAPACITY["cpu"] * 0.8,  # 80% CPU
                "memory": NODE_CAPACITY["memory"] * 0.9  # 90% 内存
            }
        else:
            # 非闲置状态：提供较少资源
            return {
                "cpu": NODE_CAPACITY["cpu"] * 0.2,  # 20% CPU
                "memory": NODE_CAPACITY["memory"] * 0.3  # 30% 内存
            }
    
    def register_node(self) -> bool:
        """注册节点到调度中心"""
        try:
            system_info = self._get_system_info()
            
            registration_data = {
                "node_id": self.node_id,
                "system_info": system_info,
                "available_resources": self._calculate_available_resources()
            }
            
            response = requests.post(
                f"{self.server_url}/api/nodes/register",
                json=registration_data,
                timeout=10
            )
            
            if response.status_code == 200:
                self.is_registered = True
                print(f"[SUCCESS] Registered with scheduler as node: {self.node_id}")
                return True
            else:
                print(f"[ERROR] Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Registration error: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
        """发送心跳到调度中心"""
        try:
            is_idle_state, idle_info = self._check_idle()
            available_resources = self._calculate_available_resources()
            
            heartbeat_data = {
                "node_id": self.node_id,
                "current_load": {
                    "cpu_usage": idle_info.get("cpu_percent", 0) / 100.0 * NODE_CAPACITY["cpu"],
                    "memory_usage": int(idle_info.get("memory_percent", 0) / 100.0 * NODE_CAPACITY["memory"])
                },
                "is_idle": is_idle_state,
                "available_resources": available_resources
            }
            
            response = requests.post(
                f"{self.server_url}/api/nodes/heartbeat",
                json=heartbeat_data,
                timeout=5
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"[ERROR] Heartbeat failed: {e}")
            return False
    
    def get_task(self) -> Optional[Dict[str, Any]]:
        """获取任务"""
        try:
            response = requests.post(
                f"{self.server_url}/api/tasks/claim",
                json={
                    "node_id": self.node_id,
                    "available_resources": self._calculate_available_resources()
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # 没有可用任务
                return {"status": "no_tasks"}
            else:
                print(f"[ERROR] Get task failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[ERROR] Get task error: {e}")
            return None
    
    def execute_task(self, task_id: str, code: str) -> str:
        """执行任务"""
        try:
            # 创建安全的执行环境
            local_vars = {}
            
            # 执行代码
            exec(code, {"__builtins__": {}}, local_vars)
            
            # 获取结果
            result = local_vars.get("__result__", "Task completed without result")
            
            return str(result)
            
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return error_msg
    
    def submit_result(self, task_id: str, result: str) -> bool:
        """提交任务结果"""
        try:
            response = requests.post(
                f"{self.server_url}/api/tasks/{task_id}/complete",
                json={
                    "node_id": self.node_id,
                    "result": result
                },
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"[ERROR] Submit result failed: {e}")
            return False
    
    def run(self):
        """运行节点客户端"""
        print("=" * 60)
        print("Windows Node Client - Idle Computing System")
        print("=" * 60)
        
        system_info = self._get_system_info()
        print(f"Node ID: {self.node_id}")
        print(f"Server URL: {self.server_url}")
        print(f"Node Capacity: CPU={NODE_CAPACITY['cpu']} cores, Memory={NODE_CAPACITY['memory']}MB")
        print(f"Hostname: {system_info['hostname']}")
        print(f"Platform: {system_info['platform']}")
        print(f"Python: {system_info['python_version']}")
        print(f"Idle Sense: {'Available' if system_info['idle_sense_available'] else 'Not Available'}")
        print("-" * 60)
        
        # 注册节点
        if not self.register_node():
            print("[ERROR] Failed to register node")
            return
        
        print("[INFO] Node client started successfully")
        print("[INFO] Waiting for tasks...")
        
        # 主循环
        last_heartbeat = time.time()
        
        while self.is_running and self.error_count < self.max_errors:
            try:
                # 发送心跳（每30秒一次）
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    if self.send_heartbeat():
                        print("[INFO] Heartbeat sent")
                    else:
                        print("[WARNING] Heartbeat failed")
                    last_heartbeat = current_time
                
                # 获取任务
                task_data = self.get_task()
                
                if task_data:
                    if "task_id" in task_data and "code" in task_data:
                        task_id = task_data["task_id"]
                        code = task_data["code"]
                        
                        print(f"[INFO] Received task: {task_id}")
                        
                        # 执行任务
                        start_time = time.time()
                        result = self.execute_task(task_id, code)
                        execution_time = time.time() - start_time
                        
                        # 提交结果
                        if self.submit_result(task_id, result):
                            print(f"[SUCCESS] Completed in {execution_time:.1f}s")
                        else:
                            self.error_count += 1
                            print(f"[ERROR] Failed to submit result")
                    else:
                        if task_data.get("status") == "no_tasks":
                            # 没有任务，等待一段时间
                            time.sleep(5)
                else:
                    self.error_count += 1
                    print("[ERROR] Failed to get task")
                
                # 错误计数重置
                if self.error_count > 0:
                    time.sleep(10)  # 出错时等待更长时间
                else:
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                print("\n[INFO] Shutting down...")
                break
            except Exception as e:
                self.error_count += 1
                print(f"[ERROR] Main loop error: {e}")
                time.sleep(10)
        
        print("[INFO] Node client stopped")

def main():
    """主函数"""
    client = WindowsNodeClient()
    client.run()

if __name__ == "__main__":
    main()