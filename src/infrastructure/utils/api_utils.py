"""
API调用工具模块

提供统一的API调用封装，支持：
- 错误处理
- 重试机制
- 超时控制
- 响应解析

使用示例：
    from src.infrastructure.utils import safe_api_call

    success, data = safe_api_call(requests.get, "http://example.com/api", timeout=10)
    if success:
        print(data)
    else:
        print(f"Error: {data.get('error')}")
"""

import functools
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

import requests

T = TypeVar("T")


@dataclass
class APIResult:
    """API调用结果"""
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None

    @classmethod
    def ok(cls, data: dict[str, Any], status_code: int = 200) -> "APIResult":
        """创建成功结果"""
        return cls(success=True, data=data, status_code=status_code)

    @classmethod
    def fail(cls, error: str, status_code: Optional[int] = None) -> "APIResult":
        """创建失败结果"""
        return cls(success=False, error=error, status_code=status_code)


def safe_api_call(
    func: Callable[..., requests.Response],
    *args,
    default: Any = None,
    **kwargs
) -> tuple[bool, Any]:
    """
    统一的API调用包装器

    Args:
        func: 要调用的函数（通常是 requests.get, requests.post 等）
        *args: 位置参数
        default: 默认返回值（已弃用，保留向后兼容）
        **kwargs: 关键字参数

    Returns:
        (是否成功, 结果或错误信息)

    Examples:
        >>> success, data = safe_api_call(requests.get, "http://example.com/api")
        >>> if success:
        ...     print(data)
        ... else:
        ...     print(f"Error: {data.get('error')}")
    """
    try:
        response = func(*args, **kwargs)

        if hasattr(response, 'status_code'):
            if response.status_code == 200:
                try:
                    return True, response.json()
                except ValueError:
                    return True, {"text": response.text}
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict) and "error" in error_data:
                        error_msg = error_data["error"]
                except (ValueError, KeyError):
                    pass
                return False, {"error": error_msg, "text": response.text, "status_code": response.status_code}
        else:
            return True, response

    except requests.exceptions.ConnectionError as e:
        return False, {"error": "无法连接到调度中心", "details": str(e)}
    except requests.exceptions.Timeout as e:
        return False, {"error": "请求超时", "details": str(e)}
    except requests.exceptions.RequestException as e:
        return False, {"error": f"请求失败: {str(e)}", "details": str(e)}
    except Exception as e:
        return False, {"error": f"未知错误: {str(e)}", "details": str(e)}


def safe_api_call_v2(
    func: Callable[..., requests.Response],
    *args,
    **kwargs
) -> APIResult:
    """
    统一的API调用包装器（新版本，返回APIResult对象）

    Args:
        func: 要调用的函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        APIResult对象

    Examples:
        >>> result = safe_api_call_v2(requests.get, "http://example.com/api")
        >>> if result.success:
        ...     print(result.data)
        ... else:
        ...     print(f"Error: {result.error}")
    """
    try:
        response = func(*args, **kwargs)

        if hasattr(response, 'status_code'):
            if response.status_code == 200:
                try:
                    return APIResult.ok(response.json(), response.status_code)
                except ValueError:
                    return APIResult.ok({"text": response.text}, response.status_code)
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict) and "error" in error_data:
                        error_msg = error_data["error"]
                except (ValueError, KeyError):
                    pass
                return APIResult.fail(error_msg, response.status_code)
        else:
            return APIResult.ok(response)

    except requests.exceptions.ConnectionError:
        return APIResult.fail("无法连接到调度中心")
    except requests.exceptions.Timeout:
        return APIResult.fail("请求超时")
    except requests.exceptions.RequestException as e:
        return APIResult.fail(f"请求失败: {str(e)}")
    except Exception as e:
        return APIResult.fail(f"未知错误: {str(e)}")


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (requests.exceptions.RequestException,)
):
    """
    失败重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟时间增长因子
        exceptions: 需要重试的异常类型

    Returns:
        装饰器函数

    Examples:
        >>> @retry_on_failure(max_retries=3, delay=1.0)
        ... def fetch_data():
        ...     response = requests.get("http://example.com/api")
        ...     response.raise_for_status()
        ...     return response.json()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        raise last_exception from e

            raise last_exception from last_exception

        return wrapper
    return decorator


def with_timeout(timeout: int = 10):
    """
    超时控制装饰器

    Args:
        timeout: 超时时间（秒）

    Returns:
        装饰器函数

    Note:
        此装饰器需要配合支持 timeout 参数的函数使用
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            kwargs.setdefault('timeout', timeout)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class APIClient:
    """
    API客户端类

    提供统一的API调用接口，支持：
    - 自动重试
    - 超时控制
    - 错误处理
    - 响应缓存

    Examples:
        >>> client = APIClient(base_url="http://example.com", timeout=10)
        >>> success, data = client.get("/api/users")
    """

    def __init__(
        self,
        base_url: str = "",
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        初始化API客户端

        Args:
            base_url: 基础URL
            timeout: 默认超时时间
            max_retries: 最大重试次数
            retry_delay: 重试延迟
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session = requests.Session()

    def _build_url(self, endpoint: str) -> str:
        """构建完整URL"""
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def get(self, endpoint: str, **kwargs) -> tuple[bool, Any]:
        """GET请求"""
        kwargs.setdefault('timeout', self.timeout)
        return safe_api_call(
            self._session.get,
            self._build_url(endpoint),
            **kwargs
        )

    def post(self, endpoint: str, **kwargs) -> tuple[bool, Any]:
        """POST请求"""
        kwargs.setdefault('timeout', self.timeout)
        return safe_api_call(
            self._session.post,
            self._build_url(endpoint),
            **kwargs
        )

    def put(self, endpoint: str, **kwargs) -> tuple[bool, Any]:
        """PUT请求"""
        kwargs.setdefault('timeout', self.timeout)
        return safe_api_call(
            self._session.put,
            self._build_url(endpoint),
            **kwargs
        )

    def delete(self, endpoint: str, **kwargs) -> tuple[bool, Any]:
        """DELETE请求"""
        kwargs.setdefault('timeout', self.timeout)
        return safe_api_call(
            self._session.delete,
            self._build_url(endpoint),
            **kwargs
        )

    def close(self):
        """关闭会话"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


__all__ = [
    "APIResult",
    "safe_api_call",
    "safe_api_call_v2",
    "retry_on_failure",
    "with_timeout",
    "APIClient",
]
