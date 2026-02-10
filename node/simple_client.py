"""
node/simple_client.py
全兼容闲置计算节点客户端
支持：游戏本、轻薄本、台式机
要求：只使用Python标准库 + psutil（最小依赖）
"""

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

# 尝试导入psutil，如果没有就使用简化版本
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    print("提示: psutil未安装，将使用简化系统检测")
    print("建议安装: pip install psutil")
    PSUTIL_AVAILABLE = False
    # 创建简化替代函数
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
        
        print(f"[初始化] 节点ID: {self.node_id}")
        print(f"[初始化] 设备类型: {self.device_type}")
        print(f"[初始化] 容量配置: CPU={self.capacity['cpu']}核, "
              f"内存={self.capacity['memory']}MB, 磁盘={self.capacity['disk']}MB")
    
    def _generate_node_id(self) -> str:
        """生成节点ID"""
        import random
        
        # 使用主机名 + 时间戳 + 随机数
        hostname = socket.gethostname()
        timestamp = int(time.time())
        random_suffix = random.randint(1000, 9999)
        
        node_id = f"{hostname}-{timestamp}-{random_suffix}"
        return node_id[:32]
    
    def _detect_device_type(self) -> str:
        """检测设备类型：游戏本、轻薄本、台式机"""
        try:
            # 基于系统信息判断
            system_info = platform.uname()
            
            # 获取CPU核心数
            if PSUTIL_AVAILABLE:
                cpu_cores = psutil.cpu_count(logical=True) or 4
            else:
                cpu_cores = 4  # 默认值
            
            # 获取内存大小
            if PSUTIL_AVAILABLE:
                memory_gb = psutil.virtual_memory().total / (1024**3)
            else:
                memory_gb = 8.0  # 默认8GB
            
            # 判断逻辑
            if cpu_cores >= 8 and memory_gb >= 16:
                return "gaming_laptop"  # 游戏本
            elif cpu_cores <= 4 and memory_gb <= 8:
                return "ultrabook"      # 轻薄本
            else:
                return "desktop"        # 台式机/性能本
                
        except:
            return "unknown"
    
    def _get_capacity_by_device_type(self) -> Dict[str, float]:
        """根据设备类型设置容量（保守估计）"""
        capacities = {
            "gaming_laptop": {
                "cpu": 4.0,      # 游戏本：最多用4核（总核数的一半）
                "memory": 8192,  # 最多用8GB
                "disk": 30000    # 30GB
            },
            "ultrabook": {
                "cpu": 2.0,      # 轻薄本：最多用2核
                "memory": 4096,  # 最多用4GB
                "disk": 10000    # 10GB
            },
            "desktop": {
                "cpu": 6.0,      # 台式机：最多用6核
                "memory": 12288, # 最多用12GB
                "disk": 50000    # 50GB
            },
            "unknown": {
                "cpu": 2.0,      # 未知设备：保守估计
                "memory": 2048,
                "disk": 10000
            }
        }
        
        return capacities.get(self.device_type, capacities["unknown"])
    
    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息（兼容版）"""
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
            except Exception as e:
                print(f"获取系统信息失败: {e}")
        
        return system_info
    
    def _calculate_available_resources(self) -> Dict[str, Any]:
        """计算可用资源（智能调节）"""
        try:
            if PSUTIL_AVAILABLE:
                cpu_percent = psutil.cpu_percent(interval=0.5)
                memory = psutil.virtual_memory()
                
                # 安全余量：留出足够资源给用户
                cpu_safe_margin = 0.3  # 留出30%CPU
                memory_safe_margin = 0.4  # 留出40%内存
                
                # 计算可用资源（考虑安全余量）
                cpu_available = max(0.5, self.capacity["cpu"] * (1 - cpu_percent/100 - cpu_safe_margin))
                memory_available = int(self.capacity["memory"] * (1 - memory.percent/100 - memory_safe_margin))
                
                available = {
                    "cpu": cpu_available,
                    "memory": max(512, memory_available),  # 最少512MB
                    "disk": self.capacity["disk"] * 0.5  # 只用一半磁盘
                }
            else:
                # 无psutil时的保守估计
                available = {
                    "cpu": self.capacity["cpu"] * 0.3,  # 只用30%
                    "memory": int(self.capacity["memory"] * 0.3),
                    "disk": self.capacity["disk"] * 0.3
                }
            
            return available
            
        except Exception:
            # 出错时返回最小资源
            return {
                "cpu": 0.5,
                "memory": 512,
                "disk": 1000
            }
    
    def _check_idle(self) -> Tuple[bool, Dict[str, Any]]:
        """智能空闲检测（三设备兼容）"""
        try:
            if not PSUTIL_AVAILABLE:
                # 无psutil时，假设设备可用（但保守）
                return True, {
                    "cpu_percent": 30.0,
                    "memory_percent": 50.0,
                    "user_idle_time_sec": 300,
                    "is_screen_locked": False,
                    "is_idle": True,
                    "reason": "no_psutil_assume_idle"
                }
            
            # 获取系统状态
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            
            # 🎯 根据不同设备类型设置不同阈值
            idle_thresholds = {
                "gaming_laptop": {
                    "idle_time": 25,      # 游戏本：25秒无操作
                    "cpu_threshold": 75.0, # CPU低于75%
                    "memory_threshold": 85.0 # 内存低于85%
                },
                "ultrabook": {
                    "idle_time": 15,      # 轻薄本：15秒无操作
                    "cpu_threshold": 70.0, # CPU低于70%（更保守）
                    "memory_threshold": 80.0 # 内存低于80%
                },
                "desktop": {
                    "idle_time": 30,      # 台式机：30秒无操作
                    "cpu_threshold": 80.0, # CPU低于80%
                    "memory_threshold": 90.0 # 内存低于90%
                }
            }
            
            thresholds = idle_thresholds.get(self.device_type, idle_thresholds["desktop"])
            
            # 🛡️ 安全保护：绝对阈值
            ABSOLUTE_CPU_LIMIT = 90.0    # CPU绝对不能超过90%
            ABSOLUTE_MEMORY_LIMIT = 95.0 # 内存绝对不能超过95%
            
            # 判断是否空闲
            is_system_idle = True
            
            if cpu_percent > thresholds["cpu_threshold"]:
                is_system_idle = False
                print(f"[空闲检测] CPU使用率 {cpu_percent}% > {thresholds['cpu_threshold']}%")
            
            if memory.percent > thresholds["memory_threshold"]:
                is_system_idle = False
                print(f"[空闲检测] 内存使用率 {memory.percent}% > {thresholds['memory_threshold']}%")
            
            # 安全保护：即使空闲，如果资源过高也要暂停
            if cpu_percent > ABSOLUTE_CPU_LIMIT or memory.percent > ABSOLUTE_MEMORY_LIMIT:
                is_system_idle = False
                print(f"[安全保护] 资源过高，暂停计算: CPU={cpu_percent}%, 内存={memory.percent}%")
            
            idle_info = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "user_idle_time_sec": 300,  # 简化：假设用户空闲
                "is_screen_locked": False,
                "is_idle": is_system_idle,
                "reason": "idle" if is_system_idle else f"busy_cpu{cpu_percent}_mem{memory.percent}",
                "device_type": self.device_type
            }
            
            if is_system_idle:
                print(f"[状态] 设备空闲 - {self.device_type}: CPU{cpu_percent}%, 内存{memory.percent}%")
            else:
                print(f"[状态] 设备忙碌 - {self.device_type}: CPU{cpu_percent}%, 内存{memory.percent}%")
            
            return is_system_idle, idle_info
            
        except Exception as e:
            print(f"[警告] 空闲检测失败: {e}")
            # 出错时保守返回空闲（但标记为错误）
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
        """注册节点"""
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
                print(f"[成功] 节点注册成功: {self.node_id} ({self.device_type})")
                return True
            else:
                print(f"[错误] 注册失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[错误] 注册异常: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
        """发送心跳"""
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
                print(f"心跳失败: {response.status_code}")
                if response.status_code == 404:  # 节点未找到
                    self.is_registered = False
                    return self.register_node()
                return False
                
        except Exception as e:
            print(f"心跳异常: {e}")
            return False
    
    def heartbeat_loop(self):
        """心跳循环"""
        print(f"心跳线程启动 (间隔: {HEARTBEAT_INTERVAL}秒)")
        
        while self.running:
            try:
                if not self.is_registered:
                    self.register_node()
                
                if self.is_registered:
                    success = self.send_heartbeat()
                    if not success:
                        print("警告: 心跳失败，将重试")
                
            except Exception as e:
                print(f"心跳循环异常: {e}")
            
            # 等待
            for _ in range(HEARTBEAT_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)
        
        print("心跳线程停止")
    
    def safe_execute(self, code: str, timeout: int = TASK_TIMEOUT) -> str:
        """安全执行代码（简化版）"""
        try:
            # 创建本地执行环境
            import subprocess
            import tempfile
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # 执行代码（限制资源）
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
                # 清理临时文件
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            return f"错误: 执行超时（{timeout}秒）"
        except Exception as e:
            return f"错误: 执行异常 - {str(e)[:100]}"
    
    def fetch_task(self) -> Optional[Dict[str, Any]]:
        """获取任务"""
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
            print(f"获取任务失败: {e}")
            return None
    
    def submit_result(self, task_id: int, result: str) -> bool:
        """提交结果"""
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
            print(f"提交结果失败: {e}")
            return False
    
    def run(self):
        """主运行循环"""
        print("=" * 60)
        print("全兼容闲置计算节点 v3.0")
        print(f"设备类型: {self.device_type}")
        print("=" * 60)
        
        # 显示系统信息
        system_info = self._get_system_info()
        print(f"主机名: {system_info['hostname']}")
        print(f"平台: {system_info['platform']}")
        print(f"Python: {system_info['python_version']}")
        print(f"设备容量: CPU={self.capacity['cpu']}核, 内存={self.capacity['memory']}MB")
        print("-" * 60)
        
        # 注册节点
        if not self.register_node():
            print("警告: 节点注册失败，以兼容模式运行")
        
        # 启动心跳
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        print("节点运行中。按 Ctrl+C 停止。")
        print("-" * 60)
        
        try:
            while self.running:
                try:
                    current_time = datetime.now().strftime('%H:%M:%S')
                    
                    # 检查空闲状态
                    is_idle_state, idle_info = self._check_idle()
                    
                    if is_idle_state:
                        print(f"[{current_time}] 系统空闲 - 检查任务...")
                        
                        task_data = self.fetch_task()
                        
                        if task_data and task_data.get("task_id") and task_data.get("code"):
                            task_id = task_data["task_id"]
                            code = task_data["code"]
                            
                            self.task_count += 1
                            print(f"  任务 #{task_id} (总计: {self.task_count})")
                            print(f"  代码长度: {len(code)} 字符")
                            
                            # 执行任务
                            start_time = time.time()
                            result = self.safe_execute(code)
                            execution_time = time.time() - start_time
                            
                            self.total_compute_time += execution_time
                            
                            # 提交结果
                            if self.submit_result(task_id, result):
                                print(f"  [成功] 用时 {execution_time:.1f}秒")
                                result_preview = result[:80] + "..." if len(result) > 80 else result
                                print(f"  结果: {result_preview}")
                            else:
                                self.error_count += 1
                                print(f"  [错误] 提交失败")
                        else:
                            if task_data and task_data.get("status") == "no_tasks":
                                print(f"  调度器暂无任务")
                            else:
                                print(f"  无任务响应")
                    else:
                        cpu_percent = idle_info.get("cpu_percent", 0)
                        memory_percent = idle_info.get("memory_percent", 0)
                        print(f"[{current_time}] 系统忙碌 - CPU: {cpu_percent}%, 内存: {memory_percent}%")
                    
                    # 显示统计
                    if self.task_count > 0 and self.task_count % 3 == 0:
                        uptime = time.time() - self.start_time
                        print(f"\n[统计] 任务: {self.task_count}, "
                              f"错误: {self.error_count}, "
                              f"运行: {uptime:.0f}秒, "
                              f"计算: {self.total_compute_time:.0f}秒")
                    
                    print("-" * 40)
                    
                    # 等待
                    for _ in range(CHECK_INTERVAL):
                        if not self.running:
                            break
                        time.sleep(1)
                    
                except KeyboardInterrupt:
                    print("\n" + "=" * 60)
                    print("用户停止节点")
                    break
                except Exception as e:
                    self.error_count += 1
                    error_time = datetime.now().strftime('%H:%M:%S')
                    print(f"[{error_time}] 意外错误: {e}")
                    time.sleep(min(30, CHECK_INTERVAL))
        
        finally:
            self.running = False
            
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                print("等待心跳线程停止...")
                self.heartbeat_thread.join(timeout=5)
            
            # 最终统计
            print("\n" + "=" * 60)
            print("节点总结:")
            print(f"  节点ID: {self.node_id}")
            print(f"  设备类型: {self.device_type}")
            print(f"  执行任务: {self.task_count}")
            print(f"  总计算时间: {self.total_compute_time:.1f}秒")
            print(f"  错误次数: {self.error_count}")
            print(f"  运行时间: {time.time() - self.start_time:.0f}秒")
            print("=" * 60)

def main():
    """主函数"""
    client = NodeClient()
    client.run()

if __name__ == "__main__":
    main()