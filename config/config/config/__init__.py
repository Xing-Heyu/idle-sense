"""
config - 配置管理模块
"""

from .default_settings import (
    SCHEDULER, NODE, WEB, MONITORING, PATHS, SECURITY, DEFAULTS
)

__all__ = [
    'SCHEDULER',
    'NODE', 
    'WEB',
    'MONITORING',
    'PATHS',
    'SECURITY',
    'DEFAULTS'
]

__version__ = "1.0.0"
