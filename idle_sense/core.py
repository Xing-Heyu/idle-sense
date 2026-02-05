"""
idle-sense 核心模块
统一接口和系统检测
"""

import platform
import logging

logger = logging.getLogger(__name__)


def is_idle(threshold: float = 0.3) -> bool:
    """
    检测电脑是否处于闲置状态
    
    Args:
阈值：CPU使用率阈值（0.3表示30%）
    
返回值：
布尔型：True表示空闲，False表示正在使用
    """
    system = platform.system()
    
    尝试:
        如果系统 ==“Windows”:
            fromwindowsimportis_idleaswindows_is_idle
            return windows_is_idle(threshold)
        elif system == "Darwin":  # macOS
            from .macos import is_idle as macos_is_idle
            return macos_is_idle(threshold)
        elif系统 ==“Linux”:
            # 暂不支持Linux，返回False（安全默认）
logger.warning(“Linux支持尚未实现”)
            返回 False
        否则:
logger.error(f"不支持的系统：{system}")
            返回 False
     exceptImportError ase:
logger.error(f"导入错误：{e}")
        返回 False
     exceptException ase:
        logger.error(f"Unexpected error: {e}")
        return False  # 出错时默认返回非闲置，避免打扰用户
