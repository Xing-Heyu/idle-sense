"""
LegacyAdapter 单元测试

验证适配器层的正确性和向后兼容性
"""

import os
import sys

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.adapters import FeatureFlag, LegacyAdapter
from src.infrastructure.adapters.legacy_adapter import MigrationConfig, create_adapter, get_adapter


class TestMigrationConfig:
    """测试迁移配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = MigrationConfig()
        assert config.enabled_features == set()
        assert config.fallback_on_error is True
        assert config.log_switching is True

    def test_enable_disable_feature(self):
        """测试启用/禁用功能"""
        config = MigrationConfig()

        # 初始状态
        assert not config.is_enabled(FeatureFlag.USE_NEW_AUTH)

        # 启用
        config.enable(FeatureFlag.USE_NEW_AUTH)
        assert config.is_enabled(FeatureFlag.USE_NEW_AUTH)

        # 禁用
        config.disable(FeatureFlag.USE_NEW_AUTH)
        assert not config.is_enabled(FeatureFlag.USE_NEW_AUTH)

    def test_multiple_features(self):
        """测试多个功能开关"""
        config = MigrationConfig()

        config.enable(FeatureFlag.USE_NEW_AUTH)
        config.enable(FeatureFlag.USE_NEW_TASK)

        assert config.is_enabled(FeatureFlag.USE_NEW_AUTH)
        assert config.is_enabled(FeatureFlag.USE_NEW_TASK)
        assert not config.is_enabled(FeatureFlag.USE_NEW_NODE)


class TestLegacyAdapter:
    """测试遗留系统适配器"""

    def test_adapter_creation(self):
        """测试适配器创建"""
        adapter = LegacyAdapter()
        assert adapter is not None
        assert adapter.config is not None

    def test_adapter_with_config(self):
        """测试带配置的适配器创建"""
        config = MigrationConfig()
        config.enable(FeatureFlag.USE_NEW_AUTH)

        adapter = LegacyAdapter(config)
        assert adapter.config.is_enabled(FeatureFlag.USE_NEW_AUTH)

    def test_create_adapter_helper(self):
        """测试创建适配器的便捷函数"""
        # 默认不启用新功能
        adapter = create_adapter()
        assert not adapter.config.is_enabled(FeatureFlag.USE_NEW_AUTH)

        # 启用新功能
        adapter_new = create_adapter(enable_new_features=True)
        assert adapter_new.config.is_enabled(FeatureFlag.USE_NEW_AUTH)
        assert adapter_new.config.is_enabled(FeatureFlag.USE_NEW_TASK)
        assert adapter_new.config.is_enabled(FeatureFlag.USE_NEW_NODE)

    def test_get_adapter_singleton(self):
        """测试适配器单例"""
        adapter1 = get_adapter()
        adapter2 = get_adapter()
        assert adapter1 is adapter2


class TestLegacyAdapterAuth:
    """测试认证适配功能"""

    def test_logout_always_succeeds(self):
        """测试登出功能始终成功"""
        adapter = LegacyAdapter()
        result = adapter.logout("test_user_id")

        assert result["success"] is True
        assert "登出成功" in result["message"]


class TestFeatureFlag:
    """测试功能开关枚举"""

    def test_feature_flag_values(self):
        """测试功能开关值"""
        assert FeatureFlag.USE_NEW_AUTH.value == "use_new_auth"
        assert FeatureFlag.USE_NEW_TASK.value == "use_new_task"
        assert FeatureFlag.USE_NEW_NODE.value == "use_new_node"
        assert FeatureFlag.USE_NEW_UI.value == "use_new_ui"


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_adapter_has_required_methods(self):
        """测试适配器具有所需方法"""
        adapter = LegacyAdapter()

        # 检查必需的方法存在
        assert hasattr(adapter, "login")
        assert hasattr(adapter, "register")
        assert hasattr(adapter, "logout")
        assert hasattr(adapter, "submit_task")
        assert hasattr(adapter, "get_nodes")
        assert hasattr(adapter, "get_system_stats")

    def test_method_signatures(self):
        """测试方法签名兼容性"""
        import inspect

        adapter = LegacyAdapter()

        # 检查 login 方法签名
        sig = inspect.signature(adapter.login)
        params = list(sig.parameters.keys())
        assert "username" in params

        # 检查 register 方法签名
        sig = inspect.signature(adapter.register)
        params = list(sig.parameters.keys())
        assert "username" in params
        assert "folder_location" in params

        # 检查 submit_task 方法签名
        sig = inspect.signature(adapter.submit_task)
        params = list(sig.parameters.keys())
        assert "code" in params


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
