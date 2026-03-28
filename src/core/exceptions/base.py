"""
基础异常类模块

提供 Idle-Sense 项目的基础异常类
"""

from typing import Any, Optional


class IdleSenseError(Exception):
    """
    Idle-Sense 基础异常类

    所有 Idle-Sense 项目异常的基类

    Attributes:
        message: 错误消息
        code: 错误代码
        details: 额外详情字典
    """

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} - {self.details}"
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, code={self.code!r})"


__all__ = ["IdleSenseError"]
