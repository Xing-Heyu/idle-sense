"""
调度器联邦模块 - P2P Federation for Schedulers

实现"对等个人中心"架构：
- 每个用户运行自己的完整栈（Web UI + 调度器 + 本地节点）
- 调度器之间通过 P2P 网络互相连接
- 形成去中心化的算力联盟

功能：
1. 发现：通过组播/DHT 找到其他调度器
2. 握手：与其他调度器建立长连接
3. 节点信息同步：广播本地节点列表
4. 任务路由：本地无空闲节点时转发任务
5. 结果回传：远程执行结果沿原路径返回
"""

import asyncio
import hashlib
import json
import os
import socket
import struct
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


@dataclass
class RemoteScheduler:
    """远程调度器信息"""
    scheduler_id: str
    address: str
    port: int
    last_seen: float = 0.0
    connection: Any = None
    nodes: dict = field(default_factory=dict)
    reputation: float = 1.0
    is_connected: bool = False


@dataclass
class FederationTask:
    """联邦任务"""
    task_id: int
    code: str
    source_scheduler: str
    target_scheduler: Optional[str] = None
    timeout: int = 300
    resources: dict = field(default_factory=lambda: {"cpu": 1.0, "memory": 512})
    created_at: float = field(default_factory=time.time)
    status: str = "pending"


@dataclass
class FederationResult:
    """联邦任务结果"""
    task_id: int
    source_scheduler: str
    executing_scheduler: str
    executing_node: str
    result: str
    success: bool = True
    error: Optional[str] = None
    execution_time: float = 0.0


class MulticastDiscovery:
    """组播发现服务"""
    
    MULTICAST_GROUP = "239.255.255.250"
    MULTICAST_PORT = 1900
    DISCOVERY_INTERVAL = 30
    
    def __init__(self, scheduler_id: str, port: int, federation_port: int):
        self.scheduler_id = scheduler_id
        self.port = port
        self.federation_port = federation_port
        self._running = False
        self._socket: Optional[socket.socket] = None
        self._discovered: dict[str, tuple[str, int]] = {}
        self._callbacks: list[Callable] = []
    
    def add_discovery_callback(self, callback: Callable):
        self._callbacks.append(callback)
    
    def start(self):
        self._running = True
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self._socket.bind(("", self.MULTICAST_PORT))
            group = socket.inet_aton(self.MULTICAST_GROUP)
            mreq = struct.pack("4sL", group, socket.INADDR_ANY)
            self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            self._socket.settimeout(5)
            
            threading.Thread(target=self._listen_loop, daemon=True).start()
            threading.Thread(target=self._announce_loop, daemon=True).start()
            print(f"[组播发现] 已启动，监听组播组 {self.MULTICAST_GROUP}:{self.MULTICAST_PORT}")
        except Exception as e:
            print(f"[组播发现] 启动失败: {e}")
            self._running = False
    
    def stop(self):
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
    
    def _listen_loop(self):
        while self._running:
            try:
                data, addr = self._socket.recvfrom(4096)
                
                if not data or len(data.strip()) == 0:
                    continue
                
                try:
                    message = json.loads(data.decode())
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    continue
                
                if message.get("type") == "scheduler_announce":
                    scheduler_id = message.get("scheduler_id")
                    scheduler_port = message.get("federation_port")
                    
                    if scheduler_id and scheduler_id != self.scheduler_id:
                        self._discovered[scheduler_id] = (addr[0], scheduler_port)
                        print(f"[组播发现] 发现调度器: {scheduler_id} @ {addr[0]}:{scheduler_port}")
                        
                        for callback in self._callbacks:
                            try:
                                callback(scheduler_id, addr[0], scheduler_port)
                            except Exception as e:
                                print(f"[组播发现] 回调错误: {e}")
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    pass
    
    def _announce_loop(self):
        while self._running:
            try:
                message = {
                    "type": "scheduler_announce",
                    "scheduler_id": self.scheduler_id,
                    "http_port": self.port,
                    "federation_port": self.federation_port,
                    "timestamp": time.time(),
                }
                
                data = json.dumps(message).encode()
                self._socket.sendto(data, (self.MULTICAST_GROUP, self.MULTICAST_PORT))
            except Exception as e:
                if self._running:
                    print(f"[组播发现] 广播错误: {e}")
            
            time.sleep(self.DISCOVERY_INTERVAL)
    
    def get_discovered_schedulers(self) -> dict[str, tuple[str, int]]:
        return self._discovered.copy()


class DHTDiscovery:
    """DHT 发现服务（基于 Kademlia）"""
    
    def __init__(self, scheduler_id: str, port: int):
        self.scheduler_id = scheduler_id
        self.port = port
        self._dht: Optional[Any] = None
        self._running = False
    
    async def start(self, bootstrap_nodes: list[tuple[str, int]] = None):
        try:
            from legacy.p2p_network import KademliaDHT
            
            self._dht = KademliaDHT(node_id=self.scheduler_id, port=self.port)
            await self._dht.start(bootstrap_nodes=bootstrap_nodes)
            self._running = True
            print(f"[DHT发现] 已启动，端口: {self.port}")
        except Exception as e:
            print(f"[DHT发现] 启动失败: {e}")
    
    async def stop(self):
        self._running = False
        if self._dht:
            await self._dht.stop()
    
    async def register_scheduler(self, http_port: int, federation_port: int):
        if not self._dht:
            return False
        
        key = f"scheduler:{self.scheduler_id}"
        value = {
            "scheduler_id": self.scheduler_id,
            "http_port": http_port,
            "federation_port": federation_port,
            "timestamp": time.time(),
        }
        return await self._dht.set(key, value)
    
    async def discover_schedulers(self) -> list[dict]:
        if not self._dht:
            return []
        
        schedulers = []
        try:
            keys = await self._dht.get_keys_with_prefix("scheduler:")
            for key in keys:
                value = await self._dht.get(key)
                if value:
                    schedulers.append(value)
        except Exception as e:
            print(f"[DHT发现] 查询错误: {e}")
        
        return schedulers


class SchedulerFederation:
    """调度器联邦核心类"""
    
    DEFAULT_FEDERATION_PORT = 8765
    HEARTBEAT_INTERVAL = 30
    NODE_SYNC_INTERVAL = 60
    CONNECTION_TIMEOUT = 10
    
    def __init__(
        self,
        scheduler_id: str = None,
        http_port: int = 8000,
        federation_port: int = None,
        storage: Any = None,
    ):
        self.scheduler_id = scheduler_id or self._generate_scheduler_id()
        self.http_port = http_port
        self.federation_port = federation_port or self.DEFAULT_FEDERATION_PORT
        self.storage = storage
        
        self._running = False
        self._remote_schedulers: dict[str, RemoteScheduler] = {}
        self._pending_federation_tasks: dict[int, FederationTask] = {}
        self._federation_results: dict[int, FederationResult] = {}
        self._task_callbacks: dict[int, Callable] = {}
        
        self._discovery: Optional[MulticastDiscovery] = None
        self._dht: Optional[DHTDiscovery] = None
        self._server: Optional[asyncio.Server] = None
        
        self._lock = threading.RLock()
        
        self._stats = {
            "tasks_forwarded": 0,
            "tasks_received": 0,
            "results_returned": 0,
            "nodes_synced": 0,
            "schedulers_discovered": 0,
        }
    
    def _generate_scheduler_id(self) -> str:
        return hashlib.sha256(
            f"{socket.gethostname()}{time.time()}{uuid.uuid4()}".encode()
        ).hexdigest()[:16]
    
    def start(self):
        self._running = True
        
        self._discovery = MulticastDiscovery(
            self.scheduler_id,
            self.http_port,
            self.federation_port,
        )
        self._discovery.add_discovery_callback(self._on_scheduler_discovered)
        self._discovery.start()
        
        threading.Thread(target=self._run_async_server, daemon=True).start()
        
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._node_sync_loop, daemon=True).start()
        threading.Thread(target=self._cleanup_loop, daemon=True).start()
        
        print("=" * 60)
        print("调度器联邦模块已启动")
        print(f"调度器ID: {self.scheduler_id}")
        print(f"HTTP端口: {self.http_port}")
        print(f"联邦端口: {self.federation_port}")
        print("=" * 60)
    
    def stop(self):
        self._running = False
        
        if self._discovery:
            self._discovery.stop()
        
        for scheduler in self._remote_schedulers.values():
            if scheduler.connection:
                try:
                    asyncio.run(scheduler.connection.close())
                except Exception:
                    pass
        
        print("[联邦] 已停止")
    
    def _run_async_server(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            self._server = loop.run_until_complete(
                asyncio.start_server(
                    self._handle_connection,
                    "0.0.0.0",
                    self.federation_port,
                )
            )
            print(f"[联邦] TCP服务器已启动，监听端口 {self.federation_port}")
            loop.run_forever()
        except Exception as e:
            print(f"[联邦] 服务器错误: {e}")
        finally:
            loop.close()
    
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        print(f"[联邦] 新连接: {addr}")
        
        try:
            while self._running:
                data = await asyncio.wait_for(reader.read(65536), timeout=60)
                if not data:
                    break
                
                message = json.loads(data.decode())
                await self._process_message(message, writer)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"[联邦] 连接错误: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"[联邦] 连接关闭: {addr}")
    
    async def _process_message(self, message: dict, writer: asyncio.StreamWriter):
        msg_type = message.get("type")
        
        if msg_type == "handshake":
            await self._handle_handshake(message, writer)
        elif msg_type == "node_sync":
            await self._handle_node_sync(message)
        elif msg_type == "task_forward":
            await self._handle_task_forward(message)
        elif msg_type == "result_return":
            await self._handle_result_return(message)
        elif msg_type == "heartbeat":
            await self._handle_heartbeat(message)
    
    async def _handle_handshake(self, message: dict, writer: asyncio.StreamWriter):
        scheduler_id = message.get("scheduler_id")
        http_port = message.get("http_port")
        
        with self._lock:
            if scheduler_id not in self._remote_schedulers:
                self._remote_schedulers[scheduler_id] = RemoteScheduler(
                    scheduler_id=scheduler_id,
                    address=writer.get_extra_info("peername")[0],
                    port=http_port,
                    last_seen=time.time(),
                    connection=writer,
                    is_connected=True,
                )
            else:
                self._remote_schedulers[scheduler_id].last_seen = time.time()
                self._remote_schedulers[scheduler_id].connection = writer
                self._remote_schedulers[scheduler_id].is_connected = True
        
        print(f"[联邦] 握手成功: {scheduler_id}")
        
        response = {
            "type": "handshake_ack",
            "scheduler_id": self.scheduler_id,
            "http_port": self.http_port,
        }
        writer.write(json.dumps(response).encode())
        await writer.drain()
    
    async def _handle_node_sync(self, message: dict):
        scheduler_id = message.get("scheduler_id")
        nodes = message.get("nodes", {})
        
        with self._lock:
            if scheduler_id in self._remote_schedulers:
                self._remote_schedulers[scheduler_id].nodes = nodes
                self._remote_schedulers[scheduler_id].last_seen = time.time()
        
        self._stats["nodes_synced"] += len(nodes)
        print(f"[联邦] 节点同步: {scheduler_id} -> {len(nodes)} 个节点")
    
    async def _handle_task_forward(self, message: dict):
        task_data = message.get("task")
        source_scheduler = message.get("source_scheduler")
        
        task = FederationTask(
            task_id=task_data["task_id"],
            code=task_data["code"],
            source_scheduler=source_scheduler,
            timeout=task_data.get("timeout", 300),
            resources=task_data.get("resources", {}),
        )
        
        with self._lock:
            self._pending_federation_tasks[task.task_id] = task
        
        self._stats["tasks_received"] += 1
        print(f"[联邦] 收到远程任务: {task.task_id} 来自 {source_scheduler}")
        
        if self.storage:
            local_task_id = self.storage.add_task(
                code=task.code,
                timeout=task.timeout,
                resources=task.resources,
                user_id=f"federation:{source_scheduler}",
            )
            self._task_callbacks[local_task_id] = (task.task_id, source_scheduler)
    
    async def _handle_result_return(self, message: dict):
        result_data = message.get("result")
        task_id = result_data["task_id"]
        
        result = FederationResult(
            task_id=task_id,
            source_scheduler=result_data["source_scheduler"],
            executing_scheduler=result_data["executing_scheduler"],
            executing_node=result_data["executing_node"],
            result=result_data["result"],
            success=result_data.get("success", True),
            error=result_data.get("error"),
            execution_time=result_data.get("execution_time", 0),
        )
        
        with self._lock:
            self._federation_results[task_id] = result
            if task_id in self._pending_federation_tasks:
                del self._pending_federation_tasks[task_id]
        
        self._stats["results_returned"] += 1
        print(f"[联邦] 收到远程结果: 任务 {task_id}")
    
    async def _handle_heartbeat(self, message: dict):
        scheduler_id = message.get("scheduler_id")
        
        with self._lock:
            if scheduler_id in self._remote_schedulers:
                self._remote_schedulers[scheduler_id].last_seen = time.time()
    
    def _on_scheduler_discovered(self, scheduler_id: str, address: str, port: int):
        if scheduler_id == self.scheduler_id:
            return
        
        self._stats["schedulers_discovered"] += 1
        print(f"[联邦] 发现远程调度器: {scheduler_id} @ {address}:{port}")
        
        threading.Thread(
            target=self._connect_to_scheduler,
            args=(scheduler_id, address, port),
            daemon=True,
        ).start()
    
    def _connect_to_scheduler(self, scheduler_id: str, address: str, port: int):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._async_connect_to_scheduler(scheduler_id, address, port))
        except Exception as e:
            print(f"[联邦] 连接失败: {scheduler_id} - {e}")
        finally:
            loop.close()
    
    async def _async_connect_to_scheduler(self, scheduler_id: str, address: str, port: int):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(address, port),
                timeout=self.CONNECTION_TIMEOUT,
            )
            
            handshake = {
                "type": "handshake",
                "scheduler_id": self.scheduler_id,
                "http_port": self.http_port,
            }
            writer.write(json.dumps(handshake).encode())
            await writer.drain()
            
            response_data = await asyncio.wait_for(reader.read(4096), timeout=10)
            response = json.loads(response_data.decode())
            
            if response.get("type") == "handshake_ack":
                with self._lock:
                    self._remote_schedulers[scheduler_id] = RemoteScheduler(
                        scheduler_id=scheduler_id,
                        address=address,
                        port=response.get("http_port", 8000),
                        last_seen=time.time(),
                        connection=writer,
                        is_connected=True,
                    )
                
                print(f"[联邦] 已连接到远程调度器: {scheduler_id}")
                
                await self._sync_nodes_to_scheduler(scheduler_id, writer)
        except Exception as e:
            raise Exception(f"连接错误: {e}")
    
    async def _sync_nodes_to_scheduler(self, scheduler_id: str, writer: asyncio.StreamWriter):
        if not self.storage:
            return
        
        nodes = {}
        try:
            local_nodes = self.storage.get_available_nodes(include_busy=True)
            for node in local_nodes:
                nodes[node["node_id"]] = {
                    "capacity": node.get("capacity", {}),
                    "is_idle": node.get("is_idle", False),
                    "status": node.get("status", "unknown"),
                }
        except Exception as e:
            print(f"[联邦] 获取本地节点失败: {e}")
            return
        
        message = {
            "type": "node_sync",
            "scheduler_id": self.scheduler_id,
            "nodes": nodes,
            "timestamp": time.time(),
        }
        
        try:
            writer.write(json.dumps(message).encode())
            await writer.drain()
        except Exception as e:
            print(f"[联邦] 节点同步发送失败: {e}")
    
    def _heartbeat_loop(self):
        while self._running:
            try:
                self._send_heartbeats()
            except Exception as e:
                print(f"[联邦] 心跳错误: {e}")
            
            time.sleep(self.HEARTBEAT_INTERVAL)
    
    def _send_heartbeats(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            tasks = []
            for scheduler in self._remote_schedulers.values():
                if scheduler.connection and scheduler.is_connected:
                    tasks.append(self._send_heartbeat(scheduler))
            
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        finally:
            loop.close()
    
    async def _send_heartbeat(self, scheduler: RemoteScheduler):
        try:
            message = {
                "type": "heartbeat",
                "scheduler_id": self.scheduler_id,
                "timestamp": time.time(),
            }
            scheduler.connection.write(json.dumps(message).encode())
            await scheduler.connection.drain()
        except Exception:
            scheduler.is_connected = False
    
    def _node_sync_loop(self):
        while self._running:
            try:
                self._sync_all_nodes()
            except Exception as e:
                print(f"[联邦] 节点同步错误: {e}")
            
            time.sleep(self.NODE_SYNC_INTERVAL)
    
    def _sync_all_nodes(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            tasks = []
            for scheduler in self._remote_schedulers.values():
                if scheduler.connection and scheduler.is_connected:
                    tasks.append(self._sync_nodes_to_scheduler(
                        scheduler.scheduler_id, scheduler.connection
                    ))
            
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        finally:
            loop.close()
    
    def _cleanup_loop(self):
        while self._running:
            try:
                self._cleanup_dead_schedulers()
            except Exception as e:
                print(f"[联邦] 清理错误: {e}")
            
            time.sleep(60)
    
    def _cleanup_dead_schedulers(self):
        current_time = time.time()
        timeout = 180
        
        with self._lock:
            dead_schedulers = []
            for scheduler_id, scheduler in self._remote_schedulers.items():
                if current_time - scheduler.last_seen > timeout:
                    dead_schedulers.append(scheduler_id)
            
            for scheduler_id in dead_schedulers:
                del self._remote_schedulers[scheduler_id]
                print(f"[联邦] 移除死亡调度器: {scheduler_id}")
    
    def get_all_nodes(self) -> list[dict]:
        """获取所有节点（本地 + 远程）"""
        all_nodes = []
        
        if self.storage:
            try:
                local_nodes = self.storage.get_available_nodes(include_busy=True)
                for node in local_nodes:
                    node["source"] = "local"
                    node["scheduler_id"] = self.scheduler_id
                    all_nodes.append(node)
            except Exception as e:
                print(f"[联邦] 获取本地节点失败: {e}")
        
        with self._lock:
            for scheduler_id, scheduler in self._remote_schedulers.items():
                for node_id, node_info in scheduler.nodes.items():
                    all_nodes.append({
                        "node_id": node_id,
                        "source": "remote",
                        "scheduler_id": scheduler_id,
                        "scheduler_address": scheduler.address,
                        "capacity": node_info.get("capacity", {}),
                        "is_idle": node_info.get("is_idle", False),
                        "status": node_info.get("status", "unknown"),
                    })
        
        return all_nodes
    
    def forward_task(self, task_id: int, code: str, timeout: int = 300, resources: dict = None) -> bool:
        """转发任务到远程调度器"""
        best_scheduler = self._find_best_remote_scheduler()
        
        if not best_scheduler:
            print("[联邦] 无可用远程调度器")
            return False
        
        task = FederationTask(
            task_id=task_id,
            code=code,
            source_scheduler=self.scheduler_id,
            target_scheduler=best_scheduler.scheduler_id,
            timeout=timeout,
            resources=resources or {"cpu": 1.0, "memory": 512},
        )
        
        with self._lock:
            self._pending_federation_tasks[task_id] = task
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success = loop.run_until_complete(self._async_forward_task(task, best_scheduler))
            if success:
                self._stats["tasks_forwarded"] += 1
            return success
        finally:
            loop.close()
    
    async def _async_forward_task(self, task: FederationTask, scheduler: RemoteScheduler) -> bool:
        if not scheduler.connection or not scheduler.is_connected:
            return False
        
        message = {
            "type": "task_forward",
            "source_scheduler": self.scheduler_id,
            "task": {
                "task_id": task.task_id,
                "code": task.code,
                "timeout": task.timeout,
                "resources": task.resources,
            },
            "timestamp": time.time(),
        }
        
        try:
            scheduler.connection.write(json.dumps(message).encode())
            await scheduler.connection.drain()
            print(f"[联邦] 任务已转发: {task.task_id} -> {scheduler.scheduler_id}")
            return True
        except Exception as e:
            print(f"[联邦] 任务转发失败: {e}")
            scheduler.is_connected = False
            return False
    
    def _find_best_remote_scheduler(self) -> Optional[RemoteScheduler]:
        """找到最佳远程调度器"""
        best_scheduler = None
        best_score = -1
        
        with self._lock:
            for scheduler in self._remote_schedulers.values():
                if not scheduler.is_connected:
                    continue
                
                idle_nodes = sum(1 for n in scheduler.nodes.values() if n.get("is_idle", False))
                
                if idle_nodes > 0:
                    score = idle_nodes * scheduler.reputation
                    if score > best_score:
                        best_score = score
                        best_scheduler = scheduler
        
        return best_scheduler
    
    def get_federation_stats(self) -> dict:
        """获取联邦统计信息"""
        with self._lock:
            return {
                "scheduler_id": self.scheduler_id,
                "remote_schedulers": len(self._remote_schedulers),
                "connected_schedulers": sum(
                    1 for s in self._remote_schedulers.values() if s.is_connected
                ),
                "total_remote_nodes": sum(
                    len(s.nodes) for s in self._remote_schedulers.values()
                ),
                "pending_federation_tasks": len(self._pending_federation_tasks),
                "stats": self._stats.copy(),
            }
    
    def on_local_task_completed(self, task_id: int, result: str, node_id: str, success: bool = True):
        """本地任务完成回调"""
        if task_id in self._task_callbacks:
            federation_task_id, source_scheduler = self._task_callbacks.pop(task_id)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(
                    self._return_result(
                        federation_task_id,
                        source_scheduler,
                        result,
                        node_id,
                        success,
                    )
                )
            finally:
                loop.close()
    
    async def _return_result(
        self,
        task_id: int,
        target_scheduler_id: str,
        result: str,
        node_id: str,
        success: bool,
    ):
        scheduler = self._remote_schedulers.get(target_scheduler_id)
        if not scheduler or not scheduler.connection:
            print(f"[联邦] 无法返回结果: 调度器 {target_scheduler_id} 未连接")
            return
        
        message = {
            "type": "result_return",
            "result": {
                "task_id": task_id,
                "source_scheduler": self.scheduler_id,
                "executing_scheduler": self.scheduler_id,
                "executing_node": node_id,
                "result": result,
                "success": success,
            },
            "timestamp": time.time(),
        }
        
        try:
            scheduler.connection.write(json.dumps(message).encode())
            await scheduler.connection.drain()
            print(f"[联邦] 结果已返回: 任务 {task_id} -> {target_scheduler_id}")
        except Exception as e:
            print(f"[联邦] 结果返回失败: {e}")


_federation_instance: Optional[SchedulerFederation] = None


def get_federation() -> Optional[SchedulerFederation]:
    """获取联邦实例"""
    return _federation_instance


def init_federation(
    scheduler_id: str = None,
    http_port: int = 8000,
    federation_port: int = None,
    storage: Any = None,
) -> SchedulerFederation:
    """初始化联邦模块"""
    global _federation_instance
    
    _federation_instance = SchedulerFederation(
        scheduler_id=scheduler_id,
        http_port=http_port,
        federation_port=federation_port,
        storage=storage,
    )
    
    return _federation_instance


def start_federation():
    """启动联邦模块"""
    global _federation_instance
    
    if _federation_instance:
        _federation_instance.start()
    else:
        print("[联邦] 错误: 未初始化联邦模块")


def stop_federation():
    """停止联邦模块"""
    global _federation_instance
    
    if _federation_instance:
        _federation_instance.stop()
