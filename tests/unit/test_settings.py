"""
配置管理模块单元测试
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

# 导入配置模块
from config.settings import (
    DistributedTaskSettings,
    ResourceSettings,
    SchedulerSettings,
    SecuritySettings,
    Settings,
    StorageSettings,
    WebUISettings,
    get_settings,
)


class TestSchedulerSettings:
    """调度器配置测试"""

    def test_default_values(self):
        """测试默认值"""
        settings = SchedulerSettings()
        assert settings.URL == "http://localhost:8000"
        assert settings.API_TIMEOUT == 10
        assert settings.HEALTH_CHECK_TIMEOUT == 3
        assert settings.MAX_RETRIES == 3
        assert settings.RETRY_DELAY == 1.0

    def test_url_validation(self):
        """测试URL验证"""
        # 有效URL
        settings = SchedulerSettings(URL="http://example.com:8000")
        assert settings.URL == "http://example.com:8000"

        # 去除尾部斜杠
        settings = SchedulerSettings(URL="http://example.com:8000/")
        assert settings.URL == "http://example.com:8000"

        # HTTPS支持
        settings = SchedulerSettings(URL="https://secure.example.com")
        assert settings.URL == "https://secure.example.com"

    def test_timeout_validation(self):
        """测试超时时间验证"""
        # 有效值
        settings = SchedulerSettings(API_TIMEOUT=30)
        assert settings.API_TIMEOUT == 30

        # 边界值
        settings = SchedulerSettings(API_TIMEOUT=1)
        assert settings.API_TIMEOUT == 1

        settings = SchedulerSettings(API_TIMEOUT=300)
        assert settings.API_TIMEOUT == 300

    def test_environment_variable_override(self):
        """测试环境变量覆盖"""
        with patch.dict(os.environ, {"SCHEDULER_URL": "http://custom:9000"}):
            settings = SchedulerSettings()
            assert settings.URL == "http://custom:9000"


class TestResourceSettings:
    """资源配置测试"""

    def test_default_values(self):
        """测试默认值"""
        settings = ResourceSettings()
        assert settings.DEFAULT_CPU_SHARE == 4.0
        assert settings.DEFAULT_MEMORY_SHARE == 8192
        assert settings.MIN_CPU_SHARE == 0.5
        assert settings.MAX_CPU_SHARE == 16.0

    def test_cpu_share_range(self):
        """测试CPU共享范围"""
        # 有效值
        settings = ResourceSettings(DEFAULT_CPU_SHARE=8.0)
        assert settings.DEFAULT_CPU_SHARE == 8.0

        # 边界值
        settings = ResourceSettings(DEFAULT_CPU_SHARE=0.5)
        assert settings.DEFAULT_CPU_SHARE == 0.5

        settings = ResourceSettings(DEFAULT_CPU_SHARE=32.0)
        assert settings.DEFAULT_CPU_SHARE == 32.0


class TestWebUISettings:
    """Web UI 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        settings = WebUISettings()
        assert settings.PAGE_TITLE == "闲置计算加速器"
        assert settings.PAGE_ICON == "⚡"
        assert settings.LAYOUT == "wide"
        assert not settings.AUTO_REFRESH
        assert settings.REFRESH_INTERVAL == 30

    def test_refresh_interval_range(self):
        """测试刷新间隔范围"""
        settings = WebUISettings(REFRESH_INTERVAL=60)
        assert settings.REFRESH_INTERVAL == 60

        settings = WebUISettings(REFRESH_INTERVAL=5)
        assert settings.REFRESH_INTERVAL == 5

        settings = WebUISettings(REFRESH_INTERVAL=300)
        assert settings.REFRESH_INTERVAL == 300


class TestStorageSettings:
    """存储配置测试"""

    def test_default_values(self):
        """测试默认值"""
        settings = StorageSettings()
        assert "local_users" in settings.USERS_DIR
        assert "node_data" in settings.NODE_DATA_DIR

    def test_ensure_directories(self, tmp_path):
        """测试目录创建"""
        settings = StorageSettings(
            USERS_DIR=str(tmp_path / "users"),
            NODE_DATA_DIR=str(tmp_path / "node_data"),
            LOG_DIR=str(tmp_path / "logs"),
            TEMP_DIR=str(tmp_path / "tmp"),
        )
        settings.ensure_directories()

        assert Path(settings.USERS_DIR).exists()
        assert Path(settings.NODE_DATA_DIR).exists()
        assert Path(settings.LOG_DIR).exists()
        assert Path(settings.TEMP_DIR).exists()


class TestDistributedTaskSettings:
    """分布式任务配置测试"""

    def test_default_values(self):
        """测试默认值"""
        settings = DistributedTaskSettings()
        assert settings.DEFAULT_CHUNK_SIZE == 10
        assert settings.DEFAULT_MAX_PARALLEL_CHUNKS == 5
        assert settings.TASK_TIMEOUT == 3600
        assert settings.RESULT_TTL == 86400


class TestSecuritySettings:
    """安全配置测试"""

    def test_default_values(self):
        """测试默认值"""
        settings = SecuritySettings()
        assert settings.MAX_CODE_SIZE == 10000
        assert settings.MAX_INPUT_SIZE == 1024
        assert settings.SANDBOX_ENABLED
        assert not settings.NETWORK_ACCESS
        assert "math" in settings.ALLOWED_MODULES
        assert "json" in settings.ALLOWED_MODULES


class TestSettings:
    """主配置类测试"""

    def test_default_values(self):
        """测试默认值"""
        settings = Settings()
        assert settings.APP_NAME == "闲置计算加速器"
        assert settings.APP_VERSION == "2.0.0"
        assert not settings.DEBUG

    def test_sub_settings(self):
        """测试子配置"""
        settings = Settings()
        assert isinstance(settings.SCHEDULER, SchedulerSettings)
        assert isinstance(settings.RESOURCE, ResourceSettings)
        assert isinstance(settings.WEB, WebUISettings)
        assert isinstance(settings.STORAGE, StorageSettings)
        assert isinstance(settings.DISTRIBUTED, DistributedTaskSettings)
        assert isinstance(settings.SECURITY, SecuritySettings)

    def test_compatibility_properties(self):
        """测试兼容性属性"""
        settings = Settings()
        assert settings.SCHEDULER_URL == settings.SCHEDULER.URL
        assert settings.REFRESH_INTERVAL == settings.WEB.REFRESH_INTERVAL
        assert settings.API_TIMEOUT == settings.SCHEDULER.API_TIMEOUT

    def test_to_dict(self):
        """测试转换为字典"""
        settings = Settings()
        config_dict = settings.to_dict()

        assert "APP_NAME" in config_dict
        assert "SCHEDULER" in config_dict
        assert "RESOURCE" in config_dict
        assert "WEB" in config_dict
        assert isinstance(config_dict["SCHEDULER"], dict)

    def test_ensure_directories(self, tmp_path):
        """测试目录创建"""
        settings = Settings(
            STORAGE=StorageSettings(
                USERS_DIR=str(tmp_path / "users"),
                NODE_DATA_DIR=str(tmp_path / "node_data"),
                LOG_DIR=str(tmp_path / "logs"),
                TEMP_DIR=str(tmp_path / "tmp"),
            )
        )
        settings.ensure_directories()

        assert Path(settings.STORAGE.USERS_DIR).exists()


class TestGetSettings:
    """测试配置获取函数"""

    def test_singleton(self):
        """测试单例模式"""
        settings1 = get_settings()
        settings2 = get_settings()

        # 应该是同一个实例
        assert settings1 is settings2

    def test_settings_instance(self):
        """测试返回类型"""
        settings = get_settings()
        assert isinstance(settings, Settings)


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
