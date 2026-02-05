"""
idle_sense/core.py
Cross-platform idle state detection
"""

import platform
from typing import Any, Optional

# 📝 修改：从立即加载改为懒加载模式
# 避免在导入core.py时就触发平台模块的语法错误
_PLATFORM_MODULE: Optional[Any] = None

def _get_platform_module():
    """Get platform-specific module with lazy loading"""
    global _PLATFORM_MODULE
    
    if _PLATFORM_MODULE is not None:
        return _PLATFORM_MODULE
    
    system = platform.system()
    
    try:
        if system == "Windows":
            from idle_sense import windows
            _PLATFORM_MODULE = windows
        elif system == "Darwin":
            from idle_sense import macos
            _PLATFORM_MODULE = macos
        elif system == "Linux":
            # 📝 修改：提供更清晰的Linux支持信息
            class LinuxStub:
                @staticmethod
                def is_idle(*args, **kwargs):
                    raise NotImplementedError("Linux support is in development")
                
                @staticmethod
                def get_system_status(*args, **kwargs):
                    return {
                        "platform": "Linux",
                        "idle": False,
                        "reason": "Linux support in development",
                        "idle_time": 0,
                        "cpu_usage": 0.0,
                        "memory_usage": 0.0
                    }
            _PLATFORM_MODULE = LinuxStub()
        else:
            raise NotImplementedError(f"Unsupported system: {system}")
            
    except ImportError as e:
        # 📝 修改：提供更友好的错误信息，帮助云端调试
        raise ImportError(
            f"Failed to import platform module for {system}. "
            f"Possible reasons:\n"
            f"1. The module file (idle_sense/{system.lower()}.py) is missing\n"
            f"2. There's a syntax error in the module\n"
            f"3. Missing dependencies (check requirements.txt)\n"
            f"Original error: {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error loading platform module for {system}: {e}") from e
    
    return _PLATFORM_MODULE

def is_idle(idle_threshold_sec: int = 300, 
           cpu_threshold: float = 15.0,
           memory_threshold: float = 70.0) -> bool:
    """Check if system is idle"""
    platform_module = _get_platform_module()
    return platform_module.is_idle(idle_threshold_sec, cpu_threshold, memory_threshold)

def get_system_status(idle_threshold_sec: int = 300,
                     cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> dict:
    """Get current system status"""
    platform_module = _get_platform_module()
    return platform_module.get_system_status(idle_threshold_sec, cpu_threshold, memory_threshold)

def get_platform() -> str:
    """Get current platform name"""
    return platform.system()

# 📝 新增：健康检查函数（云端调试用）
def check_platform_module() -> tuple[bool, str]:
    """Check if platform module can be loaded"""
    try:
        module = _get_platform_module()
        platform_name = get_platform()
        return True, f"Platform module for {platform_name} loaded successfully"
    except ImportError as e:
        return False, f"Import failed: {e}"
    except NotImplementedError as e:
        return False, f"Platform not supported: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

# 📝 新增：简单版本检查
def get_version() -> str:
    """Get module version"""
    return "1.0.0"
