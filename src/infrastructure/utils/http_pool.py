"""
HTTP 连接池管理器

提供 HTTP 连接复用功能，提高网络请求性能
"""

import threading
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HTTPConnectionPool:
    """
    HTTP 连接池管理器（单例模式）

    提供 HTTP 连接复用，减少连接开销

    Attributes:
        session: requests.Session 实例
        config: 连接池配置
    """

    _instance: Optional["HTTPConnectionPool"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        max_connections: int = 10,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        timeout: int = 30,
        pool_connections: int = 10,
        pool_maxsize: int = 20,
    ):
        if self._initialized:
            return

        self._initialized = True
        self.config = {
            "max_connections": max_connections,
            "max_retries": max_retries,
            "backoff_factor": backoff_factor,
            "timeout": timeout,
            "pool_connections": pool_connections,
            "pool_maxsize": pool_maxsize,
        }
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建配置好的 Session"""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.config["max_retries"],
            backoff_factor=self.config["backoff_factor"],
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"],
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.config["pool_connections"],
            pool_maxsize=self.config["pool_maxsize"],
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get_session(self) -> requests.Session:
        """获取 Session 实例"""
        return self.session

    def request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """发送 HTTP 请求"""
        kwargs.setdefault("timeout", self.config["timeout"])
        return self.session.request(method, url, **kwargs)

    def get(self, url: str, **kwargs) -> requests.Response:
        """发送 GET 请求"""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """发送 POST 请求"""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> requests.Response:
        """发送 PUT 请求"""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> requests.Response:
        """发送 DELETE 请求"""
        return self.request("DELETE", url, **kwargs)

    def close(self) -> None:
        """关闭连接池"""
        self.session.close()

    @classmethod
    def reset(cls) -> None:
        """重置单例实例"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None


def get_connection_pool(**kwargs) -> HTTPConnectionPool:
    """获取连接池实例"""
    return HTTPConnectionPool(**kwargs)


__all__ = ["HTTPConnectionPool", "get_connection_pool"]
