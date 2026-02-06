"""
idle_sense/macos.py
macOS idle detector - simplified and robust version
借鉴自多个开源项目的成熟代码片段
"""

import time
import subprocess
import platform
import re
from typing import Dict, Tuple

# 平台检测：仅在macOS上允许导入
if platform.system() != "Darwin":
    raise ImportError(f"This module is for macOS only. Current system: {platform.system()}")

# psutil 作为可选依赖，用于获取CPU/内存使用率
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class MacOSIdleDetector:
    """macOS idle detector with reliable ioreg-based idle time detection"""
    
    def __init__(self, idle_threshold_sec: int = 300, 
                 cpu_threshold: float = 15.0,
                 memory_threshold: float = 70.0):
        self.idle_threshold_sec = idle_threshold_sec
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
    
    def get_user_idle_time_sec(self) -> float:
        """
        Get user idle time in seconds using ioreg command.
        借鉴自开源项目：使用正则表达式可靠解析 HIDIdleTime
        """
        try:
            # 借鉴点1：使用 capture_output 简化代码 (Python 3.7+)
            result = subprocess.run(
                ['ioreg', '-c', 'IOHIDSystem'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                # 命令失败，返回0（保守假设：非空闲）
                return 0.0
            
            # 借鉴点2：使用正则表达式精确匹配 HIDIdleTime
            # 匹配格式: "HIDIdleTime" = 1234567890
            match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', result.stdout)
            
            if match:
                # 借鉴点3：将纳秒直接转换为秒
                idle_ns = int(match.group(1))
                return idle_ns / 1_000_000_000.0
            else:
                # 未找到 HIDIdleTime，系统可能刚启动或异常
                return 0.0
                
        except subprocess.TimeoutExpired:
            # 命令超时
            return 0.0
        except FileNotFoundError:
            # ioreg 命令不存在（极不可能在macOS上发生）
            return 0.0
        except Exception:
            # 其他任何异常
            return 0.0
    
    def get_cpu_memory_usage(self) -> Tuple[float, float]:
        """Get CPU and memory usage with psutil fallback"""
        if not PSUTIL_AVAILABLE:
            # 无 psutil，返回保守值（假设低使用率）
            return 0.0, 0.0
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            return cpu_percent, memory_percent
        except Exception:
            # psutil 调用失败
            return 0.0, 0.0
    
    def is_charging(self) -> bool:
        """Check if charging with psutil fallback"""
        if not PSUTIL_AVAILABLE:
            # 无 psutil，保守假设正在充电（允许执行任务）
            return True
        
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                # 无电池设备（如 iMac, Mac Pro）
                return True
            return battery.power_plugged
        except Exception:
            # 异常时保守假设充电中
            return True
    
    def get_system_status(self) -> Dict:
        """
        Get complete system status.
        借鉴自现有代码结构，保持接口一致性。
        """
        idle_time = self.get_user_idle_time_sec()
        cpu_percent, memory_percent = self.get_cpu_memory_usage()
        is_charging_val = self.is_charging()
        
        return {
            'timestamp': time.time(),
            'user_idle_time_sec': round(idle_time, 1),
            'cpu_percent': round(cpu_percent, 1),
            'memory_percent': round(memory_percent, 1),
            'is_charging': is_charging_val,
            'is_user_idle': idle_time >= self.idle_threshold_sec,
            'is_cpu_idle': cpu_percent <= self.cpu_threshold,
            'is_memory_idle': memory_percent <= self.memory_threshold,
            'has_psutil': PSUTIL_AVAILABLE,
            'platform': 'macOS',
        }
    
    def is_idle(self) -> bool:
        """
        Check if system is idle.
        核心逻辑：用户空闲且CPU/内存使用率低
        """
        status = self.get_system_status()
        return (status['is_user_idle'] and 
                status['is_cpu_idle'] and 
                status['is_memory_idle'])

# 模块级函数，保持与 core.py 的兼容性
def is_idle(idle_threshold_sec: int = 300,
           cpu_threshold: float = 15.0,
           memory_threshold: float = 70.0) -> bool:
    """Check if system is idle - 模块公共接口"""
    detector = MacOSIdleDetector(idle_threshold_sec, 
                                 cpu_threshold, 
                                 memory_threshold)
    return detector.is_idle()

def get_system_status(idle_threshold_sec: int = 300,
                     cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> Dict:
    """Get system status - 模块公共接口"""
    detector = MacOSIdleDetector(idle_threshold_sec,
                                 cpu_threshold,
                                 memory_threshold)
    return detector.get_system_status()

# 借鉴自开源项目的诊断工具
def check_macos_capabilities() -> Dict[str, bool]:
    """检查系统工具可用性（借鉴自诊断代码）"""
    capabilities = {
        'ioreg_available': False,
        'psutil_available': PSUTIL_AVAILABLE,
        'platform_macOS': platform.system() == 'Darwin'
    }
    
    try:
        # 检查 ioreg 命令
        result = subprocess.run(['which', 'ioreg'], 
                              capture_output=True, 
                              text=True,
                              timeout=2)
        capabilities['ioreg_available'] = result.returncode == 0
    except Exception:
        capabilities['ioreg_available'] = False
    
    return capabilities
