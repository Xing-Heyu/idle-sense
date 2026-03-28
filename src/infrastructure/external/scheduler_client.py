"""
调度器API客户端模块

提供与调度中心通信的完整API封装，支持：
- 健康检查
- 任务提交和监控
- 节点管理
- 分布式任务处理
- 系统统计

使用示例：
    from src.infrastructure.external import SchedulerClient

    client = SchedulerClient("http://localhost:8000")

    # 检查健康状态
    health_ok, health_info = client.check_health()

    # 提交任务
    success, task_info = client.submit_task(code="print('hello')", timeout=300)
"""

import threading
from dataclasses import dataclass
from typing import Any, Optional

import requests

from ..utils.api_utils import safe_api_call


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    is_online: bool
    is_idle: bool
    status: str
    status_detail: str
    platform: str
    capacity: dict[str, Any]
    tags: dict[str, str]
    owner: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeInfo":
        """从字典创建"""
        status = data.get("status", "")
        is_online = status.lower() == "online_available"
        is_idle = data.get("is_idle", False)

        return cls(
            node_id=data.get("node_id", "unknown"),
            is_online=is_online,
            is_idle=is_idle,
            status="在线" if is_online else "离线",
            status_detail="空闲" if is_idle else "忙碌" if is_online else "离线",
            platform=data.get("platform", "unknown"),
            capacity=data.get("capacity", {}),
            tags=data.get("tags", {}),
            owner=data.get("tags", {}).get("user_id", "未知")
        )


@dataclass
class HealthInfo:
    """健康检查信息"""
    status: str
    online_nodes: int
    total_nodes: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthInfo":
        """从字典创建"""
        nodes_info = data.get("nodes", {})
        return cls(
            status=data.get("status", "unknown"),
            online_nodes=nodes_info.get("online", 0),
            total_nodes=nodes_info.get("total", 0)
        )


class SchedulerClient:
    """
    调度器API客户端

    提供与调度中心通信的完整API封装

    Examples:
        >>> client = SchedulerClient("http://localhost:8000")
        >>> health_ok, health_info = client.check_health()
        >>> if health_ok:
        ...     print(f"Online nodes: {health_info.online_nodes}")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: int = 10,
        health_check_timeout: int = 3,
        max_retries: int = 3
    ):
        """
        初始化调度器客户端

        Args:
            base_url: 调度器基础URL
            timeout: 默认API超时时间
            health_check_timeout: 健康检查超时时间
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.health_check_timeout = health_check_timeout
        self.max_retries = max_retries
        self._session = requests.Session()

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> tuple[bool, Any]:
        """
        发送HTTP请求

        Args:
            method: HTTP方法
            endpoint: API端点
            **kwargs: 请求参数

        Returns:
            (是否成功, 结果或错误信息)
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        if method.upper() == "GET":
            return safe_api_call(self._session.get, url, **kwargs)
        elif method.upper() == "POST":
            return safe_api_call(self._session.post, url, **kwargs)
        elif method.upper() == "PUT":
            return safe_api_call(self._session.put, url, **kwargs)
        elif method.upper() == "DELETE":
            return safe_api_call(self._session.delete, url, **kwargs)
        else:
            return False, {"error": f"不支持的HTTP方法: {method}"}

    def check_health(self) -> tuple[bool, dict[str, Any]]:
        """
        检查调度中心健康状态

        Returns:
            (是否在线, 健康信息)
        """
        success, health_data = self._request(
            "GET", "/health", timeout=self.health_check_timeout
        )

        if not success:
            success, root_data = self._request(
                "GET", "/", timeout=self.health_check_timeout
            )
            if success:
                return True, {"status": "online", "nodes": {"online": 0, "total": 0}}
            return False, health_data

        success, nodes_data = self._request(
            "GET", "/api/nodes", params={"online_only": False}, timeout=self.health_check_timeout + 1
        )

        if success:
            all_nodes = nodes_data.get("nodes", [])
            online_nodes = 0

            for node in all_nodes:
                is_online = self._is_node_online(node)
                if is_online:
                    online_nodes += 1

            if "nodes" not in health_data:
                health_data["nodes"] = {}
            health_data["nodes"]["online"] = online_nodes
            health_data["nodes"]["total"] = len(all_nodes)
        else:
            if "nodes" not in health_data:
                health_data["nodes"] = {}
            health_data["nodes"]["online"] = 0
            health_data["nodes"]["total"] = 0

        return True, health_data

    def _is_node_online(self, node: dict[str, Any]) -> bool:
        """判断节点是否在线"""
        if "is_online" in node:
            val = node["is_online"]
            if isinstance(val, bool):
                return val
            elif isinstance(val, str):
                return val.lower() in ["true", "yes", "1", "online"]
        elif "status" in node:
            status = node["status"]
            if isinstance(status, str):
                return status.lower() == "online_available"
        return False

    def get_all_nodes(self) -> tuple[bool, dict[str, Any]]:
        """
        获取所有节点信息

        Returns:
            (是否成功, 节点信息)
        """
        success, data = self._request(
            "GET", "/api/nodes", params={"online_only": False}, timeout=5
        )

        if not success:
            return success, data

        nodes = data.get("nodes", [])
        processed_nodes = []
        online_count = 0
        idle_count = 0

        for node in nodes:
            node_info = NodeInfo.from_dict(node)
            processed_nodes.append({
                "node_id": node_info.node_id,
                "is_online": node_info.is_online,
                "is_idle": node_info.is_idle,
                "status": node_info.status,
                "status_detail": node_info.status_detail,
                "platform": node_info.platform,
                "capacity": node_info.capacity,
                "tags": node_info.tags,
                "owner": node_info.owner
            })

            if node_info.is_online:
                online_count += 1
                if node_info.is_idle:
                    idle_count += 1

        return True, {
            "nodes": processed_nodes,
            "total_nodes": len(processed_nodes),
            "online_nodes": online_count,
            "idle_nodes": idle_count,
            "busy_nodes": online_count - idle_count
        }

    def submit_task(
        self,
        code: str,
        timeout: int = 300,
        cpu: float = 1.0,
        memory: int = 512,
        user_id: Optional[str] = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        提交任务到调度中心

        Args:
            code: 任务代码
            timeout: 超时时间（秒）
            cpu: CPU需求（核心数）
            memory: 内存需求（MB）
            user_id: 用户ID

        Returns:
            (是否成功, 任务信息)
        """
        payload = {
            "code": code,
            "timeout": timeout,
            "resources": {"cpu": cpu, "memory": memory},
            "user_id": user_id
        }
        return self._request("POST", "/submit", json=payload, timeout=10)

    def get_task_status(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            (是否成功, 任务状态)
        """
        return self._request("GET", f"/status/{task_id}", timeout=5)

    def delete_task(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        删除任务

        Args:
            task_id: 任务ID

        Returns:
            (是否成功, 删除结果)
        """
        return self._request("DELETE", f"/api/tasks/{task_id}", timeout=5)

    def get_all_results(self) -> tuple[bool, dict[str, Any]]:
        """
        获取所有任务结果

        Returns:
            (是否成功, 任务结果)
        """
        return self._request("GET", "/results", timeout=5)

    def get_system_stats(self) -> tuple[bool, dict[str, Any]]:
        """
        获取系统统计信息

        Returns:
            (是否成功, 统计信息)
        """
        success, data = self._request("GET", "/stats", timeout=5)

        if not success:
            return False, data

        tasks_info = data.get("tasks", {})
        nodes_info = data.get("nodes", {})

        return True, {
            "tasks": {
                "total": tasks_info.get("total", 0),
                "completed": tasks_info.get("completed", 0),
                "failed": tasks_info.get("failed", 0),
                "avg_time": tasks_info.get("avg_completion_time", 0)
            },
            "nodes": {
                "idle": nodes_info.get("idle", 0),
                "busy": nodes_info.get("online", 0) - nodes_info.get("idle", 0),
                "offline": nodes_info.get("offline", 0),
                "total": nodes_info.get("total", 0)
            },
            "throughput": {
                "compute_hours": tasks_info.get("total", 0) * tasks_info.get("avg_completion_time", 0) / 3600
            },
            "scheduler": data.get("scheduler", {})
        }

    def stop_node(self, node_id: str) -> tuple[bool, dict[str, Any]]:
        """
        停止指定节点

        Args:
            node_id: 节点ID

        Returns:
            (是否成功, 停止结果)
        """
        return self._request("POST", f"/api/nodes/{node_id}/stop", timeout=5)

    def activate_local_node(
        self,
        cpu_limit: float,
        memory_limit: int,
        storage_limit: int,
        user_id: Optional[str] = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        激活本地节点

        Args:
            cpu_limit: CPU限制
            memory_limit: 内存限制（MB）
            storage_limit: 存储限制（MB）
            user_id: 用户ID

        Returns:
            (是否成功, 节点信息)
        """
        return self._request(
            "POST",
            "/api/nodes/activate-local",
            json={
                "cpu_limit": cpu_limit,
                "memory_limit": memory_limit,
                "storage_limit": storage_limit,
                "user_id": user_id
            },
            timeout=10
        )

    def close(self):
        """关闭会话"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class DistributedTaskClient:
    """
    分布式任务客户端

    处理分布式任务的提交、监控和结果获取

    Examples:
        >>> client = DistributedTaskClient(distributed_task_manager)
        >>> success, result = client.submit_task(...)
    """

    def __init__(self, distributed_task_manager=None):
        """
        初始化分布式任务客户端

        Args:
            distributed_task_manager: 分布式任务管理器实例
        """
        self.manager = distributed_task_manager
        self._available = distributed_task_manager is not None

    @property
    def is_available(self) -> bool:
        """检查分布式任务模块是否可用"""
        return self._available

    def submit_task(
        self,
        name: str,
        description: str,
        code_template: str,
        data: Any,
        chunk_size: int = 10,
        max_parallel_chunks: int = 5,
        merge_code: Optional[str] = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        提交分布式任务

        Args:
            name: 任务名称
            description: 任务描述
            code_template: 代码模板
            data: 任务数据
            chunk_size: 分片大小
            max_parallel_chunks: 最大并行分片数
            merge_code: 合并代码

        Returns:
            (是否成功, 任务信息)
        """
        if not self._available:
            return False, {"error": "分布式任务处理模块不可用"}

        try:
            task_id = self.manager.submit_distributed_task(
                name=name,
                description=description,
                code_template=code_template,
                data=data,
                chunk_size=chunk_size,
                max_parallel_chunks=max_parallel_chunks,
                merge_code=merge_code
            )

            if self.manager.create_task_chunks(task_id):
                def execute_task():
                    self.manager.execute_distributed_task(task_id)

                thread = threading.Thread(target=execute_task, daemon=True)
                thread.start()

                return True, {"task_id": task_id, "message": "分布式任务已提交"}
            else:
                return False, {"error": "创建任务分片失败"}

        except Exception as e:
            return False, {"error": str(e)}

    def get_status(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        获取分布式任务状态

        Args:
            task_id: 任务ID

        Returns:
            (是否成功, 任务状态)
        """
        if not self._available:
            return False, {"error": "分布式任务处理模块不可用"}

        try:
            status = self.manager.get_task_status(task_id)
            if status:
                return True, status
            else:
                return False, {"error": "任务不存在"}
        except Exception as e:
            return False, {"error": str(e)}

    def get_result(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        获取分布式任务结果

        Args:
            task_id: 任务ID

        Returns:
            (是否成功, 任务结果)
        """
        if not self._available:
            return False, {"error": "分布式任务处理模块不可用"}

        try:
            result = self.manager.get_task_result(task_id)
            if result is not None:
                return True, {"result": result}
            else:
                return False, {"error": "任务未完成或结果不可用"}
        except Exception as e:
            return False, {"error": str(e)}


__all__ = [
    "SchedulerClient",
    "DistributedTaskClient",
    "NodeInfo",
    "HealthInfo",
]
