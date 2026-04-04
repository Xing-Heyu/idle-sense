"""
Streamlit 安全配置模块

提供安全头配置和 XSS 防护功能
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SecurityHeaders:
    """安全头配置"""

    content_security_policy: str = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none';"
    )
    x_content_type_options: str = "nosniff"
    x_frame_options: str = "DENY"
    x_xss_protection: str = "1; mode=block"
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: str = (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    )
    strict_transport_security: Optional[str] = "max-age=31536000; includeSubDomains"

    def to_dict(self) -> dict[str, str]:
        """转换为字典格式"""
        headers = {
            "Content-Security-Policy": self.content_security_policy,
            "X-Content-Type-Options": self.x_content_type_options,
            "X-Frame-Options": self.x_frame_options,
            "X-XSS-Protection": self.x_xss_protection,
            "Referrer-Policy": self.referrer_policy,
            "Permissions-Policy": self.permissions_policy,
        }

        if self.strict_transport_security:
            headers["Strict-Transport-Security"] = self.strict_transport_security

        return headers


@dataclass
class SecurityConfig:
    """安全配置"""

    enabled: bool = True
    headers: SecurityHeaders = None
    enable_cors_protection: bool = True
    enable_csrf_protection: bool = True
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "Lax"

    def __post_init__(self):
        if self.headers is None:
            self.headers = SecurityHeaders()

    @classmethod
    def from_env(cls) -> "SecurityConfig":
        """从环境变量创建配置"""
        return cls(
            enabled=os.getenv("IDLE_SECURITY_ENABLED", "true").lower() == "true",
            enable_cors_protection=os.getenv("IDLE_CORS_PROTECTION", "true").lower() == "true",
            enable_csrf_protection=os.getenv("IDLE_CSRF_PROTECTION", "true").lower() == "true",
            session_cookie_secure=os.getenv("IDLE_SESSION_COOKIE_SECURE", "true").lower() == "true",
        )


def get_security_headers() -> dict[str, str]:
    """获取安全头字典"""
    config = SecurityConfig.from_env()
    if not config.enabled:
        return {}
    return config.headers.to_dict()


def apply_security_headers(response_headers: dict) -> dict:
    """应用安全头到响应"""
    security_headers = get_security_headers()
    response_headers.update(security_headers)
    return response_headers


def get_streamlit_config() -> dict:
    """获取 Streamlit 安全配置"""
    return {
        "server": {
            "enableCORS": False,
            "enableXsrfProtection": True,
            "headless": True,
        },
        "browser": {
            "gatherUsageStats": False,
            "serverAddress": "localhost",
            "serverPort": 8501,
        },
        "client": {
            "showErrorDetails": False,
        },
    }


def generate_csp_nonce() -> str:
    """生成 CSP nonce 值"""
    import secrets
    return secrets.token_hex(16)


def sanitize_input(text: str) -> str:
    """清理用户输入，防止 XSS"""
    if not text:
        return ""

    import html
    return html.escape(text)


def validate_redirect_url(url: str, allowed_hosts: Optional[list[str]] = None) -> bool:
    """验证重定向 URL 是否安全"""
    if not url:
        return False

    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)

        if parsed.scheme not in ["http", "https"]:
            return False

        if allowed_hosts and parsed.netloc not in allowed_hosts:
            return False

        return True
    except Exception:
        return False


SECURITY_HTML = """
<script>
// 安全头配置 (通过 JavaScript 设置)
document.addEventListener('DOMContentLoaded', function() {
    // 设置 meta 标签形式的安全头
    const securityMeta = [
        { name: 'X-Content-Type-Options', content: 'nosniff' },
        { name: 'X-Frame-Options', content: 'DENY' },
        { name: 'X-XSS-Protection', content: '1; mode=block' },
        { name: 'Referrer-Policy', content: 'strict-origin-when-cross-origin' }
    ];

    securityMeta.forEach(meta => {
        const element = document.createElement('meta');
        element.httpEquiv = meta.name;
        element.content = meta.content;
        document.head.appendChild(element);
    });
});
</script>
"""


def get_security_html() -> str:
    """获取安全相关的 HTML 代码"""
    return SECURITY_HTML


__all__ = [
    "SecurityHeaders",
    "SecurityConfig",
    "get_security_headers",
    "apply_security_headers",
    "get_streamlit_config",
    "generate_csp_nonce",
    "sanitize_input",
    "validate_redirect_url",
    "get_security_html",
]
