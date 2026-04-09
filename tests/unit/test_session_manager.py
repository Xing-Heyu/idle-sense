"""
单元测试 - 会话管理器测试

测试 SessionManager 和 SessionConfig
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

from src.presentation.streamlit.utils.session_manager import SessionConfig, SessionManager
from src.presentation.streamlit.utils.session_backend import (
    FileSessionBackend,
    MemorySessionBackend,
    RedisSessionBackend,
)


class TestSessionManagerUserIdGeneration:
    """用户ID生成测试（不需要 Streamlit）"""

    def test_generate_user_id(self):
        """测试生成用户ID"""
        user_id = SessionManager.generate_user_id("testuser")
        assert user_id.startswith("local_")
        assert len(user_id) == 14

    def test_generate_user_id_consistent(self):
        """测试相同用户名生成相同ID"""
        id1 = SessionManager.generate_user_id("testuser")
        id2 = SessionManager.generate_user_id("testuser")
        assert id1 == id2

    def test_generate_user_id_different(self):
        """测试不同用户名生成不同ID"""
        id1 = SessionManager.generate_user_id("user1")
        id2 = SessionManager.generate_user_id("user2")
        assert id1 != id2

    def test_generate_user_id_chinese(self):
        """测试中文用户名"""
        user_id = SessionManager.generate_user_id("测试用户")
        assert user_id.startswith("local_")
        assert len(user_id) == 14

    def test_generate_user_id_empty(self):
        """测试空用户名"""
        user_id = SessionManager.generate_user_id("")
        assert user_id.startswith("local_")
        assert len(user_id) == 14

    def test_generate_user_id_long(self):
        """测试长用户名"""
        long_name = "a" * 100
        user_id = SessionManager.generate_user_id(long_name)
        assert user_id.startswith("local_")
        assert len(user_id) == 14


class TestSessionManagerConstants:
    """常量测试"""

    def test_session_key_constant(self):
        """测试会话键常量"""
        assert SessionManager.SESSION_KEY == "user_session"

    def test_history_key_constant(self):
        """测试历史键常量"""
        assert SessionManager.HISTORY_KEY == "task_history"


class TestSessionConfig:
    """会话配置测试"""

    def test_default_config(self):
        config = SessionConfig()
        assert config.backend_type == "file"
        assert config.redis_key_prefix == "session:"
        assert config.session_ttl == 3600

    def test_custom_config(self):
        """测试自定义配置"""
        config = SessionConfig(
            backend_type="redis",
            redis_url="redis://custom:6379/1",
            redis_key_prefix="custom:",
            session_ttl=7200,
        )
        assert config.backend_type == "redis"
        assert config.redis_url == "redis://custom:6379/1"
        assert config.redis_key_prefix == "custom:"
        assert config.session_ttl == 7200

    def test_from_env_default(self):
        config = SessionConfig.from_env()
        assert config.backend_type == "file"
        assert config.session_ttl == 3600

    def test_from_env_custom(self, monkeypatch):
        """测试从环境变量创建配置（自定义值）"""
        monkeypatch.setenv("IDLE_SESSION_BACKEND", "redis")
        monkeypatch.setenv("IDLE_SESSION_REDIS_URL", "redis://env:6379/2")
        monkeypatch.setenv("IDLE_SESSION_REDIS_PREFIX", "env:")
        monkeypatch.setenv("IDLE_SESSION_TTL", "1800")

        config = SessionConfig.from_env()
        assert config.backend_type == "redis"
        assert config.redis_url == "redis://env:6379/2"
        assert config.redis_key_prefix == "env:"
        assert config.session_ttl == 1800


class TestSessionManagerBackend:
    """会话管理器后端测试"""

    def setup_method(self):
        SessionManager._backend = None
        SessionManager._config = None

    def test_default_backend_is_file(self):
        backend = SessionManager.get_backend()
        assert isinstance(backend, FileSessionBackend)

    def test_configure_memory_backend(self):
        """测试配置内存后端"""
        config = SessionConfig(backend_type="memory")
        SessionManager.configure(config)
        backend = SessionManager.get_backend()
        assert isinstance(backend, MemorySessionBackend)

    def test_configure_redis_backend(self):
        """测试配置 Redis 后端"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.from_url.return_value = mock_redis

        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            config = SessionConfig(
                backend_type="redis",
                redis_url="redis://localhost:6379/0",
            )
            SessionManager.configure(config)
            backend = SessionManager.get_backend()
            assert isinstance(backend, RedisSessionBackend)

    def test_redis_fallback_on_error(self):
        """测试 Redis 连接失败时回退到内存"""
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.side_effect = Exception("Connection refused")

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            config = SessionConfig(
                backend_type="redis",
                redis_url="redis://localhost:6379/0",
            )
            SessionManager.configure(config)
            backend = SessionManager.get_backend()
            assert isinstance(backend, MemorySessionBackend)

    def test_get_backend_type_memory(self):
        """测试获取后端类型（内存）"""
        config = SessionConfig(backend_type="memory")
        SessionManager.configure(config)
        assert SessionManager.get_backend_type() == "memory"

    def test_is_redis_connected_memory(self):
        """测试 Redis 连接状态（内存后端）"""
        config = SessionConfig(backend_type="memory")
        SessionManager.configure(config)
        assert not SessionManager.is_redis_connected()


class TestSessionManagerBackendOperations:
    """会话管理器后端操作测试"""

    def setup_method(self):
        SessionManager._backend = None
        SessionManager._config = None
        config = SessionConfig(backend_type="memory", session_ttl=3600)
        SessionManager.configure(config)

    def test_set_session_stores_in_backend(self):
        """测试设置会话存储到后端"""
        backend = SessionManager.get_backend()
        user_id = "test_user_001"

        SessionManager.set_user_session(user_id, "testuser", role="admin")

        stored = backend.get_session(user_id)
        assert stored is not None
        assert stored["user_id"] == user_id
        assert stored["username"] == "testuser"
        assert stored["role"] == "admin"

    def test_clear_session_deletes_from_backend(self):
        """测试清除会话从后端删除"""
        backend = SessionManager.get_backend()
        user_id = "test_user_002"

        SessionManager.set_user_session(user_id, "testuser")
        assert backend.exists(user_id)

        SessionManager._backend = backend
        SessionManager.clear_user_session()

    def test_restore_session_from_backend(self):
        """测试从后端恢复会话"""
        backend = SessionManager.get_backend()
        user_id = "test_user_003"
        session_data = {"user_id": user_id, "username": "restored_user"}

        backend.set_session(user_id, session_data)

        mock_session_state = {}
        with patch("streamlit.session_state", mock_session_state):
            result = SessionManager.restore_session_from_backend(user_id)
            assert result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
