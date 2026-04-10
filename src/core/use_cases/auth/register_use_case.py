"""
用户注册用例

使用示例：
    from src.core.use_cases.auth import RegisterUseCase, RegisterRequest

    use_case = RegisterUseCase(user_repository, audit_logger)
    response = use_case.execute(RegisterRequest(
        username="test_user",
        folder_location="project"
    ))

    if response.success:
        print(f"注册成功: {response.user_id}")
"""

import json
from dataclasses import dataclass
from typing import Optional

from src.core.entities import UserFactory
from src.core.interfaces.repositories import IUserRepository
from src.infrastructure.audit import AuditAction, AuditLogger


@dataclass
class RegisterRequest:
    """用户注册请求"""

    username: str
    folder_location: str = "project"


@dataclass
class RegisterResponse:
    """用户注册响应"""

    success: bool
    user_id: str = ""
    username: str = ""
    message: str = ""
    error_code: str = ""


class RegisterUseCase:
    """用户注册用例"""

    def __init__(
        self,
        user_repository: IUserRepository,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """
        初始化用户注册用例

        Args:
            user_repository: 用户仓储
            audit_logger: 审计日志记录器（可选）
        """
        self._user_repository = user_repository
        self._audit_logger = audit_logger

    def execute(self, request: RegisterRequest) -> RegisterResponse:
        """
        执行用户注册

        Args:
            request: 用户注册请求

        Returns:
            用户注册响应
        """
        user = UserFactory.create(
            username=request.username, folder_location=request.folder_location
        )

        is_valid, message = user.validate()
        if not is_valid:
            return RegisterResponse(
                success=False, message=message, error_code="USERNAME_VALIDATION_ERROR"
            )

        available_username = self._user_repository.find_available_username(request.username)
        if available_username != request.username:
            user.username = available_username

        try:
            saved_user = self._user_repository.save(user)
            self._log_registration_success(saved_user.user_id, saved_user.username)
            return RegisterResponse(
                success=True,
                user_id=saved_user.user_id,
                username=saved_user.username,
                message="注册成功",
            )
        except PermissionError as e:
            return self._handle_permission_error(e, user.username)
        except OSError as e:
            return self._handle_os_error(e, user.username)
        except json.JSONDecodeError as e:
            return self._handle_json_error(e, user.username)
        except Exception as e:
            return self._handle_unknown_error(e, user.username)

    def _handle_permission_error(self, error: PermissionError, username: str) -> RegisterResponse:
        """处理权限错误"""
        message = "无法创建用户数据文件，请检查文件夹权限或尝试以管理员身份运行程序"
        self._log_registration_failure("permission_error", username, str(error))
        return RegisterResponse(success=False, message=message, error_code="PERMISSION_ERROR")

    def _handle_os_error(self, error: OSError, username: str) -> RegisterResponse:
        """处理操作系统错误"""
        if "No space left" in str(error) or error.errno == 28:
            message = "磁盘空间不足，无法创建用户数据，请清理磁盘空间后重试"
            error_code = "DISK_FULL"
        else:
            message = "保存用户数据时发生系统错误，请稍后重试"
            error_code = "SYSTEM_ERROR"
        self._log_registration_failure("os_error", username, str(error))
        return RegisterResponse(success=False, message=message, error_code=error_code)

    def _handle_json_error(self, error: json.JSONDecodeError, username: str) -> RegisterResponse:
        """处理JSON解析错误"""
        message = "用户数据格式错误，可能存在数据损坏"
        self._log_registration_failure("data_corruption", username, str(error))
        return RegisterResponse(success=False, message=message, error_code="DATA_CORRUPTION")

    def _handle_unknown_error(self, error: Exception, username: str) -> RegisterResponse:
        """处理未知错误"""
        message = "注册过程中发生未知错误，请稍后重试"
        self._log_registration_failure("unknown_error", username, str(error))
        return RegisterResponse(success=False, message=message, error_code="UNKNOWN_ERROR")

    def _log_registration_success(self, user_id: str, username: str) -> None:
        """记录注册成功审计日志"""
        if self._audit_logger:
            self._audit_logger.log(
                action=AuditAction.USER_REGISTER,
                user_id=user_id,
                resource_type="user",
                resource_id=user_id,
                details={"username": username, "status": "success"},
            )

    def _log_registration_failure(self, error_type: str, username: str, error_message: str) -> None:
        """记录注册失败审计日志"""
        if self._audit_logger:
            self._audit_logger.log(
                action=AuditAction.USER_REGISTER,
                user_id="unknown",
                resource_type="user",
                resource_id="unknown",
                details={
                    "username": username,
                    "status": "failed",
                    "error_type": error_type,
                    "error_message": error_message[:200],
                },
            )


__all__ = ["RegisterUseCase", "RegisterRequest", "RegisterResponse"]
