"""
idle_sense/macos.py
macOS idle detector with cross-platform compatibility
"""

import time
import subprocess
import platform
import sys
from typing import Dict, Tuple, Optional

# 📝 修复：在模块级别添加平台检测，防止在非macOS系统导入
if platform.system() != "Darwin":
    raise ImportError(
        "MacOSIdleDetector can only be used on macOS systems. "
        f"Current platform: {platform.system()}\n"
        "For other platforms, use the appropriate module (windows.py for Windows)."
    )

# 📝 修改：添加psutil优雅降级
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available, battery and usage monitoring will be limited")

class MacOSIdleDetector:
    """macOS idle detector with enhanced compatibility"""
    
    def __init__(self, idle_threshold_sec: int = 300, 
                 cpu_threshold: float = 15.0,
                 memory_threshold: float = 70.0):
        self.idle_threshold_sec = idle_threshold_sec
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        
        # 📝 修复：再次确认平台，防止绕过ImportError的导入
        if platform.system() != "Darwin":
            raise RuntimeError("MacOSIdleDetector can only be used on macOS")
    
    def get_user_idle_time_sec(self) -> float:
        """Get user idle time in seconds with robust error handling"""
        try:
            # 📝 修复：添加兼容性参数处理
            subprocess_args = {
                'args': ["ioreg", "-c", "IOHIDSystem"],
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'text': True,
                'universal_newlines': True  # 兼容性参数
            }
            
            # Python 3.7+ 支持 capture_output
            if sys.version_info >= (3, 7):
                subprocess_args['capture_output'] = True
            else:
                subprocess_args['stdout'] = subprocess.PIPE
                subprocess_args['stderr'] = subprocess.PIPE
            
            result = subprocess.run(**subprocess_args, timeout=5)
            
            if result.returncode != 0:
                print(f"Warning: ioreg command failed: {result.stderr}")
                return 0.0
            
            for line in result.stdout.splitlines():
                if "HIDIdleTime" in line:
                    parts = line.split("=")
                    if len(parts) > 1:
                        ns_str = parts[1].strip().rstrip(";")
                        try:
                            idle_ns = int(ns_str)
                            return idle_ns / 1_000_000_000.0  # 纳秒转秒
                        except ValueError:
                            continue
            
            # 如果没有找到HIDIdleTime，使用备用方法
            return self._fallback_idle_time()
            
        except subprocess.TimeoutExpired:
            print("Warning: ioreg command timed out")
            return 0.0
        except FileNotFoundError:
            print("Warning: ioreg command not found")
            return 0.0
        except Exception as e:
            print(f"Warning: Failed to get idle time: {e}")
            return 0.0
    
    def _fallback_idle_time(self) -> float:
        """Fallback method to estimate idle time"""
        try:
            # 📝 备用方案：使用psutil的启动时间或简单启发式
            if PSUTIL_AVAILABLE:
                # 检查是否有用户进程活动
                for proc in psutil.process_iter(['name', 'username']):
                    try:
                        info = proc.info
                        if info['username'] and 'loginwindow' not in info['name'].lower():
                            # 有用户进程运行，可能不是完全空闲
                            return 0.0
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            return 300.0  # 默认返回5分钟
        except Exception:
            return 0.0
    
    def is_screen_saver_active(self) -> bool:
        """Check if screensaver is active with robust error handling"""
        try:
            # 📝 修复：使用更兼容的subprocess调用
            cmd = ["pgrep", "-x", "ScreenSaverEngine"]
            
            subprocess_args = {
                'args': cmd,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE
            }
            
            if sys.version_info >= (3, 7):
                subprocess_args['capture_output'] = True
            
            result = subprocess.run(**subprocess_args, timeout=3)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("Warning: pgrep command timed out")
            return False
        except FileNotFoundError:
            print("Warning: pgrep command not found")
            return False
        except Exception as e:
            print(f"Warning: Failed to check screensaver: {e}")
            return False
    
    def get_cpu_memory_usage(self) -> Tuple[float, float]:
        """Get CPU and memory usage with fallback"""
        if not PSUTIL_AVAILABLE:
            # 📝 修复：无psutil时返回默认值
            return 0.0, 0.0
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            return cpu_percent, memory_percent
        except Exception as e:
            print(f"Warning: Failed to get CPU/memory usage: {e}")
            return 0.0, 0.0
    
    def is_charging(self) -> bool:
        """Check if charging with fallback"""
        if not PSUTIL_AVAILABLE:
            # 📝 修复：无psutil时假设正在充电（安全默认）
            return True
        
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                # 无电池设备（如Mac Pro、iMac等）
                return True
            return battery.power_plugged
        except Exception as e:
            print(f"Warning: Failed to check charging status: {e}")
            return True  # 安全默认值
    
    def get_system_status(self) -> Dict:
        """Get system status with comprehensive error handling"""
        try:
            idle_time = self.get_user_idle_time_sec()
            cpu_percent, memory_percent = self.get_cpu_memory_usage()
            is_screen_saver = self.is_screen_saver_active()
            is_charging_val = self.is_charging()
            
            return {
                'timestamp': time.time(),
                'user_idle_time_sec': round(idle_time, 1),
                'cpu_percent': round(cpu_percent, 1),
                'memory_percent': round(memory_percent, 1),
                'is_screen_saver_active': is_screen_saver,
                'is_charging': is_charging_val,
                'is_user_idle': idle_time >= self.idle_threshold_sec,
                'is_cpu_idle': cpu_percent <= self.cpu_threshold,
                'is_memory_idle': memory_percent <= self.memory_threshold,
                'has_psutil': PSUTIL_AVAILABLE,
                'platform': platform.system(),
            }
        except Exception as e:
            # 📝 修复：整个状态获取过程的异常处理
            print(f"Error: Failed to get system status: {e}")
            return {
                'timestamp': time.time(),
                'error': str(e),
                'platform': platform.system(),
                'is_user_idle': False,
                'is_cpu_idle': False,
                'is_memory_idle': False,
            }
    
    def is_idle(self) -> bool:
        """Check if system is idle with error handling"""
        try:
            status = self.get_system_status()
            
            # 📝 修复：使用.get()避免KeyError
            if status.get('is_screen_saver_active', False):
                return status.get('is_cpu_idle', False)
            else:
                return (status.get('is_user_idle', False) and 
                        status.get('is_cpu_idle', False) and 
                        status.get('is_memory_idle', False))
        except Exception as e:
            print(f"Error: Failed to check idle status: {e}")
            return False

def is_idle(idle_threshold_sec: int = 300,
           cpu_threshold: float = 15.0,
           memory_threshold: float = 70.0) -> bool:
    """Check if system is idle"""
    try:
        detector = MacOSIdleDetector(idle_threshold_sec, 
                                     cpu_threshold, 
                                     memory_threshold)
        return detector.is_idle()
    except Exception as e:
        print(f"Error: Failed to create detector or check idle: {e}")
        return False

def get_system_status(idle_threshold_sec: int = 300,
                     cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> Dict:
    """Get system status"""
    try:
        detector = MacOSIdleDetector(idle_threshold_sec,
                                     cpu_threshold,
                                     memory_threshold)
        return detector.get_system_status()
    except Exception as e:
        return {
            'timestamp': time.time(),
            'error': f"Failed to initialize MacOSIdleDetector: {e}",
            'platform': platform.system(),
        }

# 📝 新增：诊断函数
def check_macos_tools() -> Dict[str, bool]:
    """Check macOS tool availability"""
    tools = ['ioreg', 'pgrep']
    availability = {}
    
    for tool in tools:
        try:
            result = subprocess.run(['which', tool], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=2)
            availability[tool] = result.returncode == 0
        except Exception:
            availability[tool] = False
    
    availability['psutil_available'] = PSUTIL_AVAILABLE
    availability['platform'] = platform.system()
    
    return availability
