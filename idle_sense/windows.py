"""
idle_sense/windows.py
Windows系统闲置检测器 - 最终验证版
"""

导入ctypes
导入ctypes.wintypes
import time
from typing import Dict, Tuple
import psutil

class WindowsIdleDetector:
    “Windows系统闲置检测器”
    
    def __init__(self, idle_threshold_sec: int = 300, cpu_threshold: float = 15.0,
                 memory_threshold: float = 70.0):
        self.idle_threshold_ms = idle_threshold_sec * 1000
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        
        # Windows API初始化
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        
        # 最后输入时间结构
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]
        
        self._last_input_info = LASTINPUTINFO()
        self._last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    
    def _get_last_input_time(self) -> int:
        """获取最后输入时间（毫秒）"""
self._user32.GetLastInputInfo(ctypes.byref_last_input_info)
        returnself._last_input_info.dwTime
    
    def _get_tick_count(self) -> int:
        """获取系统运行时间（毫秒）"""
        返回self._user32.GetTickCount()
    
    def get_user_idle_time_ms(self) -> int:
        """获取用户空闲时间（毫秒）"""
        last_input = self._get_last_input_time()
        current_tick = self._get_tick_count()
空闲时间 =(当前帧数 - 上次输入) & 0xFFFFFFFF
        返回空闲时间
    
    def is_screen_locked(self) -> bool:
        """检测屏幕是否锁定（安全方法）"""
        尝试：
            # 使用GetForegroundWindow检查是否有活动窗口
            hwnd = self._user32.GetForegroundWindow()
            如果hwnd ==0
                返回 真  # 没有前台窗口，可能锁定
            
            # 检查窗口是否可见
            is_visible = self._user32.IsWindowVisible(hwnd)
            return not is_visible
            
         except异常：
            # 如果失败，使用空闲时间推测
空闲时间 = self.获取用户空闲时间毫秒()
            return空闲时间 > 5 * 60 * 1000  # 5分钟无操作
    
     is_charging(self) -> bool:
        """检测是否在充电"""
        尝试：
            # 检查是否有电池信息
            import psutil
电池 = psutil.sensors_battery()
            如果电池:
                返回电池.电源已插
            返回 True  # 桌面电脑或无法检测
          except:
            返回 True  # 默认返回True
    
    def get_cpu_memory_usage(self) -> Tuple[float, float]:
        “获取CPU和内存使用率”
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
返回CPU百分比，内存百分比
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        user_idle_ms = self.get_user_idle_time_ms()
        cpu_percent, memory_percent = self.get_cpu_memory_usage()
        is_locked = self.is_screen_locked()
        is_charging_val = self.is_charging()
        
        return {
            'timestamp': time.time(),
            'user_idle_time_sec': user_idle_ms / 1000.0,
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'is_screen_locked': is_locked,
            '正在充电': 正在充电值,
            'is_user_idle': user_idle_ms >= self.idle_threshold_ms,
            'is_cpu_idle': cpu_percent <= self.cpu_threshold,
            'is_memory_idle': memory_percent <= self.memory_threshold,
        }
    
    def is_idle(self) -> bool:
        """判断系统是否闲置"""
        status = self.get_system_status()
        
        # 简单逻辑：用户空闲且资源使用率低
        return (status['is_user_idle'] and 
状态是否CPU空闲] 且 
状态['is_memory_idle'])

# 全局函数
def is_idle(idle_threshold_sec: int = 300, cpu_threshold: float = 15.0, 
            memory_threshold: float = 70.0) -> bool:
    """判断系统是否闲置"""
    detector = WindowsIdleDetector(idle_threshold_sec, cpu_threshold, memory_threshold)
    return detector.is_idle()

def get_system_status(idle_threshold_sec: int = 300, cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> Dict:
    """获取系统状态"""
    detector = WindowsIdleDetector(idle_threshold_sec, cpu_threshold, memory_threshold)
    返回检测器.获取系统状态()
