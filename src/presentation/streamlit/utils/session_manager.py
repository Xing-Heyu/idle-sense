"""
会话管理工具

提供会话持久化和恢复功能：
- localStorage 恢复
- URL 参数恢复
- 会话清理
"""

import hashlib
import json
from typing import Any, Optional

import streamlit as st


class SessionManager:
    """会话管理器"""

    SESSION_KEY = "user_session"
    HISTORY_KEY = "task_history"
    LOCAL_STORAGE_KEY = "idle_accelerator_session"

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
            st.session_state["resource_allocation"] = {
                "cpu": 4.0,
                "memory": 4096
            }

    @staticmethod
    def get_user_session() -> Optional[dict[str, Any]]:
        """获取用户会话"""
        return st.session_state.get(SessionManager.SESSION_KEY)

    @staticmethod
    def set_user_session(user_id: str, username: str, **kwargs):
        """设置用户会话"""
        st.session_state[SessionManager.SESSION_KEY] = {
            "user_id": user_id,
            "username": username,
            **kwargs
        }

    @staticmethod
    def clear_user_session():
        """清除用户会话"""
        st.session_state[SessionManager.SESSION_KEY] = None
        st.session_state[SessionManager.HISTORY_KEY] = []
        st.session_state["active_node_id"] = None

    @staticmethod
    def add_task_to_history(task_id: str, task_type: str = "单节点任务", **kwargs):
        """添加任务到历史记录"""
        from datetime import datetime

        history = st.session_state.get(SessionManager.HISTORY_KEY, [])
        history.append({
            "task_id": task_id,
            "time": datetime.now().strftime("%H:%M:%S"),
            "status": "submitted",
            "type": task_type,
            **kwargs
        })
        st.session_state[SessionManager.HISTORY_KEY] = history

    @staticmethod
    def get_task_history() -> list:
        """获取任务历史"""
        return st.session_state.get(SessionManager.HISTORY_KEY, [])

    @staticmethod
    def restore_from_url_params():
        """从URL参数恢复会话"""
        try:
            params = st.query_params

            if "user_id" in params and "username" in params:
                user_id = params["user_id"]
                username = params["username"]

                if not st.session_state.get(SessionManager.SESSION_KEY):
                    SessionManager.set_user_session(user_id, username)
                    return True
        except Exception:
            pass

        return False

    @staticmethod
    def restore_from_localstorage():
        """从 localStorage 恢复会话"""
        if st.session_state.get(SessionManager.SESSION_KEY):
            return False

        st.markdown("""
        <script>
        const savedSession = localStorage.getItem('idle_accelerator_session');
        if (savedSession) {
            try {
                const sessionData = JSON.parse(savedSession);
                const url = new URL(window.location.href);
                url.searchParams.set('restore_session', savedSession);
                window.history.replaceState({}, '', url);
            } catch(e) {}
        }
        </script>
        """, unsafe_allow_html=True)

        restore_data = st.query_params.get_all("restore_session")
        if restore_data:
            try:
                session_data = json.loads(restore_data[0])
                if session_data.get("user_id") and session_data.get("username"):
                    st.session_state[SessionManager.SESSION_KEY] = session_data
                    st.query_params.pop("restore_session", None)
                    return True
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        return False

    @staticmethod
    def save_to_localstorage(user_id: str, username: str, **kwargs):
        """保存会话到 localStorage"""
        session_data = {
            "user_id": user_id,
            "username": username,
            **kwargs
        }
        session_json = json.dumps(session_data, ensure_ascii=False)
        st.markdown(f"""
        <script>
        localStorage.setItem('idle_accelerator_session', '{session_json}');
        </script>
        """, unsafe_allow_html=True)

    @staticmethod
    def clear_localstorage():
        """清除 localStorage 中的会话"""
        st.markdown("""
        <script>
        localStorage.removeItem('idle_accelerator_session');
        </script>
        """, unsafe_allow_html=True)

    @staticmethod
    def generate_user_id(username: str) -> str:
        """生成用户ID"""
        hash_value = hashlib.md5(username.encode()).hexdigest()[:8]
        return f"local_{hash_value}"


__all__ = ["SessionManager"]
