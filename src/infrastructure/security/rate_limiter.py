"""
API 请求限流模块

提供基于 IP 地址的请求限流功能，防止 DoS 攻击
"""

import logging
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Optional

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """限流配置"""
    enabled: bool = True
    default_limit: str = "60/minute"
    storage_uri: str = "memory://"

    submit_limit: str = "10/minute"
    register_limit: str = "5/minute"
    activate_limit: str = "5/minute"

    retry_after_seconds: int = 60
    trusted_proxies: list[str] = None


class RateLimiter:
    """API 请求限流器"""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._limiter = None
        self._app: Optional[FastAPI] = None

    def init_app(self, app: FastAPI) -> None:
        """初始化限流器并绑定到 FastAPI 应用"""
        if not self.config.enabled:
            return

        try:
            from slowapi import Limiter
            from slowapi.errors import RateLimitExceeded
            from slowapi.util import get_remote_address

            self._limiter = Limiter(
                key_func=get_remote_address,
                default_limits=[self.config.default_limit],
                enabled=self.config.enabled,
            )

            app.state.limiter = self._limiter

            @app.exception_handler(RateLimitExceeded)
            async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
                from slowapi import _rate_limit_exceeded_handler
                response = _rate_limit_exceeded_handler(request, exc)
                return response

            self._app = app

        except ImportError:
            logger.warning("slowapi 未安装，API 限流功能不可用。请运行: pip install slowapi")
        except Exception as e:
            logger.warning("限流器初始化失败: %s，API 限流功能不可用", e)

    @property
    def limiter(self):
        """获取底层 limiter 实例"""
        return self._limiter

    def limit(self, limit_value: str) -> Callable:
        """
        限流装饰器

        Args:
            limit_value: 限流规则，如 "10/minute", "5/hour"

        Returns:
            装饰器函数
        """
        if not self._limiter:
            def decorator(func: Callable) -> Callable:
                @wraps(func)
                async def wrapper(*args, **kwargs):
                    return await func(*args, **kwargs)
                return wrapper
            return decorator

        return self._limiter.limit(limit_value)

    def get_client_ip(self, request: Request) -> str:
        """获取客户端 IP 地址（仅信任已配置的代理）"""
        if self.config.trusted_proxies:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip

        return request.client.host if request.client else "unknown"

    def check_rate_limit(self, request: Request, limit: str) -> Optional[dict]:
        """
        检查是否超过限流

        Returns:
            None 如果未超限，否则返回错误信息字典
        """
        if not self._limiter:
            return None

        client_ip = self.get_client_ip(request)

        try:
            from slowapi.errors import RateLimitExceeded

            self._limiter.test(request, limit)

        except RateLimitExceeded:
            return {
                "error": "Rate limit exceeded",
                "limit": limit,
                "retry_after": self.config.retry_after_seconds,
                "client_ip": client_ip,
            }

        return None


def create_rate_limiter(
    enabled: bool = True,
    default_limit: str = "60/minute",
    submit_limit: str = "10/minute",
    register_limit: str = "5/minute",
    activate_limit: str = "5/minute",
) -> RateLimiter:
    """
    创建限流器实例

    Args:
        enabled: 是否启用限流
        default_limit: 默认限流规则
        submit_limit: /submit 端点限流规则
        register_limit: /api/nodes/register 端点限流规则
        activate_limit: /api/nodes/activate-local 端点限流规则

    Returns:
        RateLimiter 实例
    """
    config = RateLimitConfig(
        enabled=enabled,
        default_limit=default_limit,
        submit_limit=submit_limit,
        register_limit=register_limit,
        activate_limit=activate_limit,
    )
    return RateLimiter(config)


def setup_rate_limiting(app: FastAPI) -> RateLimiter:
    """
    为 FastAPI 应用设置限流

    Args:
        app: FastAPI 应用实例

    Returns:
        配置好的 RateLimiter 实例
    """
    limiter = create_rate_limiter()
    limiter.init_app(app)
    return limiter


__all__ = [
    "RateLimitConfig",
    "RateLimiter",
    "create_rate_limiter",
    "setup_rate_limiting",
]
