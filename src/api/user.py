"""
用户 API

提供用户相关的统一接口
"""

from typing import Any, Optional

from src.core.use_cases.auth.login_use_case import LoginUseCase
from src.core.use_cases.auth.logout_use_case import LogoutUseCase
from src.core.use_cases.auth.register_use_case import RegisterUseCase
from src.infrastructure.repositories.user_repository import FileUserRepository


class UserAPI:
    """
    用户 API

    提供用户操作的统一接口
    """

    def __init__(
        self,
        user_repository: Optional[FileUserRepository] = None,
        users_dir: str = "local_users",
    ):
        self._user_repository = user_repository or FileUserRepository(users_dir=users_dir)

    def register(
        self,
        username: str,
        folder_location: str = "project",
    ) -> dict[str, Any]:
        """注册用户"""
        use_case = RegisterUseCase(self._user_repository)
        return use_case.execute(username, folder_location)

    def login(self, user_id: str) -> dict[str, Any]:
        """用户登录"""
        use_case = LoginUseCase(self._user_repository)
        return use_case.execute(user_id)

    def logout(self, user_id: str) -> bool:
        """用户登出"""
        use_case = LogoutUseCase(self._user_repository)
        return use_case.execute(user_id)

    def get_user(self, user_id: str) -> Optional[dict[str, Any]]:
        """获取用户信息"""
        user = self._user_repository.find_by_id(user_id)
        return user.to_dict() if user else None

    def list_users(self) -> list[dict[str, Any]]:
        """获取所有用户列表"""
        users = self._user_repository.find_all()
        return [user.to_dict() for user in users]


__all__ = ["UserAPI"]
