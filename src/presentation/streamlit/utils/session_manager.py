"""
会话管理工具

提供会话持久化和恢复功能：
- 服务端会话存储（内存/Redis/文件）
- URL 参数恢复
- 会话清理
- 支持可配置后端

注意：已弃用 localStorage 以避免 XSS 风险
"""

import hashlib
import json
import os
from typing import Any, Optional

import streamlit as st

from .session_backend import (
    FileSessionBackend,
    RedisSessionBackend,
    SessionBackend,
    SessionBackendFactory,
)


class SessionConfig:
    """会话配置"""

    def __init__(
        self,
        backend_type: str = "file",
        redis_url: Optional[str] = None,
        redis_key_prefix: str = "session:",
        session_ttl: int = 3600,
    ):
        self.backend_type = backend_type
        self.redis_url = redis_url or os.environ.get(
            "IDLE_SESSION_REDIS_URL", "redis://localhost:6379/0"
        )
        self.redis_key_prefix = redis_key_prefix
        self.session_ttl = session_ttl

    @classmethod
    def from_env(cls) -> "SessionConfig":
        """从环境变量创建配置"""
        return cls(
            backend_type=os.environ.get("IDLE_SESSION_BACKEND", "file"),
            redis_url=os.environ.get("IDLE_SESSION_REDIS_URL"),
            redis_key_prefix=os.environ.get("IDLE_SESSION_REDIS_PREFIX", "session:"),
            session_ttl=int(os.environ.get("IDLE_SESSION_TTL", "3600")),
        )


class SessionManager:
    """会话管理器"""

    SESSION_KEY = "user_session"
    HISTORY_KEY = "task_history"
    SESSION_TOKEN_KEY = "idle_accelerator_session"

    _backend: Optional[SessionBackend] = None
    _config: Optional[SessionConfig] = None

    @classmethod
    def configure(cls, config: Optional[SessionConfig] = None) -> None:
        """
        配置会话管理器

        Args:
            config: 会话配置，None 则从环境变量读取
        """
        cls._config = config or SessionConfig.from_env()
        cls._backend = SessionBackendFactory.create_backend(
            backend_type=cls._config.backend_type,
            redis_url=cls._config.redis_url,
            key_prefix=cls._config.redis_key_prefix,
            default_ttl=cls._config.session_ttl,
        )

    @classmethod
    def get_backend(cls) -> SessionBackend:
        """获取会话后端"""
        if cls._backend is None:
            cls.configure()
        return cls._backend

    @classmethod
    def get_config(cls) -> SessionConfig:
        """获取会话配置"""
        if cls._config is None:
            cls.configure()
        return cls._config

    @classmethod
    def _get_session_id(cls) -> str:
        """获取当前会话ID"""
        session = st.session_state.get(cls.SESSION_KEY)
        if session and "user_id" in session:
            return session["user_id"]
        return "anonymous"

    @staticmethod
    def init_session_state():
        """初始化会话状态"""
        if SessionManager.SESSION_KEY not in st.session_state:
            st.session_state[SessionManager.SESSION_KEY] = None

        if SessionManager.HISTORY_KEY not in st.session_state:
            st.session_state[SessionManager.HISTORY_KEY] = []

        if "active_node_id" not in st.session_state:
            st.session_state["active_node_id"] = None

        if "debug_mode" not in st.session_state:
            st.session_state["debug_mode"] = False

        if "resource_allocation" not in st.session_state:
            st.session_state["resource_allocation"] = {"cpu": 4.0, "memory": 4096}

    @staticmethod
    def get_user_session() -> Optional[dict[str, Any]]:
        """获取用户会话"""
        return st.session_state.get(SessionManager.SESSION_KEY)

    @staticmethod
    def set_user_session(user_id: str, username: str, **kwargs):
        """设置用户会话"""
        session_data = {"user_id": user_id, "username": username, **kwargs}
        st.session_state[SessionManager.SESSION_KEY] = session_data

        backend = SessionManager.get_backend()
        config = SessionManager.get_config()
        backend.set_session(user_id, session_data, ttl=config.session_ttl)

    @staticmethod
    def clear_user_session():
        """清除用户会话"""
        session = st.session_state.get(SessionManager.SESSION_KEY)
        if session and "user_id" in session:
            backend = SessionManager.get_backend()
            backend.delete_session(session["user_id"])

        st.session_state[SessionManager.SESSION_KEY] = None
        st.session_state[SessionManager.HISTORY_KEY] = []
        st.session_state["active_node_id"] = None

    @staticmethod
    def restore_session_from_backend(user_id: str) -> bool:
        """
        从后端存储恢复会话

        Args:
            user_id: 用户ID

        Returns:
            是否恢复成功
        """
        if st.session_state.get(SessionManager.SESSION_KEY):
            return False

        backend = SessionManager.get_backend()
        session_data = backend.get_session(user_id)

        if session_data:
            st.session_state[SessionManager.SESSION_KEY] = session_data
            return True

        return False

    @staticmethod
    def add_task_to_history(task_id: str, task_type: str = "单节点任务", **kwargs):
        """添加任务到历史记录"""
        from datetime import datetime

        history = st.session_state.get(SessionManager.HISTORY_KEY, [])
        history.append(
            {
                "task_id": task_id,
                "time": datetime.now().strftime("%H:%M:%S"),
                "status": "submitted",
                "type": task_type,
                **kwargs,
            }
        )
        st.session_state[SessionManager.HISTORY_KEY] = history

    @staticmethod
    def get_task_history() -> list:
        """获取任务历史"""
        return st.session_state.get(SessionManager.HISTORY_KEY, [])

    @staticmethod
    def restore_from_url_params():
        try:
            params = st.query_params

            if "user_id" in params and "username" in params:
                user_id = params["user_id"]
                username = params["username"]

                if not st.session_state.get(SessionManager.SESSION_KEY):
                    if SessionManager.restore_session_from_backend(user_id):
                        return True
                    SessionManager.set_user_session(user_id, username)
                    return True
        except Exception:
            pass

        return False

    @staticmethod
    def restore_from_session_token():
        """
        从会话令牌恢复会话

        通过 URL 参数传递的会话令牌从服务端存储恢复会话。
        不再使用 localStorage 以避免 XSS 风险。
        """
        if st.session_state.get(SessionManager.SESSION_KEY):
            return False

        restore_data = st.query_params.get_all("restore_session")
        if restore_data:
            try:
                import html

                sanitized = html.unescape(restore_data[0])
                session_data = json.loads(sanitized)
                if not SessionManager._validate_session_data(session_data):
                    return False
                user_id = session_data.get("user_id")
                backend = SessionManager.get_backend()
                stored_session = backend.get_session(user_id)
                if stored_session and stored_session.get("username") == session_data.get(
                    "username"
                ):
                    st.session_state[SessionManager.SESSION_KEY] = stored_session
                    st.query_params.pop("restore_session", None)
                    return True
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                pass

        return False

    restore_from_localstorage = restore_from_session_token

    @staticmethod
    def _validate_session_data(data: dict) -> bool:
        """验证会话数据格式和内容"""
        if not isinstance(data, dict):
            return False
        required_keys = {"user_id", "username"}
        if not required_keys.issubset(data.keys()):
            return False
        user_id = data.get("user_id", "")
        username = data.get("username", "")
        if not isinstance(user_id, str) or not isinstance(username, str):
            return False
        if len(user_id) > 64 or len(username) > 64:
            return False
        import re

        if not re.match(r"^local_[a-f0-9]{8}$", user_id):
            return False
        return bool(re.match(r"^[\u4e00-\u9fa5a-zA-Z0-9_]+$", username))

    @staticmethod
    def save_session(user_id: str, username: str, **kwargs):
        """
        保存会话到服务端存储

        Args:
            user_id: 用户ID
            username: 用户名
            **kwargs: 其他会话数据
        """
        session_data = {"user_id": user_id, "username": username, **kwargs}
        backend = SessionManager.get_backend()
        config = SessionManager.get_config()
        backend.set_session(user_id, session_data, ttl=config.session_ttl)

    save_to_localstorage = save_session

    @staticmethod
    def clear_session():
        """
        清除服务端会话存储

        删除当前用户的会话数据。
        """
        session = st.session_state.get(SessionManager.SESSION_KEY)
        if session and "user_id" in session:
            backend = SessionManager.get_backend()
            backend.delete_session(session["user_id"])

    clear_localstorage = clear_session

    @staticmethod
    def generate_user_id(username: str) -> str:
        """生成用户ID"""
        hash_value = hashlib.sha256(username.encode()).hexdigest()[:8]
        return f"local_{hash_value}"

    @staticmethod
    def get_backend_type() -> str:
        """获取当前后端类型"""
        backend = SessionManager.get_backend()
        if isinstance(backend, RedisSessionBackend):
            return "redis"
        if isinstance(backend, FileSessionBackend):
            return "file"
        return "memory"

    @staticmethod
    def is_redis_connected() -> bool:
        """检查 Redis 是否连接"""
        backend = SessionManager.get_backend()
        if isinstance(backend, RedisSessionBackend):
            return backend.is_connected
        return False


__all__ = ["SessionManager", "SessionConfig"]
