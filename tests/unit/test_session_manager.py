"""
单元测试 - 会话管理器测试

测试 SessionManager
"""

import pytest

from src.presentation.streamlit.utils.session_manager import SessionManager


class TestSessionManagerUserIdGeneration:
    """用户ID生成测试（不需要 Streamlit）"""

    def test_generate_user_id(self):
        """测试生成用户ID"""
        user_id = SessionManager.generate_user_id("testuser")
        assert user_id.startswith("local_")
        assert len(user_id) == 14  # "local_" + 8位hash

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
