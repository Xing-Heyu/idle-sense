"""
登出用例

处理用户登出逻辑，清理会话状态
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ...interfaces.repositories.user_repository import IUserRepository


@dataclass
class LogoutRequest:
    """登出请求DTO"""
    user_id: str
    session_id: Optional[str] = None  # 可选的会话ID


@dataclass
class LogoutResponse:
    """登出响应DTO"""
    success: bool
    message: str = ""
    logout_time: Optional[datetime] = None


class LogoutUseCase:
    """
    登出用例

    处理用户登出流程：
    1. 验证用户存在
    2. 更新最后登出时间（可选）
    3. 清理会话状态（由调用方处理）
    4. 记录审计日志（可选）
    """

    def __init__(self, user_repository: IUserRepository):
        self._user_repository = user_repository

    def execute(self, request: LogoutRequest) -> LogoutResponse:
        """
        执行登出逻辑

        Args:
            request: 登出请求

        Returns:
            LogoutResponse: 登出响应
        """
        # 验证用户存在
        user = self._user_repository.get_by_id(request.user_id)

        if not user:
            return LogoutResponse(
                success=False,
                message=f"用户ID '{request.user_id}' 不存在"
            )

        # 更新用户登出时间（可选的审计功能）
        # 注意：这里可以扩展为记录登出历史
        logout_time = datetime.now()

        # 在实际应用中，这里可能还需要：
        # - 使会话令牌失效
        # - 清理缓存中的用户状态
        # - 记录审计日志
        # - 通知其他服务用户已登出

        return LogoutResponse(
            success=True,
            message=f"用户 '{user.username}' 登出成功",
            logout_time=logout_time
        )
