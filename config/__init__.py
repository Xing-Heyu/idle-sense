"""
config - 配置管理模块

提供两种配置管理方式：
1. 新版 Pydantic Settings（推荐）- 类型安全，支持环境变量
2. 旧版默认配置常量 - 保持向后兼容

使用示例：
    # 新版（推荐）
    from config.settings import settings
    scheduler_url = settings.SCHEDULER_URL

    # 旧版（兼容）
    from config import SCHEDULER
    scheduler_url = SCHEDULER.URL
"""

# 新版配置（推荐）
# 旧版配置（兼容）
from .default_settings import DEFAULTS, MONITORING, NODE, PATHS, SCHEDULER, SECURITY, WEB
from .settings import (
    DistributedTaskSettings,
    ResourceSettings,
    SchedulerSettings,
    SecuritySettings,
    Settings,
    StorageSettings,
    WebUISettings,
    get_settings,
    settings,
)

__all__ = [
    # 新版配置
    'Settings',
    'SchedulerSettings',
    'ResourceSettings',
    'WebUISettings',
    'StorageSettings',
    'DistributedTaskSettings',
    'SecuritySettings',
    'settings',
    'get_settings',

    # 旧版配置（兼容）
    'SCHEDULER',
    'NODE',
    'WEB',
    'MONITORING',
    'PATHS',
    'SECURITY',
    'DEFAULTS'
]

__version__ = "2.0.0"
