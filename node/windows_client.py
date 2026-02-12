#!/usr/bin/env python3
"""
Windows兼容的节点客户端
解决Windows控制台Unicode编码问题
静默模式 - 无窗口、无打印
"""

# ===== 静默模式（必须放在最前面）=====
SILENT_MODE = True  # True = 不弹窗、不打印

if SILENT_MODE:
    import sys
    import os
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except:
            pass

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

def log(msg):
    if not SILENT_MODE:
        print(msg)

# 尝试导入idle_sense库
try:
    from idle_sense import is_idle, get_idle_info
    IDLE_SENSE_AVAILABLE = True
except ImportError:
    IDLE_SENSE_AVAILABLE = False
    log("[WARNING] idle_sense library not available")

# 节点配置
NODE_CAPACITY = {
    "cpu": 8.0,
    "memory": 16384
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
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        if not SILENT_MODE and sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"闲置计算节点已启动\n节点ID: {self.node_id[:20]}...",
                    "闲置计算加速器",
                    0x00000040  # 信息图标
                )
            except:
                pass
    def _generate_node_id(self) -> str:
   
        import os
        import json
    
    # 用户目录，永远可写
        id_file = os.path.join(os.path.expanduser("~"), ".idle_sense_node_id")
    
    # 如果已经有保存的ID，直接使用
        if os.path.exists(id_file):
            try:
                with open(id_file, 'r') as f:
                    saved_id = f.read().strip()
                    if saved_id:
                        log(f"[节点ID] 使用已保存的ID: {saved_id}")
                        return saved_id
            except:
                pass
    
    # 第一次运行，生成新ID并保存
        hostname = platform.node() if hasattr(platform, 'node') else "unknown"
        timestamp = int(time.time())
        random_suffix = os.urandom(4).hex()
        node_id = f"{hostname}-{timestamp}-{random_suffix}"
        
        # 保存到用户目录
        try:
            with open(id_file, 'w') as f:
                f.write(node_id)
            log(f"[节点ID] 生成并保存新ID: {node_id}")
        except Exception as e:
            log(f"[警告] 无法保存节点ID: {e}")
    
        return node_id
    
    def _signal_handler(self, signum, frame):
        log("[INFO] Received shutdown signal")
        self.is_running = False
    
    def _get_system_info(self) -> Dict[str, Any]:
        system_info = {
            "hostname": platform.node() if hasattr(platform, 'node') else "unknown",
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "idle_sense_available": IDLE_SENSE_AVAILABLE,
            "capacity": NODE_CAPACITY.copy()
        }
        return system_info
    
    def _check_idle(self) -> Tuple[bool, Dict[str, Any]]:
        if IDLE_SENSE_AVAILABLE:
            try:
                idle_info = get_idle_info()
                is_idle = is_idle()
                return is_idle, idle_info
            except Exception as e:
                log(f"[ERROR] Idle detection failed: {e}")
        
        idle_info = {
            "cpu_percent": 10.0,
            "memory_percent": 20.0,
            "idle_time": 0
        }
        return False, idle_info
    
    def _calculate_available_resources(self) -> Dict[str, float]:
        is_idle_state, idle_info = self._check_idle()
        
        if is_idle_state:
            return {
                "cpu": NODE_CAPACITY["cpu"] * 0.8,
                "memory": NODE_CAPACITY["memory"] * 0.9
            }
        else:
            return {
                "cpu": NODE_CAPACITY["cpu"] * 0.2,
                "memory": NODE_CAPACITY["memory"] * 0.3
            }
    
    def register_node(self) -> bool:
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
                log(f"[SUCCESS] Registered with scheduler as node: {self.node_id}")
                return True
            else:
                log(f"[ERROR] Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            log(f"[ERROR] Registration error: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
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
                f"{self.server_url}/api/nodes/{self.node_id}/heartbeat",
                json=heartbeat_data,
                timeout=5
            )
            
            return response.status_code == 200
            
        except Exception as e:
            log(f"[ERROR] Heartbeat failed: {e}")
            return False
    
    def get_task(self) -> Optional[Dict[str, Any]]:
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
                return {"status": "no_tasks"}
            else:
                log(f"[ERROR] Get task failed: {response.status_code}")
                return None
                
        except Exception as e:
            log(f"[ERROR] Get task error: {e}")
            return None
    
    def execute_task(self, task_id: str, code: str) -> str:
        try:
            local_vars = {}
            exec(code, {"__builtins__": {}}, local_vars)
            result = local_vars.get("__result__", "Task completed without result")
            return str(result)
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            log(f"[ERROR] {error_msg}")
            return error_msg
    
    def submit_result(self, task_id: str, result: str) -> bool:
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
            log(f"[ERROR] Submit result failed: {e}")
            return False
    
    def run(self):
        log("=" * 60)
        log("Windows Node Client - Idle Computing System")
        log("=" * 60)
        
        system_info = self._get_system_info()
        log(f"Node ID: {self.node_id}")
        log(f"Server URL: {self.server_url}")
        log(f"Node Capacity: CPU={NODE_CAPACITY['cpu']} cores, Memory={NODE_CAPACITY['memory']}MB")
        log(f"Hostname: {system_info['hostname']}")
        log(f"Platform: {system_info['platform']}")
        log(f"Python: {system_info['python_version']}")
        log(f"Idle Sense: {'Available' if system_info['idle_sense_available'] else 'Not Available'}")
        log("-" * 60)
        
        if not self.register_node():
            log("[ERROR] Failed to register node")
            return
        
        log("[INFO] Node client started successfully")
        log("[INFO] Waiting for tasks...")
        
        last_heartbeat = time.time()
        
        while self.is_running and self.error_count < self.max_errors:
            try:
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    if self.send_heartbeat():
                        log("[INFO] Heartbeat sent")
                    else:
                        log("[WARNING] Heartbeat failed")
                    last_heartbeat = current_time
                
                task_data = self.get_task()
                
                if task_data:
                    if "task_id" in task_data and "code" in task_data:
                        task_id = task_data["task_id"]
                        code = task_data["code"]
                        
                        log(f"[INFO] Received task: {task_id}")
                        
                        start_time = time.time()
                        result = self.execute_task(task_id, code)
                        execution_time = time.time() - start_time
                        
                        if self.submit_result(task_id, result):
                            log(f"[SUCCESS] Completed in {execution_time:.1f}s")
                        else:
                            self.error_count += 1
                            log(f"[ERROR] Failed to submit result")
                    else:
                        if task_data.get("status") == "no_tasks":
                            time.sleep(5)
                else:
                    self.error_count += 1
                    log("[ERROR] Failed to get task")
                
                if self.error_count > 0:
                    time.sleep(10)
                else:
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                log("\n[INFO] Shutting down...")
                break
            except Exception as e:
                self.error_count += 1
                log(f"[ERROR] Main loop error: {e}")
                time.sleep(10)
        
        log("[INFO] Node client stopped")

def main():
    client = WindowsNodeClient()
    client.run()

if __name__ == "__main__":
    main()