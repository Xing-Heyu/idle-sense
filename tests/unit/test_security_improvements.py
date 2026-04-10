"""
test_security_improvements.py
安全改进测试 - 密码认证、权限验证、配额限制
"""

from datetime import datetime, timedelta

import pytest

from legacy.user_management import (
    AuthManager,
    PermissionDeniedError,
    PermissionValidator,
    QuotaManager,
    User,
    UserQuota,
    hash_password,
    verify_password,
)


class TestPasswordAuthentication:
    """密码认证测试"""

    def test_password_hashing(self):
        """测试密码哈希"""
        password = "test_password_123"
        hash1, salt1 = hash_password(password)
        hash2, salt2 = hash_password(password)

        assert hash1 != hash2
        assert salt1 != salt2
        assert len(salt1) == 32

    def test_password_verification(self):
        """测试密码验证"""
        password = "correct_password"
        hash_value, salt = hash_password(password)

        assert verify_password(password, hash_value, salt) is True
        assert verify_password("wrong_password", hash_value, salt) is False

    def test_user_password_set_and_verify(self):
        """测试用户密码设置和验证"""
        user = User("testuser", "test@example.com", "initial_password")

        assert user.verify_password("initial_password") is True
        assert user.verify_password("wrong_password") is False

    def test_user_password_change(self):
        """测试用户修改密码"""
        user = User("testuser", "test@example.com", "old_password")

        user.set_password("new_password")

        assert user.verify_password("old_password") is False
        assert user.verify_password("new_password") is True

    def test_user_without_password(self):
        """测试无密码用户"""
        user = User("nopass", "nopass@example.com")

        assert user.password_hash is None
        assert user.password_salt is None
        assert user.verify_password("any_password") is False


class TestUserRegistrationWithPassword:
    """用户注册测试（带密码）"""

    def test_register_user_with_password(self):
        """测试带密码注册用户"""
        auth = AuthManager()
        result = auth.register_user("newuser", "new@example.com", "password123")

        assert result["success"] is True
        assert "user_id" in result
        assert result["user"]["has_password"] is True

    def test_register_user_password_too_short(self):
        """测试密码太短"""
        auth = AuthManager()
        result = auth.register_user("shortpass", "short@example.com", "123")

        assert result["success"] is False
        assert "密码长度" in result["error"]

    def test_register_user_empty_password(self):
        """测试空密码"""
        auth = AuthManager()
        result = auth.register_user("emptypass", "empty@example.com", "")

        assert result["success"] is False

    def test_register_duplicate_username(self):
        """测试重复用户名"""
        auth = AuthManager()
        auth.register_user("duplicate", "dup1@example.com", "password123")
        result = auth.register_user("duplicate", "dup2@example.com", "password123")

        assert result["success"] is False
        assert "用户名已存在" in result["error"]


class TestUserLogin:
    """用户登录测试"""

    def test_login_success(self):
        """测试登录成功"""
        auth = AuthManager()
        auth.register_user("loginuser", "login@example.com", "correct_password")

        result = auth.login("loginuser", "correct_password")

        assert result["success"] is True
        assert "session_id" in result
        assert result["user"]["username"] == "loginuser"

    def test_login_wrong_password(self):
        """测试密码错误"""
        auth = AuthManager()
        auth.register_user("wrongpass", "wrong@example.com", "correct_password")

        result = auth.login("wrongpass", "wrong_password")

        assert result["success"] is False
        assert "密码错误" in result["error"]

    def test_login_nonexistent_user(self):
        """测试不存在的用户"""
        auth = AuthManager()
        result = auth.login("nonexistent", "any_password")

        assert result["success"] is False

    def test_login_disabled_user(self):
        """测试被禁用的用户"""
        auth = AuthManager()
        auth.register_user("disabled", "disabled@example.com", "password123")

        user = auth.get_user_by_username("disabled")
        user.is_active = False

        result = auth.login("disabled", "password123")

        assert result["success"] is False
        assert "禁用" in result["error"]

    def test_logout(self):
        """测试登出"""
        auth = AuthManager()
        auth.register_user("logoutuser", "logout@example.com", "password123")
        result = auth.login("logoutuser", "password123")

        session_id = result["session_id"]

        assert auth.validate_session(session_id) is not None

        auth.logout(session_id)

        assert auth.validate_session(session_id) is None


class TestQuotaEnforcement:
    """配额强制限制测试"""

    def test_quota_default_values(self):
        """测试默认配额值"""
        quota = UserQuota("user123")

        assert quota.daily_tasks_limit == UserQuota.DEFAULT_DAILY_LIMIT
        assert quota.concurrent_tasks_limit == UserQuota.DEFAULT_CONCURRENT_LIMIT
        assert quota.cpu_quota == UserQuota.DEFAULT_CPU_QUOTA
        assert quota.memory_quota == UserQuota.DEFAULT_MEMORY_QUOTA

    def test_quota_custom_values(self):
        """测试自定义配额值"""
        quota = UserQuota(
            "user123",
            daily_tasks_limit=50,
            concurrent_tasks_limit=3,
            cpu_quota=2.0,
            memory_quota=2048,
        )

        assert quota.daily_tasks_limit == 50
        assert quota.concurrent_tasks_limit == 3
        assert quota.cpu_quota == 2.0
        assert quota.memory_quota == 2048

    def test_quota_can_submit_task(self):
        """测试任务提交检查"""
        quota = UserQuota("user123", daily_tasks_limit=10, concurrent_tasks_limit=2)
        UserQuota.set_enforce_limits(True)

        assert quota.can_submit_task() is True

        quota.daily_usage = 10
        assert quota.can_submit_task() is False
        assert "每日任务上限" in quota.get_rejection_reason()

    def test_quota_concurrent_limit(self):
        """测试并发任务限制"""
        quota = UserQuota("user123", daily_tasks_limit=100, concurrent_tasks_limit=2)
        UserQuota.set_enforce_limits(True)

        quota.current_tasks = 2
        assert quota.can_submit_task() is False
        assert "并发任务上限" in quota.get_rejection_reason()

    def test_quota_no_enforcement(self):
        """测试不强制执行配额"""
        quota = UserQuota("user123", daily_tasks_limit=1, concurrent_tasks_limit=1)
        UserQuota.set_enforce_limits(False)

        quota.daily_usage = 100
        quota.current_tasks = 100

        assert quota.can_submit_task() is True

        UserQuota.set_enforce_limits(True)

    def test_quota_daily_reset(self):
        """测试每日重置"""
        quota = UserQuota("user123", daily_tasks_limit=10)
        quota.daily_usage = 5
        quota.last_reset_date = (datetime.now() - timedelta(days=1)).date()

        quota._reset_daily_if_needed()

        assert quota.daily_usage == 0


class TestQuotaManager:
    """配额管理器测试"""

    def test_check_quota_allowed(self):
        """测试配额检查允许"""
        manager = QuotaManager()
        UserQuota.set_enforce_limits(True)

        result = manager.check_quota("user123")

        assert result["allowed"] is True

    def test_check_quota_denied(self):
        """测试配额检查拒绝"""
        manager = QuotaManager()
        UserQuota.set_enforce_limits(True)

        manager.set_user_quota("user123", daily_tasks_limit=1)
        manager.consume_quota("user123")

        result = manager.check_quota("user123")

        assert result["allowed"] is False
        assert "reason" in result

    def test_consume_quota(self):
        """测试消耗配额"""
        manager = QuotaManager()
        UserQuota.set_enforce_limits(True)

        manager.set_user_quota("user123", daily_tasks_limit=5)

        assert manager.consume_quota("user123") is True
        assert manager.consume_quota("user123") is True

        stats = manager.get_usage_stats("user123")
        assert stats["daily_usage"] == 2

    def test_consume_quota_exceeded(self):
        """测试超出配额"""
        manager = QuotaManager()
        UserQuota.set_enforce_limits(True)

        manager.set_user_quota("user123", daily_tasks_limit=1)
        manager.consume_quota("user123")

        assert manager.consume_quota("user123") is False

    def test_release_quota(self):
        """测试释放配额"""
        manager = QuotaManager()
        manager.set_user_quota("user123", concurrent_tasks_limit=2)

        manager.consume_quota("user123")
        manager.consume_quota("user123")

        stats = manager.get_usage_stats("user123")
        assert stats["current_tasks"] == 2

        manager.release_quota("user123")

        stats = manager.get_usage_stats("user123")
        assert stats["current_tasks"] == 1


class TestPermissionValidator:
    """权限验证器测试"""

    @pytest.fixture
    def setup_auth(self):
        """设置认证环境"""
        auth = AuthManager()
        auth.register_user("perm_user", "perm@example.com", "password123")
        result = auth.login("perm_user", "password123")
        session_id = result["session_id"]
        user_id = result["user_id"]

        validator = PermissionValidator(auth)

        return auth, validator, session_id, user_id

    def test_validate_session_success(self, setup_auth):
        """测试会话验证成功"""
        auth, validator, session_id, user_id = setup_auth

        validated_id = validator.validate_session(session_id)

        assert validated_id == user_id

    def test_validate_session_invalid(self, setup_auth):
        """测试无效会话"""
        auth, validator, session_id, user_id = setup_auth

        with pytest.raises(PermissionDeniedError) as exc_info:
            validator.validate_session("invalid_session_id")

        assert "无效会话" in str(exc_info.value)

    def test_validate_resource_ownership_success(self, setup_auth):
        """测试资源所有权验证成功"""
        auth, validator, session_id, user_id = setup_auth

        result = validator.validate_resource_ownership(session_id, user_id)

        assert result == user_id

    def test_validate_resource_ownership_denied(self, setup_auth):
        """测试资源所有权验证拒绝"""
        auth, validator, session_id, user_id = setup_auth

        with pytest.raises(PermissionDeniedError) as exc_info:
            validator.validate_resource_ownership(session_id, "other_user_id")

        assert "无权操作" in str(exc_info.value)

    def test_validate_disabled_user(self, setup_auth):
        """测试禁用用户"""
        auth, validator, session_id, user_id = setup_auth

        user = auth.get_user_by_id(user_id)
        user.is_active = False

        with pytest.raises(PermissionDeniedError) as exc_info:
            validator.validate_resource_ownership(session_id, user_id)

        assert "禁用" in str(exc_info.value)


class TestAuthManagerPermission:
    """认证管理器权限测试"""

    def test_verify_permission_success(self):
        """测试权限验证成功"""
        auth = AuthManager()
        auth.register_user("perm_test", "perm_test@example.com", "password123")
        result = auth.login("perm_test", "password123")

        session_id = result["session_id"]
        user_id = result["user_id"]

        perm_result = auth.verify_permission(session_id, user_id)

        assert perm_result["allowed"] is True

    def test_verify_permission_wrong_user(self):
        """测试权限验证错误用户"""
        auth = AuthManager()
        auth.register_user("perm_test2", "perm_test2@example.com", "password123")
        result = auth.login("perm_test2", "password123")

        session_id = result["session_id"]

        perm_result = auth.verify_permission(session_id, "other_user_id")

        assert perm_result["allowed"] is False
        assert "无权操作" in perm_result["error"]

    def test_verify_permission_invalid_session(self):
        """测试权限验证无效会话"""
        auth = AuthManager()

        perm_result = auth.verify_permission("invalid_session", "any_user_id")

        assert perm_result["allowed"] is False
        assert "无效会话" in perm_result["error"]


class TestChangePassword:
    """修改密码测试"""

    def test_change_password_success(self):
        """测试修改密码成功"""
        auth = AuthManager()
        auth.register_user("change_pass", "change@example.com", "old_password")
        result = auth.login("change_pass", "old_password")
        user_id = result["user_id"]

        change_result = auth.change_password(user_id, "old_password", "new_password123")

        assert change_result["success"] is True

        auth.logout(result["session_id"])
        login_result = auth.login("change_pass", "new_password123")

        assert login_result["success"] is True

    def test_change_password_wrong_old(self):
        """测试原密码错误"""
        auth = AuthManager()
        auth.register_user("change_pass2", "change2@example.com", "correct_old")
        result = auth.login("change_pass2", "correct_old")
        user_id = result["user_id"]

        change_result = auth.change_password(user_id, "wrong_old", "new_password123")

        assert change_result["success"] is False
        assert "原密码错误" in change_result["error"]

    def test_change_password_too_short(self):
        """测试新密码太短"""
        auth = AuthManager()
        auth.register_user("change_pass3", "change3@example.com", "old_password")
        result = auth.login("change_pass3", "old_password")
        user_id = result["user_id"]

        change_result = auth.change_password(user_id, "old_password", "123")

        assert change_result["success"] is False
        assert "密码长度" in change_result["error"]


class TestIntegration:
    """集成测试"""

    def test_full_user_flow(self):
        """测试完整用户流程"""
        auth = AuthManager()
        quota_manager = QuotaManager()
        UserQuota.set_enforce_limits(True)

        reg_result = auth.register_user("full_flow", "full@example.com", "password123")
        assert reg_result["success"] is True
        user_id = reg_result["user_id"]

        login_result = auth.login("full_flow", "password123")
        assert login_result["success"] is True
        session_id = login_result["session_id"]

        perm_result = auth.verify_permission(session_id, user_id)
        assert perm_result["allowed"] is True

        quota_manager.set_user_quota(user_id, daily_tasks_limit=5, concurrent_tasks_limit=2)

        assert quota_manager.consume_quota(user_id) is True
        assert quota_manager.consume_quota(user_id) is True

        stats = quota_manager.get_usage_stats(user_id)
        assert stats["daily_usage"] == 2
        assert stats["current_tasks"] == 2

        quota_manager.release_quota(user_id)
        stats = quota_manager.get_usage_stats(user_id)
        assert stats["current_tasks"] == 1

        auth.logout(session_id)

        perm_result = auth.verify_permission(session_id, user_id)
        assert perm_result["allowed"] is False

    def test_multi_user_isolation(self):
        """测试多用户隔离"""
        auth = AuthManager()
        quota_manager = QuotaManager()
        UserQuota.set_enforce_limits(True)

        reg1 = auth.register_user("multi_iso_1", "multi_iso_1@example.com", "password1")
        reg2 = auth.register_user("multi_iso_2", "multi_iso_2@example.com", "password2")

        assert reg1["success"] is True, f"注册用户1失败: {reg1.get('error')}"
        assert reg2["success"] is True, f"注册用户2失败: {reg2.get('error')}"

        login1 = auth.login("multi_iso_1", "password1")
        login2 = auth.login("multi_iso_2", "password2")

        assert login1["success"] is True, f"登录用户1失败: {login1.get('error')}"
        assert login2["success"] is True, f"登录用户2失败: {login2.get('error')}"

        session1 = login1["session_id"]
        session2 = login2["session_id"]
        user_id1 = login1["user_id"]
        user_id2 = login2["user_id"]

        assert auth.verify_permission(session1, user_id1)["allowed"] is True
        assert auth.verify_permission(session1, user_id2)["allowed"] is False
        assert auth.verify_permission(session2, user_id2)["allowed"] is True
        assert auth.verify_permission(session2, user_id1)["allowed"] is False

        quota_manager.set_user_quota(user_id1, daily_tasks_limit=1)
        quota_manager.set_user_quota(user_id2, daily_tasks_limit=10)

        assert quota_manager.consume_quota(user_id1) is True
        assert quota_manager.consume_quota(user_id1) is False

        assert quota_manager.consume_quota(user_id2) is True
        assert quota_manager.consume_quota(user_id2) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
