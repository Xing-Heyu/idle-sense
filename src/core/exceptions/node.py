"""
节点相关异常类模块
"""

from typing import Any, Optional

from src.core.exceptions.base import IdleSenseError


class NodeError(IdleSenseError):
    """
    节点相关错误基类
    """

    def __init__(
        self,
        message: str,
        code: str = "NODE_ERROR",
        node_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if node_id:
            details["node_id"] = node_id
        super().__init__(message, code, details)


class NodeNotFoundError(NodeError):
    """
    节点不存在错误
    """

    def __init__(
        self,
        node_id: str,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        message = message or f"节点不存在: {node_id}"
        super().__init__(message, "NODE_NOT_FOUND", node_id, details)


class NodeOfflineError(NodeError):
    """
    节点离线错误
    """

    def __init__(
        self,
        node_id: str,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        message = message or f"节点已离线: {node_id}"
        super().__init__(message, "NODE_OFFLINE", node_id, details)


__all__ = ["NodeError", "NodeNotFoundError", "NodeOfflineError"]
