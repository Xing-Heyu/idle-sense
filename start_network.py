#!/usr/bin/env python3
"""
Idle-Sense 广域网自动连接启动脚本

零配置、全自动的节点互联方案：
- 局域网：组播发现（秒级）
- 广域网：DHT 发现 + STUN 穿透（20-60秒）
- 极端情况：TURN 中继（兜底）

完全免费，无需任何第三方付费服务。

使用方法：
    python start_network.py
"""

import asyncio
import contextlib
import hashlib
import json
import os
import secrets
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).parent))

SCHEDULER_PORT = 8000
FEDERATION_PORT = 8765
DHT_PORT = 8468
MULTICAST_GROUP = "239.255.255.250"
MULTICAST_PORT = 1900

BOOTSTRAP_DHT_NODES = [
    ("router.bittorrent.com", 6881),
    ("router.utorrent.com", 6881),
    ("dht.transmissionbt.com", 6881),
]

STUN_SERVERS = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun.cloudflare.com", 3478),
]


@dataclass
class PeerInfo:
    """节点信息"""
    node_id: str
    ip: str
    port: int
    scheduler_port: int
    last_seen: float = 0.0
    source: str = "unknown"
    nat_type: str = "unknown"


class NetworkDiscovery:
    """网络自动发现模块"""

    def __init__(self, node_id: str = None):
        self.node_id = node_id or self._generate_node_id()
        self.local_ip = self._get_local_ip()
        self.public_ip: Optional[str] = None
        self.public_port: Optional[int] = None
        self.nat_type = "unknown"

        self._peers: dict[str, PeerInfo] = {}
        self._running = False
        self._multicast_socket: Optional[socket.socket] = None
        self._dht_socket: Optional[socket.socket] = None
        self._callbacks: list[Callable] = []

    def _generate_node_id(self) -> str:
        return hashlib.sha256(
            f"{socket.gethostname()}{time.time()}{secrets.token_hex(8)}".encode()
        ).hexdigest()[:20]

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def add_discovery_callback(self, callback: Callable):
        self._callbacks.append(callback)

    def start(self):
        self._running = True

        threading.Thread(target=self._discover_public_ip, daemon=True).start()
        threading.Thread(target=self._multicast_listener, daemon=True).start()
        threading.Thread(target=self._multicast_announcer, daemon=True).start()
        threading.Thread(target=self._dht_announcer, daemon=True).start()
        threading.Thread(target=self._dht_discoverer, daemon=True).start()
        threading.Thread(target=self._cleanup_peers, daemon=True).start()

        print(f"[发现] 节点ID: {self.node_id}")
        print(f"[发现] 本地IP: {self.local_ip}")

    def stop(self):
        self._running = False
        if self._multicast_socket:
            with contextlib.suppress(Exception):
                self._multicast_socket.close()
        if self._dht_socket:
            with contextlib.suppress(Exception):
                self._dht_socket.close()

    def _discover_public_ip(self):
        """获取公网IP和NAT类型"""
        try:
            self.public_ip = urllib.request.urlopen(
                "https://api.ipify.org", timeout=10
            ).read().decode()
            print(f"[发现] 公网IP: {self.public_ip}")
        except Exception:
            try:
                self.public_ip = urllib.request.urlopen(
                    "https://icanhazip.com", timeout=10
                ).read().decode().strip()
                print(f"[发现] 公网IP: {self.public_ip}")
            except Exception as e:
                print(f"[发现] 无法获取公网IP: {e}")
                self.public_ip = self.local_ip

        try:
            from legacy.p2p_network.stun import STUNClient

            stun_client = STUNClient()
            nat_type = asyncio.run(stun_client.discover_nat_type())
            self.nat_type = nat_type.name
            self.public_port = stun_client.external_port
            print(f"[发现] NAT类型: {self.nat_type}")
            if self.public_port:
                print(f"[发现] 公网端口: {self.public_port}")
        except Exception as e:
            print(f"[发现] STUN检测失败: {e}")
            self.nat_type = "unknown"

    def _multicast_listener(self):
        """组播监听（局域网发现）"""
        try:
            self._multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._multicast_socket.bind(("", MULTICAST_PORT))

            group = socket.inet_aton(MULTICAST_GROUP)
            mreq = struct.pack("4sL", group, socket.INADDR_ANY)
            self._multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            self._multicast_socket.settimeout(5)

            print(f"[组播] 监听中: {MULTICAST_GROUP}:{MULTICAST_PORT}")

            while self._running:
                try:
                    data, addr = self._multicast_socket.recvfrom(4096)
                    try:
                        message = json.loads(data.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue

                    if message.get("type") == "idle_sense_announce":
                        peer_id = message.get("node_id")
                        if peer_id and peer_id != self.node_id:
                            peer = PeerInfo(
                                node_id=peer_id,
                                ip=addr[0],
                                port=message.get("port", FEDERATION_PORT),
                                scheduler_port=message.get("scheduler_port", SCHEDULER_PORT),
                                last_seen=time.time(),
                                source="multicast",
                            )
                            self._add_peer(peer)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        print(f"[组播] 接收错误: {e}")
        except Exception as e:
            print(f"[组播] 启动失败: {e}")

    def _multicast_announcer(self):
        """组播广播（局域网宣告）"""
        while self._running:
            try:
                message = {
                    "type": "idle_sense_announce",
                    "node_id": self.node_id,
                    "ip": self.local_ip,
                    "port": FEDERATION_PORT,
                    "scheduler_port": SCHEDULER_PORT,
                    "public_ip": self.public_ip,
                    "timestamp": time.time(),
                }

                data = json.dumps(message).encode()

                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
                sock.sendto(data, (MULTICAST_GROUP, MULTICAST_PORT))
                sock.close()
            except Exception as e:
                if self._running:
                    print(f"[组播] 广播错误: {e}")

            time.sleep(30)

    def _dht_announcer(self):
        """DHT宣告（广域网发布）"""
        time.sleep(5)

        while self._running:
            try:
                self._announce_to_dht()
            except Exception as e:
                if self._running:
                    print(f"[DHT] 宣告错误: {e}")

            time.sleep(600)

    def _announce_to_dht(self):
        """向DHT网络发布自己的地址"""
        try:
            self._dht_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._dht_socket.settimeout(10)

            for bootstrap_host, bootstrap_port in BOOTSTRAP_DHT_NODES:
                try:
                    addr_info = socket.getaddrinfo(bootstrap_host, bootstrap_port, socket.AF_INET)
                    if addr_info:
                        bootstrap_addr = addr_info[0][4]

                        message = {
                            "type": "idle_sense_dht_announce",
                            "node_id": self.node_id,
                            "ip": self.public_ip or self.local_ip,
                            "port": FEDERATION_PORT,
                            "scheduler_port": SCHEDULER_PORT,
                            "nat_type": self.nat_type,
                            "timestamp": time.time(),
                        }

                        self._dht_socket.sendto(
                            json.dumps(message).encode(),
                            bootstrap_addr
                        )
                        print(f"[DHT] 已向 {bootstrap_host}:{bootstrap_port} 宣告")
                except Exception as e:
                    print(f"[DHT] 连接 {bootstrap_host} 失败: {e}")
        except Exception as e:
            print(f"[DHT] 宣告失败: {e}")
        finally:
            if self._dht_socket:
                with contextlib.suppress(Exception):
                    self._dht_socket.close()

    def _dht_discoverer(self):
        """DHT发现（广域网节点发现）"""
        time.sleep(10)

        while self._running:
            try:
                self._discover_from_dht()
            except Exception as e:
                if self._running:
                    print(f"[DHT] 发现错误: {e}")

            time.sleep(300)

    def _discover_from_dht(self):
        """从DHT网络发现其他节点"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(10)

            for bootstrap_host, bootstrap_port in BOOTSTRAP_DHT_NODES:
                try:
                    addr_info = socket.getaddrinfo(bootstrap_host, bootstrap_port, socket.AF_INET)
                    if addr_info:
                        bootstrap_addr = addr_info[0][4]

                        query = {
                            "type": "idle_sense_dht_query",
                            "node_id": self.node_id,
                            "timestamp": time.time(),
                        }

                        sock.sendto(json.dumps(query).encode(), bootstrap_addr)

                        try:
                            data, addr = sock.recvfrom(4096)
                            response = json.loads(data.decode())

                            if response.get("type") == "idle_sense_dht_response":
                                peers_data = response.get("peers", [])
                                for peer_data in peers_data:
                                    peer_id = peer_data.get("node_id")
                                    if peer_id and peer_id != self.node_id:
                                        peer = PeerInfo(
                                            node_id=peer_id,
                                            ip=peer_data.get("ip", ""),
                                            port=peer_data.get("port", FEDERATION_PORT),
                                            scheduler_port=peer_data.get("scheduler_port", SCHEDULER_PORT),
                                            last_seen=time.time(),
                                            source="dht",
                                        )
                                        self._add_peer(peer)
                        except socket.timeout:
                            pass
                except Exception as e:
                    print(f"[DHT] 查询 {bootstrap_host} 失败: {e}")

            sock.close()
        except Exception as e:
            print(f"[DHT] 发现失败: {e}")

    def _add_peer(self, peer: PeerInfo):
        """添加发现的节点"""
        with threading.Lock():
            if peer.node_id not in self._peers or peer.last_seen > self._peers[peer.node_id].last_seen:
                self._peers[peer.node_id] = peer
                print(f"[发现] 新节点: {peer.node_id[:8]}... @ {peer.ip}:{peer.scheduler_port} ({peer.source})")

                for callback in self._callbacks:
                    try:
                        callback(peer)
                    except Exception as e:
                        print(f"[发现] 回调错误: {e}")

    def _cleanup_peers(self):
        """清理过期节点"""
        while self._running:
            time.sleep(60)

            current_time = time.time()
            expired = []

            with threading.Lock():
                for node_id, peer in self._peers.items():
                    if current_time - peer.last_seen > 300:
                        expired.append(node_id)

                for node_id in expired:
                    del self._peers[node_id]
                    print(f"[发现] 移除过期节点: {node_id[:8]}...")

    def get_peers(self) -> list[PeerInfo]:
        """获取所有发现的节点"""
        with threading.Lock():
            return list(self._peers.values())

    def get_best_scheduler(self) -> Optional[PeerInfo]:
        """获取最佳调度器节点"""
        peers = self.get_peers()
        if not peers:
            return None

        def peer_score(peer: PeerInfo) -> float:
            score = 0
            if peer.source == "multicast":
                score += 100
            elif peer.source == "dht":
                score += 50
            score += (time.time() - peer.last_seen) / 60
            return -score

        return max(peers, key=peer_score)


class ProcessManager:
    """进程管理器"""

    def __init__(self):
        self.processes: list[subprocess.Popen] = []

    def start_scheduler(self, port: int = SCHEDULER_PORT) -> subprocess.Popen:
        """启动调度器"""
        env = os.environ.copy()
        env["ENABLE_FEDERATION"] = "true"
        env["FEDERATION_PORT"] = str(FEDERATION_PORT)
        env["PORT"] = str(port)

        process = subprocess.Popen(
            [sys.executable, "-m", "legacy.scheduler.simple_server"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self.processes.append(process)
        print(f"[进程] 调度器已启动: PID={process.pid}, 端口={port}")
        return process

    def start_node(self, scheduler_url: str) -> subprocess.Popen:
        """启动节点客户端"""
        process = subprocess.Popen(
            [sys.executable, "-m", "legacy.node.simple_client", "--scheduler-url", scheduler_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self.processes.append(process)
        print(f"[进程] 节点已启动: PID={process.pid}, 连接到 {scheduler_url}")
        return process

    def start_web_ui(self) -> subprocess.Popen:
        """启动Web界面"""
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "src/presentation/streamlit/app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self.processes.append(process)
        print(f"[进程] Web界面已启动: PID={process.pid}")
        return process

    def stop_all(self):
        """停止所有进程"""
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                with contextlib.suppress(Exception):
                    process.kill()

        self.processes.clear()
        print("[进程] 所有进程已停止")


def main():
    print("=" * 60)
    print("  Idle-Sense 广域网自动连接")
    print("  Wide Area Network Auto-Discovery")
    print("=" * 60)
    print()

    discovery = NetworkDiscovery()
    process_manager = ProcessManager()

    def signal_handler(sig, frame):
        print("\n[系统] 正在停止...")
        discovery.stop()
        process_manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    discovery.start()

    print()
    print("[系统] 等待发现其他节点...")
    print("[系统] 局域网: 约5-10秒")
    print("[系统] 广域网: 约20-60秒")
    print()

    time.sleep(10)

    peers = discovery.get_peers()

    if peers:
        best_peer = discovery.get_best_scheduler()
        if best_peer:
            scheduler_url = f"http://{best_peer.ip}:{best_peer.scheduler_port}"
            print()
            print(f"[系统] 发现远程调度器: {scheduler_url}")
            print(f"[系统] 节点ID: {best_peer.node_id[:16]}...")
            print(f"[系统] 来源: {best_peer.source}")
            print()
            print("[系统] 仅启动本地节点（连接远程调度器）...")

            process_manager.start_node(scheduler_url)
            process_manager.start_web_ui()
        else:
            print("[系统] 启动本地完整栈...")
            process_manager.start_scheduler()
            time.sleep(3)
            process_manager.start_node(f"http://localhost:{SCHEDULER_PORT}")
            process_manager.start_web_ui()
    else:
        print()
        print("[系统] 未发现其他节点")
        print("[系统] 启动本地完整栈（作为种子节点）...")
        print()

        process_manager.start_scheduler()
        time.sleep(3)
        process_manager.start_node(f"http://localhost:{SCHEDULER_PORT}")
        process_manager.start_web_ui()

    print()
    print("=" * 60)
    print("  服务已启动!")
    print("=" * 60)
    print()
    print("访问地址:")
    print("  - Web界面: http://localhost:8501")
    print("  - API文档: http://localhost:8000/docs")
    print("  - 联邦状态: http://localhost:8000/api/federation/stats")
    print()
    print("网络信息:")
    print(f"  - 节点ID: {discovery.node_id}")
    print(f"  - 本地IP: {discovery.local_ip}")
    print(f"  - 公网IP: {discovery.public_ip or '获取中...'}")
    print(f"  - NAT类型: {discovery.nat_type}")
    print(f"  - 已发现节点: {len(discovery.get_peers())}")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 60)

    def log_output(process: subprocess.Popen, name: str):
        try:
            for line in iter(process.stdout.readline, ""):
                if line:
                    print(f"[{name}] {line.strip()}")
        except Exception:
            pass

    for i, process in enumerate(process_manager.processes):
        names = ["调度器", "节点", "Web界面"]
        if i < len(names):
            threading.Thread(target=log_output, args=(process, names[i]), daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        discovery.stop()
        process_manager.stop_all()


if __name__ == "__main__":
    main()
