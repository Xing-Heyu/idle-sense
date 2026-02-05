"""
idle_sense/core.py
Cross-platform idle state detection unified interface
跨平台闲置检测统一接口
"""

import platform

def _get_platform_module():
    """Get platform-specific module"""
    system = platform.system()
    
    if system == "Windows":
        from idle_sense import windows
        return windows
    elif system == "Darwin":  # macOS
        from idle_sense import macos
        return macos
    elif system == "Linux":
        raise NotImplementedError("Linux support is under development")
    else:
        raise NotImplementedError(f"Unsupported system: {system}")

# Early import
_PLATFORM_MODULE = _get_platform_module()

def is_idle(idle_threshold_sec: int = 300, 
            cpu_threshold: float = 15.0,
            memory_threshold: float = 70.0) -> bool:
    """Determine if the system is currently idle"""
    return _PLATFORM_MODULE.is_idle(idle_threshold_sec, cpu_threshold, memory_threshold)

def get_system_status(idle_threshold_sec: int = 300,
                     cpu_threshold: float = 15.0,
                     memory_threshold: float = 70.0) -> dict:
    """Get current system status"""
    return _PLATFORM_MODULE.get_system_status(idle_threshold_sec, cpu_threshold, memory_threshold)

def get_platform() -> str:
    """Get current platform name"""
    return platform.system()
