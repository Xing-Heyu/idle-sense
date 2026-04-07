"""
会话存储后端抽象接口

提供可扩展的会话存储后端：
- 内存存储（默认）
- Redis 存储（支持水平扩展）
"""

import json
import platform
from abc import ABC, abstractmethod
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if platform.system() != "Windows":
    import fcntl
else:
    fcntl = None


class SessionBackend(ABC):
    """会话存储后端抽象接口"""

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """
        获取会话数据

        Args:
            session_id: 会话ID

        Returns:
            会话数据字典，不存在则返回 None
        """
        pass

    @abstractmethod
    def set_session(
        self, session_id: str, data: dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """
        设置会话数据

        Args:
            session_id: 会话ID
            data: 会话数据
            ttl: 过期时间（秒），None 表示永不过期

        Returns:
            是否设置成功
        """
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """
        检查会话是否存在

        Args:
            session_id: 会话ID

        Returns:
            是否存在
        """
        pass


class MemorySessionBackend(SessionBackend):
    """内存会话存储后端"""

    def __init__(self):
        self._sessions: dict[str, dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        return self._sessions.get(session_id)

    def set_session(
        self, session_id: str, data: dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        self._sessions[session_id] = data
        return True

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions


class RedisSessionBackend(SessionBackend):
    """Redis 会话存储后端"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "session:",
        default_ttl: int = 3600,
    ):
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._default_ttl = default_ttl
        self._redis: Any = None
        self._connected = False

    def _get_redis(self) -> Any:
        if self._redis is None:
            try:
                import redis

                self._redis = redis.from_url(self._redis_url)
                self._redis.ping()
                self._connected = True
            except ImportError:
                raise ImportError(
                    "Redis support requires the 'redis' package. "
                    "Install it with: pip install redis"
                ) from None
            except Exception:
                self._connected = False
                raise
        return self._redis

    def _make_key(self, session_id: str) -> str:
        return f"{self._key_prefix}{session_id}"

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        try:
            redis_client = self._get_redis()
            data = redis_client.get(self._make_key(session_id))
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    def set_session(
        self, session_id: str, data: dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        try:
            redis_client = self._get_redis()
            key = self._make_key(session_id)
            value = json.dumps(data, ensure_ascii=False)
            actual_ttl = ttl if ttl is not None else self._default_ttl

            if actual_ttl > 0:
                redis_client.setex(key, actual_ttl, value)
            else:
                redis_client.set(key, value)
            return True
        except Exception:
            return False

    def delete_session(self, session_id: str) -> bool:
        try:
            redis_client = self._get_redis()
            result = redis_client.delete(self._make_key(session_id))
            return result > 0
        except Exception:
            return False

    def exists(self, session_id: str) -> bool:
        try:
            redis_client = self._get_redis()
            return bool(redis_client.exists(self._make_key(session_id)))
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected


class FileSessionBackend(SessionBackend):
    """文件会话存储后端（JSON 文件）"""

    def __init__(
        self,
        session_dir: str = "data/sessions",
        default_ttl: int = 3600,
    ):
        self._session_dir = Path(session_dir)
        self._default_ttl = default_ttl
        self._session_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, session_id: str) -> Path:
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self._session_dir / f"session_{safe_id}.json"

    def _is_expired(self, session_data: dict[str, Any]) -> bool:
        expires_at = session_data.get("expires_at")
        if not expires_at:
            return False
        try:
            if isinstance(expires_at, (int, float)):
                exp_time = datetime.fromtimestamp(expires_at, tz=timezone.utc)
            else:
                exp_time = datetime.fromisoformat(expires_at)
            return datetime.now(timezone.utc) > exp_time
        except (ValueError, TypeError):
            return True

    def _acquire_lock(self, file_obj, exclusive: bool = False) -> bool:
        if fcntl is not None:
            try:
                lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(file_obj, lock_type)
                return True
            except OSError:
                return False
        return True

    def _release_lock(self, file_obj) -> None:
        if fcntl is not None:
            with suppress(OSError):
                fcntl.flock(file_obj, fcntl.LOCK_UN)

    def _read_session(self, file_path: Path) -> Optional[dict[str, Any]]:
        try:
            with open(file_path, encoding="utf-8") as f:
                self._acquire_lock(f, exclusive=False)
                try:
                    data = json.load(f)
                    if self._is_expired(data):
                        self._release_lock(f)
                        file_path.unlink(missing_ok=True)
                        return None
                    return data
                finally:
                    self._release_lock(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        file_path = self._get_file_path(session_id)
        data = self._read_session(file_path)
        if data:
            return data.get("data")
        return None

    def set_session(
        self, session_id: str, data: dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        file_path = self._get_file_path(session_id)
        actual_ttl = ttl if ttl is not None else self._default_ttl
        now = datetime.now(timezone.utc)
        session_entry = {
            "data": data,
            "created_at": now.isoformat(),
            "expires_at": (now.timestamp() + actual_ttl)
            if actual_ttl > 0
            else None,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                self._acquire_lock(f, exclusive=True)
                try:
                    json.dump(session_entry, f, ensure_ascii=False, indent=2)
                finally:
                    self._release_lock(f)
            return True
        except OSError:
            return False

    def delete_session(self, session_id: str) -> bool:
        file_path = self._get_file_path(session_id)
        try:
            file_path.unlink()
            return True
        except FileNotFoundError:
            return False

    def exists(self, session_id: str) -> bool:
        file_path = self._get_file_path(session_id)
        data = self._read_session(file_path)
        return data is not None


class SessionBackendFactory:
    """会话后端工厂"""

    @staticmethod
    def create_backend(
        backend_type: str = "memory",
        redis_url: Optional[str] = None,
        key_prefix: str = "session:",
        default_ttl: int = 3600,
        session_dir: str = "data/sessions",
    ) -> SessionBackend:
        """
        创建会话后端

        Args:
            backend_type: 后端类型 ("memory", "redis" 或 "file")
            redis_url: Redis 连接URL
            key_prefix: Redis 键前缀
            default_ttl: 默认过期时间（秒）
            session_dir: 文件后端的会话存储目录

        Returns:
            SessionBackend 实例
        """
        if backend_type == "redis":
            if redis_url is None:
                redis_url = "redis://localhost:6379/0"

            try:
                backend = RedisSessionBackend(
                    redis_url=redis_url,
                    key_prefix=key_prefix,
                    default_ttl=default_ttl,
                )
                backend._get_redis()
                return backend
            except Exception:
                return MemorySessionBackend()

        if backend_type == "file":
            return FileSessionBackend(
                session_dir=session_dir,
                default_ttl=default_ttl,
            )

        return MemorySessionBackend()


__all__ = [
    "SessionBackend",
    "MemorySessionBackend",
    "RedisSessionBackend",
    "FileSessionBackend",
    "SessionBackendFactory",
]
