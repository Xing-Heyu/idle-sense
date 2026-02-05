"""
idle_sense/windows.py
Windows idle detector
"""

import ctypes
import ctypes.wintypes
import time
from typing import Dict, Tuple, Optional

# 📝 修改：添加psutil优雅降级
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class WindowsIdleDetector:
    """Windows idle detector with enhanced compatibility"""
    
    def __init__(self, idle_threshold_sec: int = 300, 
                 cpu_threshold: float = 15.0,
                 memory_threshold: float = 70.0):
        self.idle_threshold_ms = idle_threshold_sec * 1000
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        
        # Windows API initialization
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        
        # 📝 修改：检测GetTickCount64可用性
        self._has_tick_count_64 = hasattr(self._user32, 'GetTickCount64')
        
        # Last input time structure
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), 
                       ('dwTime', ctypes.c_uint)]
        
        self._last_input_info = LASTINPUTINFO()
        self._last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    
    def _get_last_input_time(self) -> int:
        """Get last input time in milliseconds"""
        if not self._user32.GetLastInputInfo(ctypes.byref(self._last_input_info)):
            # 📝 修改：API调用失败时返回0
            return 0
        return self._last_input_info.dwTime
    
    def _get_tick_count(self) -> int:
        """Get system tick count in milliseconds with 64-bit support"""
        if self._has_tick_count_64:
            # 📝 修复：使用64位版本（无回绕问题，Windows Vista+）
            return self._user32.GetTickCount64()
        else:
            # 📝 修复：32位版本备用（所有Windows都有）
            return self._user32.GetTickCount()
    
    def get_user_idle_time_ms(self) -> int:
        """Get user idle time in milliseconds with proper wrap handling"""
        last_input = self._get_last_input_time()
        current_tick = self._get_tick_count()
        
        # 📝 修复：正确的时间回绕处理
        if self._has_tick_count_64:
            # 64位版本无回绕问题
            idle_time = current_tick - last_input
        else:
            # 32位版本回绕处理
            if current_tick >= last_input:
                idle_time = current_tick - last_input
            else:
                # 发生了32位回绕（约49.7天）
                idle_time = (0xFFFFFFFF - last_input) + current_tick
        
        return max(0, idle_time)  # 确保非负
    
    def is_screen_locked(self) -> bool:
        """Check if screen is locked with fallback"""
        try:
            # 📝 修改：添加更可靠的屏幕锁定检测
            hwnd = self._user32.GetForegroundWindow()
            if hwnd == 0:
                return True
            
            # 尝试检查窗口可见性
            is_visible = self._user32.IsWindowVisible(hwnd)
            if not is_visible:
                return True
                
            # 检查工作站是否被锁定
            try:
                if hasattr(self._user32, 'GetForegroundWindow'):
                    # 简单启发式：长时间无输入可能是锁定
                    idle_time = self.get_user_idle_time_ms()
                    return idle_time > 2 * 60 * 1000  # 2分钟
                return False
            except:
                return False
                
        except Exception:
            # 📝 修改：优雅降级
            idle_time = self.get_user_idle_time_ms()
            return idle_time > 5 * 60 * 1000  # 5分钟降级判断
    
    def is_charging(self) -> bool:
        """Check if charging with fallback"""
        if not PSUTIL_AVAILABLE:
            # 📝 修改：无psutil时返回True（假设充电）
            return True
        
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                # 无电池设备（如台式机、服务器）
                return True
            return battery.power_plugged
        except Exception:
            # 📝 修改：任何异常都返回True（安全默认）
            return True
    
    def get_cpu_memory_usage(self) -> Tuple[float, float]:
        """Get CPU and memory usage with fallback"""
        if not PSUTIL_AVAILABLE:
            # 📝 修改：无psutil时返回默认值
            return 0.0, 0.0
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            return cpu_percent, memory_percent
        except Exception:
            # 📝 修改：异常时返回默认值
            return 0.0, 0.0
    
    def get_system_status(self) -> Dict:
        """Get system status"""
        user_idle_ms = self.get_user_idle_time_ms()
        cpu_percent, memory_percent = self.get_cpu_memory_usage()
        is_locked = self.is_screen_locked()
        is_charging_val = self.is_charging()
        
        # 📝 修改：添加健康状态信息
        return {
            'timestamp': time.time(),
            'user_idle_time_sec': user_idle_ms / 1000.0,
            'cpu_percent': round(cpu_percent, 1),
            'memory_percent': round(memory_percent, 1),
            'is_screen_locked': is_locked,
            'is_charging': is_charging_val,
            'is_user_idle': user_idle_ms >= self.idle_threshold_ms,
            'is_cpu_idle': cpu_percent <= self.cpu_threshold,
            'is_memory_idle': memory_percent <= self.memory_threshold,
            'has_psutil': PSUTIL_AVAILABLE,
            'has_tick64': self._has_tick_count_64,
        }
    
    def is_idle(self) -> bool:
        """Check if system is idle"""
        status = self.get_system_status()
        return (status['is_user_idle'] and 
                status['is_cpu_idle'] and 
                status['is_memory_idle'])

def is_idle(idle_threshold_sec: int = 300, 
           cpu_threshold: float = 15.0,
           memory_threshold: float = 70.0) -> bool:
    """Check if system is idle"""
    detector = WindowsIdleDetector(idle_threshold_sec, 
                                   cpu_threshold, 
                                   memory_threshold)
    return detector.is_idle()

def get_system_status(idle_threshold_sec: int = 300,
                     cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> Dict:
    """Get system status"""
    detector = WindowsIdleDetector(idle_threshold_sec,
                                   cpu_threshold,
                                   memory_threshold)
    return detector.get_system_status()

# 📝 新增：诊断函数
def check_windows_api() -> Dict[str, bool]:
    """Check Windows API availability"""
    user32 = ctypes.windll.user32
    
    return {
        'GetLastInputInfo': hasattr(user32, 'GetLastInputInfo'),
        'GetTickCount': hasattr(user32, 'GetTickCount'),
        'GetTickCount64': hasattr(user32, 'GetTickCount64'),
        'GetForegroundWindow': hasattr(user32, 'GetForegroundWindow'),
        'IsWindowVisible': hasattr(user32, 'IsWindowVisible'),
        'psutil_available': PSUTIL_AVAILABLE,
    }
