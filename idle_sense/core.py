"""
idle_sense/core.py
跨平台闲置检测统一接口
"""

导入平台

def _get_platform_module():
    """获取平台对应的模块"""
    system = platform.system()
    
    if system == "Windows":
        from idle_sense import windows
        return windows
    elif system == "Darwin":
        from idle_sense import macos
        返回macos
    elif系统 =="Linux":
        raise NotImplementedError("Linux支持开发中")
    else:
        引发 NotImplementedErrorf"不支持的系统:{

# 提前导入
_PLATFORM_MODULE = _get_platform_module()

def is_idle(idle_threshold_sec: int = 300, cpu_threshold: float = 15.0,
           memory_threshold: float = 70.0) -> bool:
    """判断当前系统是否闲置"""
    返回_PLATFORM_MODULE.空闲状态(空闲阈值秒, CPU阈值, 内存阈值)

 get_system_status(idle_threshold_sec: int = 300, cpu_threshold: float = 15.0,
内存阈值: float =70.0)-> 字典:
    """获取当前系统状态"""
    返回_PLATFORM_MODULE.获取系统状态(空闲阈值秒, CPU阈值, 内存阈值)

 获取平台()-> 字符串:
    """获取当前平台名称"""
    return platform.system()
