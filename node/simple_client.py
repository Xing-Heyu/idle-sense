"""
node/simple_client.py
Enhanced Node Client with Node Registration and Heartbeat
"""

import requests
import time
import sys
import os
import signal
import threading
import json
import traceback
import platform  # 添加platform导入
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime

# 📝 修复：更可靠的路径处理
def setup_paths() -> None:
    """Setup Python paths for imports"""
    # 获取项目根目录
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    
    # 添加项目根目录到路径（如果不在sys.path中）
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # 添加当前目录
    current_dir = str(current_file.parent)
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

setup_paths()

# 📝 尝试导入idle_sense
try:
    from idle_sense import is_idle, get_system_status, get_platform
    IDLE_SENSE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: idle_sense not available: {e}")
    print("Will use simplified idle detection")
    IDLE_SENSE_AVAILABLE = False

# 配置
SERVER_URL = "http://localhost:8000"
NODE_ID = None  # 将在启动时生成
CHECK_INTERVAL = 30  # 秒
HEARTBEAT_INTERVAL = 20  # 心跳间隔（秒）
TASK_TIMEOUT = 300   # 任务执行超时时间（秒）
MAX_RETRIES = 3      # 最大重试次数

# 节点容量配置（可根据实际硬件调整）
NODE_CAPACITY = {
    "cpu": 4.0,      # CPU核心数
    "memory": 8192,  # 内存（MB）
    "disk": 100000   # 磁盘空间（MB）
}

class TimeoutException(Exception):
    """Custom exception for timeout"""
    pass

class NodeClient:
    """Enhanced node client with registration and heartbeat"""
    
    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url.rstrip('/')
        self.node_id = self._generate_node_id()
        self.is_registered = False
        self.last_heartbeat = 0
        self.task_count = 0
        self.error_count = 0
        self.running = True
        self.heartbeat_thread = None
        
        # 性能监控
        self.start_time = time.time()
        self.total_compute_time = 0
        
        print(f"Node ID: {self.node_id}")
        print(f"Server URL: {self.server_url}")
        print(f"Node Capacity: CPU={NODE_CAPACITY['cpu']} cores, "
              f"Memory={NODE_CAPACITY['memory']}MB")
    
    def _generate_node_id(self) -> str:
        """生成唯一的节点ID"""
        import socket
        import platform
        
        # 使用主机名 + 时间戳 + 随机数
        hostname = socket.gethostname()
        timestamp = int(time.time())
        random_suffix = os.urandom(2).hex()
        
        node_id = f"{hostname}-{timestamp}-{random_suffix}"
        return node_id[:32]  # 限制长度
    
    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        system_info = {
            "hostname": platform.node() if hasattr(platform, 'node') else "unknown",
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "idle_sense_available": IDLE_SENSE_AVAILABLE,
            "capacity": NODE_CAPACITY.copy()
        }
        
        if IDLE_SENSE_AVAILABLE:
            try:
                status = get_system_status()
                system_info.update({
                    "cpu_percent": status.get('cpu_percent', 0),
                    "memory_percent": status.get('memory_percent', 0),
                    "user_idle_time_sec": status.get('user_idle_time_sec', 0),
                    "is_screen_locked": status.get('is_screen_locked', False),
                    "is_charging": status.get('is_charging', True),
                    "platform_detail": status.get('platform', 'unknown')
                })
            except Exception as e:
                print(f"Warning: Failed to get detailed system status: {e}")
        
        return system_info
    
    def _calculate_available_resources(self) -> Dict[str, Any]:
        """计算可用资源"""
        try:
            if IDLE_SENSE_AVAILABLE:
                status = get_system_status()
                cpu_usage = status.get('cpu_percent', 0) / 100.0  # 转换为比例
                memory_usage = status.get('memory_percent', 0) / 100.0
            else:
                # 简化估算
                cpu_usage = 0.5  # 保守估计50%使用率
                memory_usage = 0.5
            
            # 计算可用资源
            available = {
                "cpu": max(0.1, NODE_CAPACITY["cpu"] * (1.0 - cpu_usage)),
                "memory": int(NODE_CAPACITY["memory"] * (1.0 - memory_usage)),
                "disk": NODE_CAPACITY["disk"]  # 假设磁盘总是足够
            }
            
            return available
        except Exception:
            # 出错时返回保守估计
            return {
                "cpu": NODE_CAPACITY["cpu"] * 0.5,
                "memory": NODE_CAPACITY["memory"] // 2,
                "disk": NODE_CAPACITY["disk"]
            }
    
    def _check_idle(self) -> Tuple[bool, Dict[str, Any]]:
        """检查系统是否空闲，返回空闲状态和详细信息"""
        if not IDLE_SENSE_AVAILABLE:
            # 没有idle_sense时保守返回空闲
            return True, {"reason": "idle_sense_not_available"}
        
        try:
            # 使用更严格的空闲检测
            is_system_idle = is_idle(
                idle_threshold_sec=60,    # 1分钟用户无活动
                cpu_threshold=30.0,       # CPU使用率低于30%
                memory_threshold=80.0     # 内存使用率低于80%
            )
            
            status = get_system_status()
            idle_info = {
                "cpu_percent": status.get('cpu_percent', 0),
                "memory_percent": status.get('memory_percent', 0),
                "user_idle_time_sec": status.get('user_idle_time_sec', 0),
                "is_screen_locked": status.get('is_screen_locked', False),
                "is_idle": is_system_idle,
                "reason": "idle" if is_system_idle else "busy"
            }
            
            return is_system_idle, idle_info
            
        except Exception as e:
            print(f"Warning: idle check failed: {e}")
            return True, {"reason": f"error: {str(e)[:50]}"}
    
    def register_node(self) -> bool:
        """向调度中心注册节点"""
        try:
            registration_data = {
                "node_id": self.node_id,
                "capacity": NODE_CAPACITY,
                "tags": {
                    "client_version": "2.0.0",
                    "idle_sense": IDLE_SENSE_AVAILABLE,
                    "platform": get_platform() if IDLE_SENSE_AVAILABLE else sys.platform
                }
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
                f"{self.server_url}/api/nodes/{self.node_id}/heartbeat",
                json=heartbeat_data,
                timeout=10
            )
            
            if response.status_code == 200:
                self.last_heartbeat = time.time()
                return True
            else:
                print(f"Heartbeat failed: {response.status_code}")
                # 如果心跳失败，尝试重新注册
                if response.status_code == 404:  # 节点未找到
                    self.is_registered = False
                    return self.register_node()
                return False
                
        except Exception as e:
            print(f"Heartbeat error: {e}")
            return False
    
    def heartbeat_loop(self):
        """心跳循环线程"""
        print(f"Heartbeat thread started (interval: {HEARTBEAT_INTERVAL}s)")
        
        while self.running:
            try:
                if not self.is_registered:
                    # 尝试重新注册
                    self.register_node()
                
                if self.is_registered:
                    success = self.send_heartbeat()
                    if not success:
                        print("Warning: Heartbeat failed, will retry")
                
            except Exception as e:
                print(f"Heartbeat loop error: {e}")
            
            # 等待下一次心跳
            for _ in range(HEARTBEAT_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)
        
        print("Heartbeat thread stopped")
    
    def safe_execute(self, code: str, timeout: int = TASK_TIMEOUT) -> str:
        """
        安全执行Python代码
        
        注意：这是一个简化的安全执行环境，生产环境需要更严格的沙箱
        """
        import subprocess
        import tempfile
        import resource
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # 设置资源限制
            def set_limits():
                # CPU时间限制（秒）
                resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 1))
                # 内存限制（MB）
                memory_limit = 512  # 512MB
                resource.setrlimit(resource.RLIMIT_AS, 
                                 (memory_limit * 1024 * 1024, memory_limit * 1024 * 1024))
            
            # 执行代码
            start_time = time.time()
            
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=set_limits if hasattr(resource, 'setrlimit') else None,
                env={**os.environ, 'PYTHONPATH': ''}  # 限制模块导入
            )
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if not output:
                    output = "Execution completed successfully (no output)"
                return f"Success ({execution_time:.1f}s): {output}"
            else:
                error_msg = result.stderr.strip() or f"Exit code {result.returncode}"
                return f"Error ({execution_time:.1f}s): {error_msg}"
                
        except subprocess.TimeoutExpired:
            return f"Error: Task execution timeout ({timeout}s)"
        except MemoryError:
            return "Error: Memory limit exceeded"
        except Exception as e:
            return f"Error: {str(e)[:100]}"
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def make_request(self, method: str, url: str, **kwargs) -> Optional[Dict[str, Any]]:
        """发送HTTP请求（带重试）"""
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.request(method, url, timeout=10, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    print(f"Request failed after {MAX_RETRIES} attempts: {e}")
                    return None
                print(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(2 ** attempt)  # 指数退避
        
        return None
    
    def fetch_task(self) -> Optional[Dict[str, Any]]:
        """获取任务（使用节点感知的端点）"""
        try:
            # 使用新端点，传递节点ID
            task_data = self.make_request(
                "GET", 
                f"{self.server_url}/get_task",
                params={"node_id": self.node_id}
            )
            
            # 如果新端点失败，回退到旧端点
            if not task_data or task_data.get("status") == "no_tasks":
                task_data = self.make_request("GET", f"{self.server_url}/get_task")
            
            return task_data
        except Exception as e:
            print(f"Error fetching task: {e}")
            return None
    
    def submit_result(self, task_id: int, result: str) -> bool:
        """提交任务结果（包含节点ID）"""
        try:
            result_data = {
                "task_id": task_id,
                "result": result,
                "node_id": self.node_id  # 新增：标识是哪个节点完成的
            }
            
            response = self.make_request(
                "POST",
                f"{self.server_url}/submit_result",
                json=result_data
            )
            
            return response is not None
        except Exception as e:
            print(f"Error submitting result: {e}")
            return False
    
    def run(self):
        """主运行循环"""
        print("=" * 60)
        print("Enhanced Idle Computing Node Client v2.0")
        print("=" * 60)
        
        # 显示系统信息
        system_info = self._get_system_info()
        print(f"Hostname: {system_info['hostname']}")
        print(f"Platform: {system_info['platform']}")
        print(f"Python: {system_info['python_version']}")
        print(f"Idle Sense: {'Available' if IDLE_SENSE_AVAILABLE else 'Not available'}")
        print(f"Node Capacity: CPU={NODE_CAPACITY['cpu']} cores, "
              f"Memory={NODE_CAPACITY['memory']}MB")
        print("-" * 60)
        
        # 注册节点
        if not self.register_node():
            print("Warning: Failed to register node, running in compatibility mode")
        
        # 启动心跳线程
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        print(f"Heartbeat thread started (every {HEARTBEAT_INTERVAL}s)")
        
        print("Node is running. Press Ctrl+C to stop.")
        print("-" * 60)
        
        try:
            while self.running:
                try:
                    current_time = datetime.now().strftime('%H:%M:%S')
                    
                    # 检查系统是否空闲
                    is_idle_state, idle_info = self._check_idle()
                    
                    if is_idle_state:
                        # 系统空闲，尝试获取任务
                        print(f"[{current_time}] System idle - checking for tasks...")
                        
                        task_data = self.fetch_task()
                        
                        if task_data and task_data.get("task_id") and task_data.get("code"):
                            task_id = task_data["task_id"]
                            code = task_data["code"]
                            
                            self.task_count += 1
                            print(f"  Task #{task_id} received (Total: {self.task_count})")
                            print(f"  Code length: {len(code)} characters")
                            
                            # 执行任务
                            start_time = time.time()
                            result = self.safe_execute(code)
                            execution_time = time.time() - start_time
                            
                            self.total_compute_time += execution_time
                            
                            # 提交结果
                            if self.submit_result(task_id, result):
                                print(f"  [SUCCESS] Completed in {execution_time:.1f}s")
                                # 显示结果摘要
                                result_preview = result[:80] + "..." if len(result) > 80 else result
                                print(f"  Result: {result_preview}")
                            else:
                                self.error_count += 1
                                print(f"  [ERROR] Failed to submit result")
                        else:
                            if task_data and task_data.get("status") == "no_tasks":
                                print(f"  No tasks available in scheduler")
                            else:
                                print(f"  No response from scheduler")
                    else:
                        # 系统忙
                        cpu_percent = idle_info.get("cpu_percent", 0)
                        memory_percent = idle_info.get("memory_percent", 0)
                        idle_time = idle_info.get("user_idle_time_sec", 0)
                        
                        print(f"[{current_time}] System busy - "
                              f"CPU: {cpu_percent}%, Memory: {memory_percent}%, "
                              f"Idle: {idle_time:.0f}s")
                    
                    # 显示状态统计
                    if self.task_count > 0 and self.task_count % 5 == 0:
                        uptime = time.time() - self.start_time
                        print(f"\n[Stats] Tasks: {self.task_count}, "
                              f"Errors: {self.error_count}, "
                              f"Uptime: {uptime:.0f}s, "
                              f"Compute: {self.total_compute_time:.0f}s")
                    
                    print("-" * 40)
                    
                    # 等待下一个检查周期
                    for _ in range(CHECK_INTERVAL):
                        if not self.running:
                            break
                        time.sleep(1)
                    
                except KeyboardInterrupt:
                    print("\n" + "=" * 60)
                    print("Client stopped by user")
                    break
                except Exception as e:
                    self.error_count += 1
                    error_time = datetime.now().strftime('%H:%M:%S')
                    print(f"[{error_time}] Unexpected error: {e}")
                    traceback.print_exc()
                    time.sleep(min(60, CHECK_INTERVAL * 2))
        
        finally:
            self.running = False
            
            # 等待心跳线程结束
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                print("Waiting for heartbeat thread to stop...")
                self.heartbeat_thread.join(timeout=5)
            
            # 显示最终统计
            print("\n" + "=" * 60)
            print("Client Summary:")
            print(f"  Node ID: {self.node_id}")
            print(f"  Tasks executed: {self.task_count}")
            print(f"  Total compute time: {self.total_compute_time:.1f}s")
            print(f"  Errors encountered: {self.error_count}")
            print(f"  Uptime: {time.time() - self.start_time:.0f}s")
            print(f"  Idle sense: {'Available' if IDLE_SENSE_AVAILABLE else 'Not available'}")
            print(f"  Registered: {'Yes' if self.is_registered else 'No'}")
            print("=" * 60)

def main():
    """主函数"""
    client = NodeClient()
    client.run()

if __name__ == "__main__":
    main()