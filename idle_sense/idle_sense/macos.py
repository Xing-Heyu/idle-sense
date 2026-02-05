"""
idle_sense/macos.py
macOS系统闲置检测器 - 最终验证版
"""

import time
import subprocess
import platform
from typing import Dict, Tuple
import psutil

class MacOSIdleDetector:
    """macOS系统闲置检测器"""
    
    def __init__(self, idle_threshold_sec: int = 300, cpu_threshold: float = 15.0,
                 memory_threshold: float = 70.0):
        # 验证系统
        if platform.system() != "Darwin":
            raise RuntimeError("此模块仅适用于macOS")
            
        self.idle_threshold_sec = idle_threshold_sec
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
    
    def get_user_idle_time_sec(self) -> float:
        """获取用户空闲时间（秒）"""
        try:
            # 使用ioreg命令
            cmd = ["ioreg", "-c", "IOHIDSystem"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            for line in result.stdout.splitlines():
                if "HIDIdleTime" in line:
                    # 提取纳秒值
                    parts = line.split("=")
                    if len(parts) > 1:
                        ns_str = parts[1].strip().rstrip(";")
                        try:
                            idle_ns = int(ns_str)
                            return idle_ns / 1_000_000_000.0
                        except ValueError:
                            pass
        except:
            pass
        
        return 0.0  # 如果失败，返回0
    
    def is_screen_saver_active(self) -> bool:
        """检查屏幕保护是否激活"""
        try:
            cmd = ["pgrep", "-x", "ScreenSaverEngine"]
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        except:
            return False
    
    def get_cpu_memory_usage(self) -> Tuple[float, float]:
        """获取CPU和内存使用率"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
        return cpu_percent, memory_percent
    
    def is_charging(self) -> bool:
        """检测是否在充电"""
        try:
            battery = psutil.sensors_battery()
            if battery:
                return battery.power_plugged
            return True
        except:
            return True
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        idle_time = self.get_user_idle_time_sec()
        cpu_percent, memory_percent = self.get_cpu_memory_usage()
        is_screen_saver = self.is_screen_saver_active()
        is_charging_val = self.is_charging()
        
        return {
            'timestamp': time.time(),
            'user_idle_time_sec': idle_time,
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'is_screen_saver_active': is_screen_saver,
            'is_charging': is_charging_val,
            'is_user_idle': idle_time >= self.idle_threshold_sec,
            'is_cpu_idle': cpu_percent <= self.cpu_threshold,
            'is_memory_idle': memory_percent <= self.memory_threshold,
        }
    
    def is_idle(self) -> bool:
        """判断系统是否闲置"""
        status = self.get_system_status()
        
        # 屏幕保护激活或用户空闲且资源使用率低
        if status['is_screen_saver_active']:
            return status['is_cpu_idle']
        else:
            return (status['is_user_idle'] and 
                    status['is_cpu_idle'] and 
                    status['is_memory_idle'])

# 全局函数
def is_idle(idle_threshold_sec: int = 300, cpu_threshold: float = 15.0,
           memory_threshold: float = 70.0) -> bool:
    """判断系统是否闲置"""
    detector = MacOSIdleDetector(idle_threshold_sec, cpu_threshold, memory_threshold)
    return detector.is_idle()

def get_system_status(idle_threshold_sec: int = 300, cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> Dict:
    """获取系统状态"""
    detector = MacOSIdleDetector(idle_threshold_sec, cpu_threshold, memory_threshold)
    return detector.get_system_status()
