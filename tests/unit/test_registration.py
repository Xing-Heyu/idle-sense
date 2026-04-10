"""
单元测试 - 注册异常类和注册用例审计日志测试

测试 RegistrationError 异常类和 RegisterUseCase 的审计日志记录
"""

import json
from unittest.mock import Mock

import pytest

from src.core.exceptions import (
    IdleSenseError,
    RegistrationError,
    RegistrationPermissionError,
    StorageError,
    UserDataConflictError,
    UsernameValidationError,
)
from src.core.use_cases.auth.register_use_case import (
    RegisterRequest,
    RegisterResponse,
    RegisterUseCase,
)
from src.infrastructure.audit import AuditAction, AuditLogger


class TestRegistrationExceptions:
    """注册异常类测试"""

    def test_registration_error_base(self):
        """测试 RegistrationError 基类"""
        error = RegistrationError("注册失败")
        assert isinstance(error, IdleSenseError)
        assert error.message == "注册失败"
        assert error.code == "REGISTRATION_ERROR"

    def test_registration_error_with_details(self):
        """测试带详情的 RegistrationError"""
        error = RegistrationError("注册失败", code="CUSTOM_ERROR", details={"field": "username"})
        assert error.code == "CUSTOM_ERROR"
        assert error.details["field"] == "username"

    def test_username_validation_error(self):
        """测试 UsernameValidationError"""
        error = UsernameValidationError("用户名格式错误", username="test@user", field="username")
        assert error.code == "USERNAME_VALIDATION_ERROR"
        assert error.details["username"] == "test@user"
        assert error.details["field"] == "username"

    def test_storage_error(self):
        """测试 StorageError"""
        error = StorageError(
            "磁盘空间不足", path="/local_users", original_error="No space left on device"
        )
        assert error.code == "STORAGE_ERROR"
        assert error.details["path"] == "/local_users"
        assert error.details["original_error"] == "No space left on device"

    def test_registration_permission_error(self):
        """测试 RegistrationPermissionError"""
        error = RegistrationPermissionError(
            "权限不足", path="/local_users", required_permission="write"
        )
        assert error.code == "REGISTRATION_PERMISSION_ERROR"
        assert error.details["path"] == "/local_users"
        assert error.details["required_permission"] == "write"

    def test_user_data_conflict_error(self):
        """测试 UserDataConflictError"""
        error = UserDataConflictError(
            "用户ID冲突", user_id="local_abc123", conflict_type="duplicate_id"
        )
        assert error.code == "USER_DATA_CONFLICT_ERROR"
        assert error.details["user_id"] == "local_abc123"
        assert error.details["conflict_type"] == "duplicate_id"

    def test_exception_to_dict(self):
        """测试异常转换为字典"""
        error = StorageError("存储错误", path="/test")
        result = error.to_dict()
        assert result["error"] == "STORAGE_ERROR"
        assert result["message"] == "存储错误"
        assert result["details"]["path"] == "/test"


class TestRegisterUseCaseWithAudit:
    """注册用例审计日志测试"""

    def setup_method(self):
        self.mock_repo = Mock()
        self.mock_audit_logger = Mock(spec=AuditLogger)
        self.mock_repo.find_available_username.return_value = "testuser"
        self.mock_user = Mock()
        self.mock_user.user_id = "local_test123"
        self.mock_user.username = "testuser"
        self.mock_repo.save.return_value = self.mock_user
        self.use_case = RegisterUseCase(self.mock_repo, self.mock_audit_logger)

    def test_register_success_logs_audit(self):
        """测试注册成功时记录审计日志"""
        request = RegisterRequest(username="testuser", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is True
        self.mock_audit_logger.log.assert_called_once()
        call_args = self.mock_audit_logger.log.call_args
        assert call_args.kwargs["action"] == AuditAction.USER_REGISTER
        assert call_args.kwargs["user_id"] == "local_test123"
        assert call_args.kwargs["resource_type"] == "user"
        assert call_args.kwargs["details"]["status"] == "success"
        assert call_args.kwargs["details"]["username"] == "testuser"

    def test_register_permission_error_logs_audit(self):
        """测试权限错误时记录审计日志"""
        self.mock_repo.save.side_effect = PermissionError("Access denied")

        request = RegisterRequest(username="testuser", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False
        assert response.error_code == "PERMISSION_ERROR"
        self.mock_audit_logger.log.assert_called_once()
        call_args = self.mock_audit_logger.log.call_args
        assert call_args.kwargs["details"]["status"] == "failed"
        assert call_args.kwargs["details"]["error_type"] == "permission_error"

    def test_register_os_error_logs_audit(self):
        """测试系统错误时记录审计日志"""
        self.mock_repo.save.side_effect = OSError("I/O error occurred")

        request = RegisterRequest(username="testuser", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False
        assert response.error_code == "SYSTEM_ERROR"
        self.mock_audit_logger.log.assert_called_once()
        call_args = self.mock_audit_logger.log.call_args
        assert call_args.kwargs["details"]["status"] == "failed"
        assert call_args.kwargs["details"]["error_type"] == "os_error"

    def test_register_disk_full_error(self):
        """测试磁盘空间不足错误"""
        error = OSError("No space left on device")
        error.errno = 28
        self.mock_repo.save.side_effect = error

        request = RegisterRequest(username="testuser", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False
        assert response.error_code == "DISK_FULL"
        assert "磁盘空间不足" in response.message

    def test_register_json_error_logs_audit(self):
        """测试JSON解析错误时记录审计日志"""
        self.mock_repo.save.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        request = RegisterRequest(username="testuser", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False
        assert response.error_code == "DATA_CORRUPTION"
        self.mock_audit_logger.log.assert_called_once()

    def test_register_unknown_error_logs_audit(self):
        """测试未知错误时记录审计日志"""
        self.mock_repo.save.side_effect = RuntimeError("Unknown error")

        request = RegisterRequest(username="testuser", folder_location="project")
        response = self.use_case.execute(request)

        assert response.success is False
        assert response.error_code == "UNKNOWN_ERROR"
        self.mock_audit_logger.log.assert_called_once()
        call_args = self.mock_audit_logger.log.call_args
        assert call_args.kwargs["details"]["error_type"] == "unknown_error"

    def test_register_without_audit_logger(self):
        """测试无审计日志时正常工作"""
        use_case = RegisterUseCase(self.mock_repo, audit_logger=None)

        request = RegisterRequest(username="testuser", folder_location="project")
        response = use_case.execute(request)

        assert response.success is True


class TestRegisterResponse:
    """注册响应测试"""

    def test_response_with_error_code(self):
        """测试带错误码的响应"""
        response = RegisterResponse(
            success=False, message="权限不足", error_code="PERMISSION_ERROR"
        )
        assert response.success is False
        assert response.error_code == "PERMISSION_ERROR"
        assert response.message == "权限不足"

    def test_response_success(self):
        """测试成功响应"""
        response = RegisterResponse(
            success=True, user_id="local_abc123", username="testuser", message="注册成功"
        )
        assert response.success is True
        assert response.user_id == "local_abc123"
        assert response.username == "testuser"
        assert response.error_code == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
