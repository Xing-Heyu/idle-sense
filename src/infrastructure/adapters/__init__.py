"""
兼容性适配器层

用于平滑迁移从 web_interface.py 到 Clean Architecture
保持向后兼容，支持功能开关切换
"""

from .legacy_adapter import FeatureFlag, LegacyAdapter

__all__ = ["LegacyAdapter", "FeatureFlag"]
