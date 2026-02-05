"""
Windows系统闲置状态检测
"""

import psutil
from typing import List
import logging

logger = logging.getLogger(__name__)


class WindowsDetector:
    """Windows系统闲置检测器"""
    
    def __init__(self):
        # 高负载进程名单（需要队友A完善）
        self.high_load_processes = {
            # 游戏
            'fortnite.exe', 'valorant.exe', 'cs2.exe', 'dota2.exe',
            'overwatch.exe', 'minecraft.exe', 'steam.exe',
            # 创意软件
            'prpro.exe', 'afterfx.exe', 'photoshop.exe', 'illustrator.exe',
            'blender.exe', 'maya.exe', 'cinema4d.exe',
            # 开发工具
            'androidstudio.exe', 'unity.exe', 'unrealengine.exe'
        }
    
    def is_screen_locked(self) -> bool:
        """
        检测屏幕是否锁定
        TODO: 队友A需要实现具体逻辑
        """
        logger.warning("is_screen_locked() not implemented yet")
        return False  # 默认返回False（使用中）
    
    def get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            return psutil.cpu_percent(interval=0.5)
        except Exception as e:
            logger.error(f"Failed to get CPU usage: {e}")
            return 100.0  # 出错时返回高使用率
    
    def is_high_load_running(self) -> bool:
        """检测是否有高负载进程在运行"""
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name'].lower()
                    if proc_name in self.high_load_processes:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except Exception as e:
            logger.error(f"Failed to check high load processes: {e}")
            return True  # 出错时假设有高负载
    
    def is_charging(self) -> bool:
        """
        检测是否在充电（笔记本）
        TODO: 队友A需要实现
        """
        logger.warning("is_charging() not implemented yet")
        return True  # 默认返回True（充电中）
    
    def is_idle(self, threshold: float = 0.3) -> bool:
        """
        判断Windows电脑是否闲置
        
        Args:
阈值：CPU使用率阈值（0.3 = 30%）
        
返回值：
            bool: True表示闲置
        """
        # 1. 检查锁屏
        如果未锁定屏幕():
            返回 False
        
        # 2. 检查CPU使用率
        如果获取CPU使用率()> 阈值 *100:
            返回 False
        
        # 3. 检查高负载进程
        如果正在高负载运行():
            返回 False
        
        # 4. 检查电源（笔记本）
如果不是self.正在充电(:
            返回 假
        
         真


# 便捷函数
 is_idle(threshold: float = 0.3) -> bool:
    """检测Windows电脑是否闲置（对外接口）"""
检测器 =Windows检测器()
    返回检测器.处于空闲状态(阈值)


# 测试代码
如果__name__ =="__main__":
检测器 =Windows检测器()
    print("Windows检测器测试:")
    print(f"CPU使用率: {detector.get_cpu_usage()}%")
    print(f"高负载进程运行: {detector.is_high_load_running()}")
    print(f"是否闲置: {detector.is_idle()}")
