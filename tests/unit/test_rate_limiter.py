"""
限流功能单元测试
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


class TestRateLimitConfig:
    """测试限流配置"""

    def test_default_config(self):
        """测试默认配置"""
        from src.infrastructure.security.rate_limiter import RateLimitConfig

        config = RateLimitConfig()

        assert config.enabled is True
        assert config.default_limit == "60/minute"
        assert config.submit_limit == "10/minute"
        assert config.register_limit == "5/minute"
        assert config.activate_limit == "5/minute"
        assert config.storage_uri == "memory://"

    def test_custom_config(self):
        """测试自定义配置"""
        from src.infrastructure.security.rate_limiter import RateLimitConfig

        config = RateLimitConfig(
            enabled=False,
            default_limit="100/hour",
            submit_limit="20/minute",
        )

        assert config.enabled is False
        assert config.default_limit == "100/hour"
        assert config.submit_limit == "20/minute"


class TestRateLimiter:
    """测试限流器"""

    def test_create_rate_limiter(self):
        """测试创建限流器"""
        from src.infrastructure.security.rate_limiter import create_rate_limiter, RateLimiter

        limiter = create_rate_limiter()

        assert isinstance(limiter, RateLimiter)
        assert limiter.config.enabled is True

    def test_create_rate_limiter_disabled(self):
        """测试创建禁用的限流器"""
        from src.infrastructure.security.rate_limiter import create_rate_limiter

        limiter = create_rate_limiter(enabled=False)

        assert limiter.config.enabled is False

    def test_init_app_disabled(self):
        """测试禁用时初始化应用"""
        from src.infrastructure.security.rate_limiter import RateLimiter, RateLimitConfig

        config = RateLimitConfig(enabled=False)
        limiter = RateLimiter(config)
        app = FastAPI()

        limiter.init_app(app)

        assert limiter._limiter is None

    def test_get_client_ip_direct(self):
        """测试直接获取客户端 IP"""
        from src.infrastructure.security.rate_limiter import RateLimiter

        limiter = RateLimiter()
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        ip = limiter.get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_get_client_ip_forwarded(self):
        """测试通过 X-Forwarded-For 获取客户端 IP"""
        from src.infrastructure.security.rate_limiter import RateLimiter

        limiter = RateLimiter()
        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        ip = limiter.get_client_ip(request)

        assert ip == "10.0.0.1"

    def test_get_client_ip_real_ip(self):
        """测试通过 X-Real-IP 获取客户端 IP"""
        from src.infrastructure.security.rate_limiter import RateLimiter

        limiter = RateLimiter()
        request = MagicMock(spec=Request)
        request.headers = {"X-Real-IP": "10.0.0.2"}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        ip = limiter.get_client_ip(request)

        assert ip == "10.0.0.2"

    def test_get_client_ip_no_client(self):
        """测试无客户端信息时获取 IP"""
        from src.infrastructure.security.rate_limiter import RateLimiter

        limiter = RateLimiter()
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None

        ip = limiter.get_client_ip(request)

        assert ip == "unknown"

    def test_limit_decorator_without_limiter(self):
        """测试无限流器时的装饰器"""
        from src.infrastructure.security.rate_limiter import RateLimiter

        limiter = RateLimiter()
        limiter._limiter = None

        @limiter.limit("10/minute")
        async def test_func():
            return "success"

        assert test_func.__name__ == "test_func"


class TestSetupRateLimiting:
    """测试限流设置"""

    def test_setup_rate_limiting(self):
        """测试设置限流"""
        from src.infrastructure.security.rate_limiter import setup_rate_limiting

        app = FastAPI()
        limiter = setup_rate_limiting(app)

        assert limiter is not None
        if limiter.limiter is not None:
            assert hasattr(app.state, "limiter")

    def test_setup_rate_limiting_integration(self):
        """测试限流集成"""
        from src.infrastructure.security.rate_limiter import setup_rate_limiting

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        limiter = setup_rate_limiting(app)

        assert limiter is not None


class TestRateLimitMiddleware:
    """测试限流中间件"""

    @pytest.fixture
    def test_app(self):
        """创建测试应用"""
        from src.infrastructure.security.rate_limiter import setup_rate_limiting

        app = FastAPI()

        limiter = setup_rate_limiting(app)

        if limiter.limiter is None:
            pytest.skip("slowapi not available")

        @app.get("/test")
        @limiter.limiter.limit("5/minute")
        async def test_endpoint(request: Request):
            return {"status": "ok"}

        return app

    def test_rate_limit_allows_requests(self, test_app):
        """测试限流允许正常请求"""
        client = TestClient(test_app)

        for i in range(5):
            response = client.get("/test")
            assert response.status_code == 200

    def test_rate_limit_blocks_excess_requests(self, test_app):
        """测试限流阻止超额请求"""
        client = TestClient(test_app)

        for i in range(5):
            response = client.get("/test")
            assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429


class TestRateLimitEndpoints:
    """测试端点限流配置"""

    def test_submit_endpoint_limit(self):
        """测试 submit 端点限流配置"""
        from src.infrastructure.security.rate_limiter import RateLimitConfig

        config = RateLimitConfig()

        assert config.submit_limit == "10/minute"

    def test_register_endpoint_limit(self):
        """测试 register 端点限流配置"""
        from src.infrastructure.security.rate_limiter import RateLimitConfig

        config = RateLimitConfig()

        assert config.register_limit == "5/minute"

    def test_activate_endpoint_limit(self):
        """测试 activate 端点限流配置"""
        from src.infrastructure.security.rate_limiter import RateLimitConfig

        config = RateLimitConfig()

        assert config.activate_limit == "5/minute"


class TestRateLimitDisabled:
    """测试禁用限流"""

    def test_disabled_rate_limiter(self):
        """测试禁用限流器"""
        from src.infrastructure.security.rate_limiter import create_rate_limiter

        limiter = create_rate_limiter(enabled=False)
        app = FastAPI()

        limiter.init_app(app)

        assert limiter._limiter is None

    def test_disabled_rate_limit_decorator(self):
        """测试禁用限流时的装饰器"""
        from src.infrastructure.security.rate_limiter import RateLimiter, RateLimitConfig

        config = RateLimitConfig(enabled=False)
        limiter = RateLimiter(config)

        decorator = limiter.limit("10/minute")

        async def test_func():
            return "success"

        decorated = decorator(test_func)

        assert decorated.__name__ == "test_func"
