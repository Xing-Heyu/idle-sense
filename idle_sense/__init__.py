"""
idle-sense: 跨平台空闲检测库
"""

from .core import is_idle, get_system_status, get_platform

__version__ = "0.1.0"
__all__ = ['is_idle', 'get_system_status', 'get_platform']
