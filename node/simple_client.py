#!/usr/bin/env python3
"""
全兼容闲置计算节点客户端
支持：游戏本、轻薄本、台式机
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
import socket
import threading
import json
import traceback
import platform
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

def log(msg):
    if not SILENT_MODE:
        print(msg)

# 尝试导入psutil，如果没有就使用简化版本
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    log("提示: psutil未安装，将使用简化系统检测")
    log("建议安装: pip install psutil")
    PSUTIL_AVAILABLE = False
    import random

# 配置
SERVER_URL = "http://localhost:8000"
CHECK_INTERVAL = 30
HEARTBEAT_INTERVAL = 20
TASK_TIMEOUT = 300
MAX_RETRIES = 3

class NodeClient:
    """全兼容节点客户端 - 支持所有电脑类型"""
    
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
        
        # 设备类型检测
        self.device_type = self._detect_device_type()
        
        # 根据设备类型设置容量
        self.capacity = self._get_capacity_by_device_type()
        
        log(f"[初始化] 节点ID: {self.node_id}")
        log(f"[初始化] 设备类型: {self.device_type}")
        log(f"[初始化] 容量配置: CPU={self.capacity['cpu']}核, "
              f"内存={self.capacity['memory']}MB, 磁盘={self.capacity['disk']}MB")
        
        # ===== 启动成功视觉反馈 =====
        if not SILENT_MODE and sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"闲置计算节点已启动\n节点ID: {self.node_id}\n设备类型: {self.device_type}",
                    "闲置计算加速器 - 通用版",
                    0x00000040
                )
            except:
                pass
        # ===== 结束 =====
    
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
        hostname = socket.gethostname()
        timestamp = int(time.time())
        random_suffix = os.urandom(4).hex()
        node_id = f"{hostname}-{timestamp}-{random_suffix}"
        node_id = node_id[:32]  # 限制长度
        
        # 保存到用户目录
        try:
            with open(id_file, 'w') as f:
                f.write(node_id)
            log(f"[节点ID] 生成并保存新ID: {node_id}")
        except Exception as e:
            log(f"[警告] 无法保存节点ID: {e}")
    
        return node_id
    
    def _detect_device_type(self) -> str:
        """检测设备类型：游戏本、轻薄本、台式机"""
        try:
            if PSUTIL_AVAILABLE:
                cpu_cores = psutil.cpu_count(logical=True) or 4
                memory_gb = psutil.virtual_memory().total / (1024**3)
            else:
                cpu_cores = 4
                memory_gb = 8.0
            
            if cpu_cores >= 8 and memory_gb >= 16:
                return "gaming_laptop"
            elif cpu_cores <= 4 and memory_gb <= 8:
                return "ultrabook"
            else:
                return "desktop"
        except:
            return "unknown"
    
    def _get_capacity_by_device_type(self) -> Dict[str, float]:
        capacities = {
            "gaming_laptop": {
                "cpu": 4.0,
                "memory": 8192,
                "disk": 30000
            },
            "ultrabook": {
                "cpu": 2.0,
                "memory": 4096,
                "disk": 10000
            },
            "desktop": {
                "cpu": 6.0,
                "memory": 12288,
                "disk": 50000
            },
            "unknown": {
                "cpu": 2.0,
                "memory": 2048,
                "disk": 10000
            }
        }
        return capacities.get(self.device_type, capacities["unknown"])
    
    def _get_system_info(self) -> Dict[str, Any]:
        system_info = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "device_type": self.device_type,
            "capacity": self.capacity.copy()
        }
        
        if PSUTIL_AVAILABLE:
            try:
                cpu_percent = psutil.cpu_percent(interval=0.5)
                memory = psutil.virtual_memory()
                system_info.update({
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "cpu_cores": psutil.cpu_count(logical=True),
                    "memory_total_gb": memory.total / (1024**3),
                    "memory_available_gb": memory.available / (1024**3)
                })
            except:
                pass
        
        return system_info
    
    def _calculate_available_resources(self) -> Dict[str, Any]:
        try:
            if PSUTIL_AVAILABLE:
                cpu_percent = psutil.cpu_percent(interval=0.5)
                memory = psutil.virtual_memory()
                
                cpu_safe_margin = 0.3
                memory_safe_margin = 0.4
                
                cpu_available = max(0.5, self.capacity["cpu"] * (1 - cpu_percent/100 - cpu_safe_margin))
                memory_available = int(self.capacity["memory"] * (1 - memory.percent/100 - memory_safe_margin))
                
                available = {
                    "cpu": cpu_available,
                    "memory": max(512, memory_available),
                    "disk": self.capacity["disk"] * 0.5
                }
            else:
                available = {
                    "cpu": self.capacity["cpu"] * 0.3,
                    "memory": int(self.capacity["memory"] * 0.3),
                    "disk": self.capacity["disk"] * 0.3
                }
            return available
        except:
            return {
                "cpu": 0.5,
                "memory": 512,
                "disk": 1000
            }
    
    def _check_idle(self) -> Tuple[bool, Dict[str, Any]]:
        try:
            if not PSUTIL_AVAILABLE:
                return True, {
                    "cpu_percent": 30.0,
                    "memory_percent": 50.0,
                    "user_idle_time_sec": 300,
                    "is_screen_locked": False,
                    "is_idle": True,
                    "reason": "no_psutil_assume_idle"
                }
            
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            
            idle_thresholds = {
                "gaming_laptop": {
                    "cpu_threshold": 75.0,
                    "memory_threshold": 85.0
                },
                "ultrabook": {
                    "cpu_threshold": 70.0,
                    "memory_threshold": 80.0
                },
                "desktop": {
                    "cpu_threshold": 80.0,
                    "memory_threshold": 90.0
                }
            }
            
            thresholds = idle_thresholds.get(self.device_type, idle_thresholds["desktop"])
            ABSOLUTE_CPU_LIMIT = 90.0
            ABSOLUTE_MEMORY_LIMIT = 95.0
            
            is_system_idle = True
            
            if cpu_percent > thresholds["cpu_threshold"]:
                is_system_idle = False
                log(f"[空闲检测] CPU使用率 {cpu_percent}% > {thresholds['cpu_threshold']}%")
            
            if memory.percent > thresholds["memory_threshold"]:
                is_system_idle = False
                log(f"[空闲检测] 内存使用率 {memory.percent}% > {thresholds['memory_threshold']}%")
            
            if cpu_percent > ABSOLUTE_CPU_LIMIT or memory.percent > ABSOLUTE_MEMORY_LIMIT:
                is_system_idle = False
                log(f"[安全保护] 资源过高，暂停计算: CPU={cpu_percent}%, 内存={memory.percent}%")
            
            idle_info = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "user_idle_time_sec": 300,
                "is_screen_locked": False,
                "is_idle": is_system_idle,
                "reason": "idle" if is_system_idle else f"busy_cpu{cpu_percent}_mem{memory.percent}",
                "device_type": self.device_type
            }
            
            if is_system_idle:
                log(f"[状态] 设备空闲 - {self.device_type}: CPU{cpu_percent}%, 内存{memory.percent}%")
            else:
                log(f"[状态] 设备忙碌 - {self.device_type}: CPU{cpu_percent}%, 内存{memory.percent}%")
            
            return is_system_idle, idle_info
        except Exception as e:
            log(f"[警告] 空闲检测失败: {e}")
            return True, {
                "cpu_percent": 50.0,
                "memory_percent": 60.0,
                "user_idle_time_sec": 60,
                "is_screen_locked": False,
                "is_idle": True,
                "reason": f"error_fallback: {str(e)[:30]}",
                "device_type": self.device_type
            }
    
    def register_node(self) -> bool:
        try:
            registration_data = {
                "node_id": self.node_id,
                "capacity": self.capacity,
                "device_type": self.device_type,
                "tags": {
                    "client_version": "3.0-compatible",
                    "psutil_available": PSUTIL_AVAILABLE,
                    "platform": platform.system()
                }
            }
            
            response = requests.post(
                f"{self.server_url}/api/nodes/register",
                json=registration_data,
                timeout=10
            )
            
            if response.status_code == 200:
                self.is_registered = True
                log(f"[成功] 节点注册成功: {self.node_id} ({self.device_type})")
                return True
            else:
                log(f"[错误] 注册失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            log(f"[错误] 注册异常: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
        try:
            is_idle_state, idle_info = self._check_idle()
            available_resources = self._calculate_available_resources()
            
            heartbeat_data = {
                "node_id": self.node_id,
                "device_type": self.device_type,
                "current_load": {
                    "cpu_usage": idle_info.get("cpu_percent", 0),
                    "memory_usage": idle_info.get("memory_percent", 0)
                },
                "is_idle": is_idle_state,
                "available_resources": available_resources,
                "idle_info": idle_info
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
                log(f"心跳失败: {response.status_code}")
                if response.status_code == 404:
                    self.is_registered = False
                    return self.register_node()
                return False
        except Exception as e:
            log(f"心跳异常: {e}")
            return False
    
    def heartbeat_loop(self):
        log(f"心跳线程启动 (间隔: {HEARTBEAT_INTERVAL}秒)")
        while self.running:
            try:
                if not self.is_registered:
                    self.register_node()
                if self.is_registered:
                    success = self.send_heartbeat()
                    if not success:
                        log("警告: 心跳失败，将重试")
            except Exception as e:
                log(f"心跳循环异常: {e}")
            
            for _ in range(HEARTBEAT_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)
        log("心跳线程停止")
    
    def safe_execute(self, code: str, timeout: int = TASK_TIMEOUT) -> str:
        try:
            import subprocess
            import tempfile
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                start_time = time.time()
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=os.path.dirname(temp_file)
                )
                execution_time = time.time() - start_time
                
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if not output:
                        output = "执行成功（无输出）"
                    return f"成功 ({execution_time:.1f}秒): {output[:200]}"
                else:
                    error_msg = result.stderr or "未知错误"
                    return f"错误: {error_msg[:200]}"
            finally:
                try:
                    os.unlink(temp_file)
                except:
                    pass
        except subprocess.TimeoutExpired:
            return f"错误: 执行超时（{timeout}秒）"
        except Exception as e:
            return f"错误: 执行异常 - {str(e)[:100]}"
    
    def fetch_task(self) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(
                f"{self.server_url}/get_task",
                params={"node_id": self.node_id, "device_type": self.device_type},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            log(f"获取任务失败: {e}")
            return None
    
    def submit_result(self, task_id: int, result: str) -> bool:
        try:
            result_data = {
                "task_id": task_id,
                "result": result,
                "node_id": self.node_id,
                "device_type": self.device_type
            }
            response = requests.post(
                f"{self.server_url}/submit_result",
                json=result_data,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            log(f"提交结果失败: {e}")
            return False
    
    def run(self):
        log("=" * 60)
        log("全兼容闲置计算节点 v3.0")
        log(f"设备类型: {self.device_type}")
        log("=" * 60)
        
        system_info = self._get_system_info()
        log(f"主机名: {system_info['hostname']}")
        log(f"平台: {system_info['platform']}")
        log(f"Python: {system_info['python_version']}")
        log(f"设备容量: CPU={self.capacity['cpu']}核, 内存={self.capacity['memory']}MB")
        log("-" * 60)
        
        if not self.register_node():
            log("警告: 节点注册失败，以兼容模式运行")
        
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        log("节点运行中。按 Ctrl+C 停止。")
        log("-" * 60)
        
        try:
            while self.running:
                try:
                    current_time = datetime.now().strftime('%H:%M:%S')
                    is_idle_state, idle_info = self._check_idle()
                    
                    if is_idle_state:
                        log(f"[{current_time}] 系统空闲 - 检查任务...")
                        task_data = self.fetch_task()
                        
                        if task_data and task_data.get("task_id") and task_data.get("code"):
                            task_id = task_data["task_id"]
                            code = task_data["code"]
                            
                            self.task_count += 1
                            log(f"  任务 #{task_id} (总计: {self.task_count})")
                            log(f"  代码长度: {len(code)} 字符")
                            
                            start_time = time.time()
                            result = self.safe_execute(code)
                            execution_time = time.time() - start_time
                            self.total_compute_time += execution_time
                            
                            if self.submit_result(task_id, result):
                                log(f"  [成功] 用时 {execution_time:.1f}秒")
                                result_preview = result[:80] + "..." if len(result) > 80 else result
                                log(f"  结果: {result_preview}")
                            else:
                                self.error_count += 1
                                log(f"  [错误] 提交失败")
                        else:
                            if task_data and task_data.get("status") == "no_tasks":
                                log(f"  调度器暂无任务")
                            else:
                                log(f"  无任务响应")
                    else:
                        cpu_percent = idle_info.get("cpu_percent", 0)
                        memory_percent = idle_info.get("memory_percent", 0)
                        log(f"[{current_time}] 系统忙碌 - CPU: {cpu_percent}%, 内存: {memory_percent}%")
                    
                    if self.task_count > 0 and self.task_count % 3 == 0:
                        uptime = time.time() - self.start_time
                        log(f"\n[统计] 任务: {self.task_count}, 错误: {self.error_count}, 运行: {uptime:.0f}秒, 计算: {self.total_compute_time:.0f}秒")
                    
                    log("-" * 40)
                    
                    for _ in range(CHECK_INTERVAL):
                        if not self.running:
                            break
                        time.sleep(1)
                    
                except KeyboardInterrupt:
                    log("\n" + "=" * 60)
                    log("用户停止节点")
                    break
                except Exception as e:
                    self.error_count += 1
                    error_time = datetime.now().strftime('%H:%M:%S')
                    log(f"[{error_time}] 意外错误: {e}")
                    time.sleep(min(30, CHECK_INTERVAL))
        finally:
            self.running = False
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                log("等待心跳线程停止...")
                self.heartbeat_thread.join(timeout=5)
            
            log("\n" + "=" * 60)
            log("节点总结:")
            log(f"  节点ID: {self.node_id}")
            log(f"  设备类型: {self.device_type}")
            log(f"  执行任务: {self.task_count}")
            log(f"  总计算时间: {self.total_compute_time:.1f}秒")
            log(f"  错误次数: {self.error_count}")
            log(f"  运行时间: {time.time() - self.start_time:.0f}秒")
            log("=" * 60)

def main():
    client = NodeClient()
    client.run()

if __name__ == "__main__":
    main()