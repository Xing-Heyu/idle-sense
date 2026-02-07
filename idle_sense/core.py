"""
idle_sense/core.py
Cross-platform idle state detection
借鉴自成熟跨平台库的懒加载和错误处理模式
"""

import platform
import sys
from typing import Any, Dict, Optional

# 平台模块缓存
_PLATFORM_MODULE_CACHE: Optional[Any] = None
_PLATFORM_NAME_CACHE: Optional[str] = None

def _detect_platform() -> str:
    """
    检测当前操作系统平台。
    借鉴自跨平台库的简洁检测方式。
    """
    system = platform.system()
    
    # 简化平台映射
    platform_map = {
        'Windows': 'windows',
        'Darwin': 'macos',
        'Linux': 'linux'
    }
    
    return platform_map.get(system, system.lower())

def _load_platform_module(platform_name: str) -> Any:
    """
    动态加载平台特定模块。
    借鉴自插件系统的懒加载模式。
    """
    try:
        if platform_name == 'windows':
            from idle_sense import windows
            return windows
        elif platform_name == 'macos':
            from idle_sense import macos
            return macos
        elif platform_name == 'linux':
            # Linux支持占位符
            class LinuxStub:
                @staticmethod
                def is_idle(*args, **kwargs):
                    raise NotImplementedError("Linux支持正在开发中")
                
                @staticmethod
                def get_system_status(*args, **kwargs):
                    return {
                        "platform": "Linux",
                        "idle": False,
                        "reason": "Linux支持正在开发中",
                        "idle_time": 0,
                        "cpu_usage": 0.0,
                        "memory_usage": 0.0
                    }
            return LinuxStub()
        else:
            raise ImportError(f"不支持的操作系统: {platform_name}")
            
    except ImportError as e:
        # 提供清晰的错误信息
        error_msg = (
            f"无法加载平台模块 '{platform_name}':\n"
            f"  1. 确保文件 idle_sense/{platform_name}.py 存在\n"
            f"  2. 检查该文件是否有语法错误\n"
            f"  3. 确认所有依赖已安装\n"
            f"\n原始错误: {e}"
        )
        raise ImportError(error_msg) from e

def _get_platform_module() -> Any:
    """
    获取平台模块（带缓存）。
    借鉴自单例模式的缓存机制。
    """
    global _PLATFORM_MODULE_CACHE, _PLATFORM_NAME_CACHE
    
    # 如果已缓存，直接返回
    if _PLATFORM_MODULE_CACHE is not None:
        return _PLATFORM_MODULE_CACHE
    
    # 检测平台
    platform_name = _detect_platform()
    _PLATFORM_NAME_CACHE = platform_name
    
    # 加载平台模块
    _PLATFORM_MODULE_CACHE = _load_platform_module(platform_name)
    
    return _PLATFORM_MODULE_CACHE

def is_idle(idle_threshold_sec: int = 300, 
           cpu_threshold: float = 15.0,
           memory_threshold: float = 70.0) -> bool:
    """
    检查系统是否空闲。
    
    Args:
        idle_threshold_sec: 用户空闲时间阈值（秒）
        cpu_threshold: CPU使用率阈值（%）
        memory_threshold: 内存使用率阈值（%）
    
    Returns:
        bool: True如果系统空闲，否则False
    
    Examples:
        >>> from idle_sense import is_idle
        >>> if is_idle():
        ...     print("系统空闲，可以执行任务")
        ... else:
        ...     print("系统繁忙，请等待")
    """
    platform_module = _get_platform_module()
    return platform_module.is_idle(idle_threshold_sec, cpu_threshold, memory_threshold)

def get_system_status(idle_threshold_sec: int = 300,
                     cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> Dict:
    """
    获取系统状态详情。
    
    Args:
        idle_threshold_sec: 用户空闲时间阈值（秒）
        cpu_threshold: CPU使用率阈值（%）
        memory_threshold: 内存使用率阈值（%）
    
    Returns:
        Dict: 包含系统状态信息的字典
    
    Examples:
        >>> from idle_sense import get_system_status
        >>> status = get_system_status()
        >>> print(f"CPU使用率: {status.get('cpu_percent', 0)}%")
        >>> print(f"用户空闲时间: {status.get('user_idle_time_sec', 0)}秒")
    """
    platform_module = _get_platform_module()
    return platform_module.get_system_status(idle_threshold_sec, cpu_threshold, memory_threshold)

def get_platform() -> str:
    """
    获取当前平台名称。
    
    Returns:
        str: 平台名称 ('windows', 'macos', 'linux', 或其他)
    
    Examples:
        >>> from idle_sense import get_platform
        >>> print(f"当前平台: {get_platform()}")
    """
    global _PLATFORM_NAME_CACHE
    if _PLATFORM_NAME_CACHE is None:
        _PLATFORM_NAME_CACHE = _detect_platform()
    return _PLATFORM_NAME_CACHE

def check_platform_module() -> Dict[str, Any]:
    """
    检查平台模块状态（用于调试）。
    借鉴自健康检查模式。
    
    Returns:
        Dict: 包含平台模块状态的信息
    
    Examples:
        >>> from idle_sense import check_platform_module
        >>> status = check_platform_module()
        >>> print(f"平台: {status['platform']}")
        >>> print(f"加载成功: {status['loaded']}")
        >>> if not status['loaded']:
        ...     print(f"错误: {status['error']}")
    """
    result = {
        "platform": get_platform(),
        "loaded": False,
        "error": None,
        "module": None
    }
    
    try:
        module = _get_platform_module()
        result["loaded"] = True
        result["module"] = module.__name__ if hasattr(module, '__name__') else str(type(module))
    except Exception as e:
        result["error"] = str(e)
    
    return result

def get_version() -> str:
    """
    获取模块版本。
    
    Returns:
        str: 版本号
    """
    return "1.0.0"

# 模块初始化时的平台检查
def _initialize() -> None:
    """
    模块初始化：检查平台兼容性。
    借鉴自库的初始化模式。
    """
    platform_name = get_platform()
    
    # 输出平台信息（仅首次导入时）
    if _PLATFORM_MODULE_CACHE is None:
        print(f"[idle_sense] 检测到平台: {platform_name}")
        
        if platform_name not in ['windows', 'macos']:
            print(f"[idle_sense] 警告: {platform_name} 平台支持有限")

# 导入时自动初始化
_initialize()

# 公开的API
__all__ = [
    'is_idle',
    'get_system_status',
    'get_platform',
    'check_platform_module',
    'get_version'
]