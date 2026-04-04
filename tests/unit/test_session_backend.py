"""
单元测试 - 会话存储后端测试

测试 SessionBackend 接口及其实现
"""

import sys
import pytest
from unittest.mock import MagicMock, patch

from src.presentation.streamlit.utils.session_backend import (
    MemorySessionBackend,
    RedisSessionBackend,
    SessionBackend,
    SessionBackendFactory,
)


class TestMemorySessionBackend:
    """内存会话后端测试"""

    def setup_method(self):
        self.backend = MemorySessionBackend()

    def test_set_and_get_session(self):
        """测试设置和获取会话"""
        session_data = {"user_id": "test_user", "username": "testuser"}
        assert self.backend.set_session("session1", session_data)
        result = self.backend.get_session("session1")
        assert result == session_data

    def test_get_nonexistent_session(self):
        """测试获取不存在的会话"""
        result = self.backend.get_session("nonexistent")
        assert result is None

    def test_delete_session(self):
        """测试删除会话"""
        session_data = {"user_id": "test_user"}
        self.backend.set_session("session1", session_data)
        assert self.backend.delete_session("session1")
        assert self.backend.get_session("session1") is None

    def test_delete_nonexistent_session(self):
        """测试删除不存在的会话"""
        assert not self.backend.delete_session("nonexistent")

    def test_exists(self):
        """测试会话是否存在"""
        session_data = {"user_id": "test_user"}
        self.backend.set_session("session1", session_data)
        assert self.backend.exists("session1")
        assert not self.backend.exists("nonexistent")

    def test_set_with_ttl(self):
        """测试设置带 TTL 的会话"""
        session_data = {"user_id": "test_user"}
        assert self.backend.set_session("session1", session_data, ttl=3600)
        assert self.backend.get_session("session1") == session_data

    def test_update_session(self):
        """测试更新会话"""
        session_data1 = {"user_id": "test_user", "username": "user1"}
        session_data2 = {"user_id": "test_user", "username": "user2"}

        self.backend.set_session("session1", session_data1)
        self.backend.set_session("session1", session_data2)
        result = self.backend.get_session("session1")
        assert result == session_data2


class TestRedisSessionBackend:
    """Redis 会话后端测试"""

    def test_redis_not_installed(self):
        """测试 Redis 未安装时抛出 ImportError"""
        with patch.dict("sys.modules", {"redis": None}):
            with pytest.raises(ImportError, match="Redis support requires"):
                backend = RedisSessionBackend()
                backend._get_redis()

    def test_set_and_get_session(self):
        """测试设置和获取会话"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = b'{"user_id": "test_user"}'
        mock_redis.from_url.return_value = mock_redis

        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            backend = RedisSessionBackend()
            backend._redis = mock_redis
            backend._connected = True

            session_data = {"user_id": "test_user"}
            backend.set_session("session1", session_data)

            result = backend.get_session("session1")
            assert result == session_data

    def test_get_returns_none_on_error(self):
        """测试获取会话出错时返回 None"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.side_effect = Exception("Connection error")
        mock_redis.from_url.return_value = mock_redis

        backend = RedisSessionBackend()
        backend._redis = mock_redis
        backend._connected = True

        result = backend.get_session("session1")
        assert result is None

    def test_set_returns_false_on_error(self):
        """测试设置会话出错时返回 False"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.setex.side_effect = Exception("Connection error")
        mock_redis.from_url.return_value = mock_redis

        backend = RedisSessionBackend()
        backend._redis = mock_redis
        backend._connected = True

        result = backend.set_session("session1", {"user_id": "test"})
        assert result is False

    def test_delete_session(self):
        """测试删除会话"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.delete.return_value = 1
        mock_redis.from_url.return_value = mock_redis

        backend = RedisSessionBackend()
        backend._redis = mock_redis
        backend._connected = True

        assert backend.delete_session("session1")

    def test_exists(self):
        """测试会话是否存在"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.exists.return_value = 1
        mock_redis.from_url.return_value = mock_redis

        backend = RedisSessionBackend()
        backend._redis = mock_redis
        backend._connected = True

        assert backend.exists("session1")

    def test_connection_failure_fallback(self):
        """测试连接失败时回退"""
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception("Connection refused")
        mock_redis.from_url.return_value = mock_redis

        backend = RedisSessionBackend()
        backend._redis = mock_redis

        result = backend.get_session("session1")
        assert result is None


class TestSessionBackendFactory:
    """会话后端工厂测试"""

    def test_create_memory_backend(self):
        """测试创建内存后端"""
        backend = SessionBackendFactory.create_backend("memory")
        assert isinstance(backend, MemorySessionBackend)

    def test_create_redis_backend(self):
        """测试创建 Redis 后端"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.from_url.return_value = mock_redis

        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            backend = SessionBackendFactory.create_backend(
                "redis", redis_url="redis://localhost:6379/0"
            )
            assert isinstance(backend, RedisSessionBackend)

    def test_redis_fallback_on_connection_error(self):
        """测试 Redis 连接失败时回退到内存"""
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.side_effect = Exception("Connection refused")

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            backend = SessionBackendFactory.create_backend(
                "redis", redis_url="redis://localhost:6379/0"
            )
            assert isinstance(backend, MemorySessionBackend)

    def test_default_backend_is_memory(self):
        """测试默认后端是内存"""
        backend = SessionBackendFactory.create_backend()
        assert isinstance(backend, MemorySessionBackend)


class TestSessionBackendInterface:
    """测试 SessionBackend 抽象接口"""

    def test_cannot_instantiate_abstract_class(self):
        """测试不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            SessionBackend()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
