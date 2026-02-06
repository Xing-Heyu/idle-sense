"""
idle_sense/windows.py
Windows idle detector with reliable lock screen detection
借鉴自多个开源项目的成熟代码片段
"""

import ctypes
import time
from typing import Dict, Tuple

# psutil 作为可选依赖，用于获取CPU/内存使用率
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class WindowsIdleDetector:
    """Windows idle detector with reliable lock screen detection"""
    
    def __init__(self, idle_threshold_sec: int = 300, 
                 cpu_threshold: float = 15.0,
                 memory_threshold: float = 70.0):
        self.idle_threshold_sec = idle_threshold_sec
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        
        # 初始化 Windows API
        self.user32 = ctypes.windll.user32
        
        # 设置 GetLastInputInfo 结构
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint),
                       ('dwTime', ctypes.c_uint)]
        
        self.last_input_info = LASTINPUTINFO()
        self.last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    
    def _get_last_input_time(self) -> int:
        """Get last input time in milliseconds"""
        if not self.user32.GetLastInputInfo(ctypes.byref(self.last_input_info)):
            return 0  # API调用失败
        return self.last_input_info.dwTime
    
    def _get_tick_count(self) -> int:
        """Get system tick count in milliseconds"""
        # 优先使用 GetTickCount64（Windows Vista+）
        if hasattr(self.user32, 'GetTickCount64'):
            return self.user32.GetTickCount64()
        else:
            # 备用：GetTickCount（所有Windows版本）
            return self.user32.GetTickCount()
    
    def get_user_idle_time_ms(self) -> int:
        """
        Get user idle time in milliseconds.
        基于 Windows GetLastInputInfo API
        """
        last_input = self._get_last_input_time()
        current_tick = self._get_tick_count()
        
        if last_input == 0:
            return 0  # 获取失败
            
        # 计算空闲时间（处理32位回绕）
        if current_tick >= last_input:
            idle_time = current_tick - last_input
        else:
            # 32位计数器回绕处理（约49.7天）
            idle_time = (0xFFFFFFFF - last_input) + current_tick
        
        return max(0, idle_time)
    
    def is_screen_locked(self) -> bool:
        """
        Check if screen is locked using OpenInputDesktop API.
        借鉴自开源项目：使用 Windows API 可靠检测工作站锁定状态
        """
        try:
            # 借鉴点1：使用 OpenInputDesktop API
            # 0x0100 = DESKTOP_SWITCHDESKTOP access right
            DESKTOP_SWITCHDESKTOP = 0x0100
            
            # 尝试以切换桌面权限打开输入桌面
            hdesk = self.user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
            
            if hdesk:
                # 能打开桌面 -> 未锁定
                self.user32.CloseDesktop(hdesk)
                return False
            else:
                # 不能打开桌面 -> 已锁定或API失败
                return True
                
        except Exception:
            # 借鉴点2：API调用异常时，保守返回 True（假设已锁定）
            return True
    
    def get_cpu_memory_usage(self) -> Tuple[float, float]:
        """Get CPU and memory usage with psutil fallback"""
        if not PSUTIL_AVAILABLE:
            return 0.0, 0.0
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            return cpu_percent, memory_percent
        except Exception:
            return 0.0, 0.0
    
    def is_charging(self) -> bool:
        """Check if charging with psutil fallback"""
        if not PSUTIL_AVAILABLE:
            # 无 psutil，保守假设台式机（始终"充电"）
            return True
        
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                # 无电池设备（台式机、服务器）
                return True
            return battery.power_plugged
        except Exception:
            # 异常时保守返回 True
            return True
    
    def get_system_status(self) -> Dict:
        """Get complete system status"""
        idle_time_ms = self.get_user_idle_time_ms()
        idle_time_sec = idle_time_ms / 1000.0
        cpu_percent, memory_percent = self.get_cpu_memory_usage()
        is_locked = self.is_screen_locked()
        is_charging_val = self.is_charging()
        
        return {
            'timestamp': time.time(),
            'user_idle_time_sec': round(idle_time_sec, 1),
            'cpu_percent': round(cpu_percent, 1),
            'memory_percent': round(memory_percent, 1),
            'is_screen_locked': is_locked,
            'is_charging': is_charging_val,
            'is_user_idle': idle_time_sec >= self.idle_threshold_sec,
            'is_cpu_idle': cpu_percent <= self.cpu_threshold,
            'is_memory_idle': memory_percent <= self.memory_threshold,
            'has_psutil': PSUTIL_AVAILABLE,
            'has_tick64': hasattr(self.user32, 'GetTickCount64'),
        }
    
    def is_idle(self) -> bool:
        """
        Check if system is idle.
        核心逻辑：屏幕未锁定 + 用户空闲 + CPU/内存使用率低
        """
        status = self.get_system_status()
        
        # 如果屏幕锁定，直接返回非空闲（保守）
        if status['is_screen_locked']:
            return False
            
        return (status['is_user_idle'] and 
                status['is_cpu_idle'] and 
                status['is_memory_idle'])

# 模块级函数，保持与 core.py 的兼容性
def is_idle(idle_threshold_sec: int = 300,
           cpu_threshold: float = 15.0,
           memory_threshold: float = 70.0) -> bool:
    """Check if system is idle - 模块公共接口"""
    detector = WindowsIdleDetector(idle_threshold_sec,
                                   cpu_threshold,
                                   memory_threshold)
    return detector.is_idle()

def get_system_status(idle_threshold_sec: int = 300,
                     cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> Dict:
    """Get system status - 模块公共接口"""
    detector = WindowsIdleDetector(idle_threshold_sec,
                                   cpu_threshold,
                                   memory_threshold)
    return detector.get_system_status()

# 借鉴自开源项目的诊断工具
def check_windows_api() -> Dict[str, bool]:
    """检查Windows API可用性"""
    user32 = ctypes.windll.user32
    
    return {
        'GetLastInputInfo': hasattr(user32, 'GetLastInputInfo'),
        'GetTickCount': hasattr(user32, 'GetTickCount'),
        'GetTickCount64': hasattr(user32, 'GetTickCount64'),
        'OpenInputDesktop': hasattr(user32, 'OpenInputDesktop'),
        'CloseDesktop': hasattr(user32, 'CloseDesktop'),
        'psutil_available': PSUTIL_AVAILABLE,
    }
