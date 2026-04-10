"""
登录用例

使用示例：
    from src.core.use_cases.auth import LoginUseCase, LoginRequest

    use_case = LoginUseCase(user_repository)
    response = use_case.execute(LoginRequest(username="test_user"))

    if response.success:
        print(f"登录成功: {response.user.username}")
    else:
        print(f"登录失败: {response.message}")
"""

from dataclasses import dataclass

from src.core.interfaces.repositories import IUserRepository


@dataclass
class LoginRequest:
    """登录请求"""

    username_or_id: str


@dataclass
class LoginResponse:
    """登录响应"""

    success: bool
    user_id: str = ""
    username: str = ""
    message: str = ""


class LoginUseCase:
    """登录用例"""

    def __init__(self, user_repository: IUserRepository):
        """
        初始化登录用例

        Args:
            user_repository: 用户仓储
        """
        self._user_repository = user_repository

    def execute(self, request: LoginRequest) -> LoginResponse:
        """
        执行登录

        Args:
            request: 登录请求

        Returns:
            登录响应
        """
        user = self._user_repository.get_by_username(request.username_or_id)

        if not user:
            user = self._user_repository.get_by_id(request.username_or_id)

        if not user:
            return LoginResponse(success=False, message=f"用户 '{request.username_or_id}' 不存在")

        user.update_last_login()
        self._user_repository.update(user)

        return LoginResponse(
            success=True, user_id=user.user_id, username=user.username, message="登录成功"
        )


__all__ = ["LoginUseCase", "LoginRequest", "LoginResponse"]
