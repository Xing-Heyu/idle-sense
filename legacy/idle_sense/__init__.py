"""
idle-sense: Cross-platform idle state detection library
"""

from .core import check_platform_module, get_platform, get_system_status, get_version, is_idle

__version__ = "1.0.0"  # 📝 修改：与core.py中的版本保持一致
__all__ = [
    'is_idle',
    'get_system_status',
    'get_platform',
    'check_platform_module',
    'get_version'
]
