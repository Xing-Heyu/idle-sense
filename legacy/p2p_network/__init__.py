"""
P2P Network Module - Distributed Node Discovery and Communication.

Implements:
- Kademlia DHT for distributed hash table
- Gossip Protocol for message propagation
- NAT Traversal (STUN, UPnP, Hole Punching)
- P2P Node with bootstrap and peer management

References:
- Maymounkov & Mazieres, "Kademlia: A Peer-to-Peer Information System" (2002)
- Ford et al., "Peer-to-Peer Communication Across Network Address Translators" (2005)
- Ethereum devp2p protocol specification
"""

import asyncio
import contextlib
import hashlib
import json
import random
import socket
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class MessageType(Enum):
    PING = "ping"
    PONG = "pong"
    FIND_NODE = "find_node"
    FIND_NODE_RESPONSE = "find_node_response"
    STORE = "store"
    FIND_VALUE = "find_value"
    FIND_VALUE_RESPONSE = "find_value_response"
    GOSSIP = "gossip"
    TASK_REQUEST = "task_request"
    TASK_RESULT = "task_result"
    PEER_ANNOUNCE = "peer_announce"
    PEER_DISCONNECT = "peer_disconnect"


class NATType(Enum):
    UNKNOWN = "unknown"
    PUBLIC = "public"
    FULL_CONE = "full_cone"
    RESTRICTED_CONE = "restricted_cone"
    PORT_RESTRICTED = "port_restricted"
    SYMMETRIC = "symmetric"
    BLOCKED = "blocked"


class PeerState(Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"


@dataclass
class PeerInfo:
    node_id: str
    ip: str
    port: int
    capabilities: dict[str, Any] = field(default_factory=dict)
    last_seen: float = 0.0
    latency: float = 0.0
    state: PeerState = PeerState.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port,
            "capabilities": self.capabilities,
            "last_seen": self.last_seen,
            "latency": self.latency,
            "state": self.state.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PeerInfo":
        return cls(
            node_id=data["node_id"],
            ip=data["ip"],
            port=data["port"],
            capabilities=data.get("capabilities", {}),
            last_seen=data.get("last_seen", 0.0),
            latency=data.get("latency", 0.0),
            state=PeerState(data.get("state", "unknown")),
        )


@dataclass
class Message:
    type: MessageType
    sender_id: str
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(
        default_factory=lambda: hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
    )
    payload: dict[str, Any] = field(default_factory=dict)
    ttl: int = 3600

    def to_bytes(self) -> bytes:
        data = {
            "type": self.type.value,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "payload": self.payload,
            "ttl": self.ttl,
        }
        return json.dumps(data).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        obj = json.loads(data.decode("utf-8"))
        return cls(
            type=MessageType(obj["type"]),
            sender_id=obj["sender_id"],
            timestamp=obj.get("timestamp", time.time()),
            message_id=obj.get("message_id", ""),
            payload=obj.get("payload", {}),
            ttl=obj.get("ttl", 3600),
        )


class KademliaDHT:
    """Kademlia Distributed Hash Table implementation.

    Based on: Maymounkov & Mazieres, "Kademlia: A Peer-to-Peer Information System"
    Uses XOR metric for node distance and k-bucket routing table.
    """

    K = 20  # Bucket size (replication factor)
    ALPHA = 3  # Parallelism factor for lookups
    ID_BITS = 256  # Node ID space (SHA-256)

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.node_id_int = int.from_bytes(hashlib.sha256(node_id.encode()).digest(), "big")
        self.k_buckets: list[OrderedDict] = [OrderedDict() for _ in range(self.ID_BITS)]
        self.storage: dict[str, tuple[Any, float]] = {}
        self.pending_lookups: dict[str, asyncio.Event] = {}

    def _xor_distance(self, id1: int, id2: int) -> int:
        return id1 ^ id2

    def _get_bucket_index(self, peer_id_int: int) -> int:
        distance = self._xor_distance(self.node_id_int, peer_id_int)
        if distance == 0:
            return 0
        return distance.bit_length() - 1

    def _peer_id_to_int(self, peer_id: str) -> int:
        return int.from_bytes(hashlib.sha256(peer_id.encode()).digest(), "big")

    def add_peer(self, peer: PeerInfo) -> bool:
        peer_id_int = self._peer_id_to_int(peer.node_id)
        bucket_idx = self._get_bucket_index(peer_id_int)
        bucket = self.k_buckets[bucket_idx]

        if peer.node_id in bucket:
            bucket.move_to_end(peer.node_id)
            return True

        if len(bucket) < self.K:
            bucket[peer.node_id] = peer
            return True

        oldest_id = next(iter(bucket))
        oldest_peer = bucket[oldest_id]

        if oldest_peer.state == PeerState.OFFLINE:
            del bucket[oldest_id]
            bucket[peer.node_id] = peer
            return True

        return False

    def remove_peer(self, peer_id: str) -> bool:
        peer_id_int = self._peer_id_to_int(peer_id)
        bucket_idx = self._get_bucket_index(peer_id_int)
        bucket = self.k_buckets[bucket_idx]

        if peer_id in bucket:
            del bucket[peer_id]
            return True
        return False

    def get_peer(self, peer_id: str) -> Optional[PeerInfo]:
        peer_id_int = self._peer_id_to_int(peer_id)
        bucket_idx = self._get_bucket_index(peer_id_int)
        bucket = self.k_buckets[bucket_idx]
        return bucket.get(peer_id)

    def find_closest_peers(self, target_id: str, count: int = K) -> list[PeerInfo]:
        target_int = self._peer_id_to_int(target_id)
        closest: list[tuple[int, PeerInfo]] = []

        for bucket in self.k_buckets:
            for peer in bucket.values():
                distance = self._xor_distance(target_int, self._peer_id_to_int(peer.node_id))
                closest.append((distance, peer))

        closest.sort(key=lambda x: x[0])
        return [peer for _, peer in closest[:count]]

    def store(self, key: str, value: Any, ttl: float = 3600) -> bool:
        self.storage[key] = (value, time.time() + ttl)
        return True

    def get(self, key: str) -> Optional[Any]:
        if key not in self.storage:
            return None

        value, expiry = self.storage[key]
        if time.time() > expiry:
            del self.storage[key]
            return None

        return value

    def get_all_peers(self) -> list[PeerInfo]:
        peers = []
        for bucket in self.k_buckets:
            peers.extend(bucket.values())
        return peers

    def get_stats(self) -> dict[str, Any]:
        total_peers = sum(len(bucket) for bucket in self.k_buckets)
        non_empty_buckets = sum(1 for bucket in self.k_buckets if bucket)

        return {
            "node_id": self.node_id,
            "total_peers": total_peers,
            "non_empty_buckets": non_empty_buckets,
            "stored_items": len(self.storage),
            "k_bucket_distribution": [len(b) for b in self.k_buckets[:10]],
        }


class GossipProtocol:
    """Gossip Protocol for message propagation.

    Implements a push-pull gossip protocol with:
    - Message deduplication
    - TTL-based expiration
    - Configurable fanout
    """

    DEFAULT_FANOUT = 6
    DEFAULT_TTL = 3600
    MAX_MESSAGE_CACHE = 10000

    def __init__(self, node_id: str, dht: KademliaDHT):
        self.node_id = node_id
        self.dht = dht
        self.fanout = self.DEFAULT_FANOUT
        self.message_cache: OrderedDict[str, float] = OrderedDict()
        self.topic_handlers: dict[str, Callable] = {}
        self._running = False

    def register_handler(self, topic: str, handler: Callable):
        self.topic_handlers[topic] = handler

    def unregister_handler(self, topic: str):
        self.topic_handlers.pop(topic, None)

    def _is_message_seen(self, message_id: str) -> bool:
        if message_id in self.message_cache:
            return True

        self.message_cache[message_id] = time.time()

        while len(self.message_cache) > self.MAX_MESSAGE_CACHE:
            self.message_cache.popitem(last=False)

        return False

    def _cleanup_cache(self):
        now = time.time()
        expired = [
            msg_id
            for msg_id, timestamp in self.message_cache.items()
            if now - timestamp > self.DEFAULT_TTL
        ]
        for msg_id in expired:
            del self.message_cache[msg_id]

    def select_gossip_peers(self, exclude: set[str] = None) -> list[PeerInfo]:
        exclude = exclude or set()
        exclude.add(self.node_id)

        all_peers = self.dht.get_all_peers()
        candidates = [
            p for p in all_peers if p.node_id not in exclude and p.state == PeerState.ONLINE
        ]

        if len(candidates) <= self.fanout:
            return candidates

        return random.sample(candidates, self.fanout)

    async def broadcast(
        self,
        topic: str,
        data: dict[str, Any],
        exclude_peers: set[str] = None,
        send_func: Callable = None,
    ) -> int:
        message = Message(
            type=MessageType.GOSSIP,
            sender_id=self.node_id,
            payload={"topic": topic, "data": data},
        )

        if self._is_message_seen(message.message_id):
            return 0

        peers = self.select_gossip_peers(exclude_peers)
        sent_count = 0

        if send_func:
            for peer in peers:
                try:
                    await send_func(peer, message)
                    sent_count += 1
                except Exception:
                    pass

        return sent_count

    async def handle_message(self, message: Message, send_func: Callable = None):
        if self._is_message_seen(message.message_id):
            return

        payload = message.payload
        topic = payload.get("topic")
        data = payload.get("data", {})

        if topic and topic in self.topic_handlers:
            try:
                handler = self.topic_handlers[topic]
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                print(f"[Gossip] Handler error for topic {topic}: {e}")

        await self.broadcast(
            topic=topic,
            data=data,
            exclude_peers={message.sender_id},
            send_func=send_func,
        )

    def get_stats(self) -> dict[str, Any]:
        return {
            "cached_messages": len(self.message_cache),
            "registered_topics": list(self.topic_handlers.keys()),
            "fanout": self.fanout,
        }


class NATTraversal:
    """NAT Traversal implementation.

    Implements:
    - STUN-like external IP detection
    - UPnP port mapping
    - Hole punching for NAT traversal

    Reference: Ford et al., "Peer-to-Peer Communication Across NATs" (2005)
    """

    STUN_SERVERS = [
        ("stun.l.google.com", 19302),
        ("stun1.l.google.com", 19302),
        ("stun2.l.google.com", 19302),
    ]

    def __init__(self, local_port: int = 0):
        self.local_port = local_port
        self.nat_type = NATType.UNKNOWN
        self.external_ip: Optional[str] = None
        self.external_port: Optional[int] = None
        self._upnp_available = False

    def get_local_ip(self) -> Optional[str]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return None

    async def discover_nat_type(self) -> NATType:
        try:
            local_ip = self.get_local_ip()
            if not local_ip:
                return NATType.BLOCKED

            if self._check_public_ip():
                self.nat_type = NATType.PUBLIC
                return NATType.PUBLIC

            self.nat_type = NATType.UNKNOWN
            return self.nat_type

        except Exception:
            return NATType.UNKNOWN

    def _check_public_ip(self) -> bool:
        try:
            import urllib.request

            with urllib.request.urlopen("https://api.ipify.org?format=text", timeout=5) as response:
                external_ip = response.read().decode("utf-8").strip()
                local_ip = self.get_local_ip()

                self.external_ip = external_ip

                return external_ip == local_ip
        except Exception:
            return False

    async def setup_upnp(self, internal_port: int, external_port: int = None) -> bool:
        try:
            import upnpclient

            devices = upnpclient.discover()
            if not devices:
                self._upnp_available = False
                return False

            device = devices[0]
            external_port = external_port or internal_port

            device.AddPortMapping(
                NewRemoteHost="",
                NewExternalPort=external_port,
                NewProtocol="TCP",
                NewInternalPort=internal_port,
                NewInternalClient=self.get_local_ip(),
                NewEnabled="1",
                NewPortMappingDescription="Idle-Sense P2P",
                NewLeaseDuration="0",
            )

            self.external_port = external_port
            self._upnp_available = True
            return True

        except ImportError:
            self._upnp_available = False
            return False
        except Exception:
            self._upnp_available = False
            return False

    async def hole_punch(
        self, peer_ip: str, peer_port: int, timeout: float = 10.0
    ) -> Optional[socket.socket]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.local_port or 0))
        sock.setblocking(False)

        sock.getsockname()[1]

        loop = asyncio.get_event_loop()

        async def send_punches():
            end_time = time.time() + timeout
            while time.time() < end_time:
                try:
                    sock.sendto(b"PUNCH", (peer_ip, peer_port))
                    await asyncio.sleep(0.1)
                except Exception:
                    pass

        async def receive_response():
            end_time = time.time() + timeout
            while time.time() < end_time:
                try:
                    data, addr = await loop.sock_recvfrom(sock, 1024)
                    if addr[0] == peer_ip and data == b"PUNCH":
                        sock.sendto(b"PUNCH_ACK", addr)
                        return sock
                except Exception:
                    await asyncio.sleep(0.01)
            return None

        send_task = asyncio.create_task(send_punches())
        receive_task = asyncio.create_task(receive_response())

        done, pending = await asyncio.wait(
            [send_task, receive_task],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        if receive_task.done() and receive_task.result():
            return receive_task.result()

        sock.close()
        return None

    def get_stats(self) -> dict[str, Any]:
        return {
            "nat_type": self.nat_type.value,
            "external_ip": self.external_ip,
            "external_port": self.external_port,
            "upnp_available": self._upnp_available,
            "local_ip": self.get_local_ip(),
        }


class P2PNode:
    """Main P2P Node implementation.

    Combines DHT, Gossip Protocol, and NAT Traversal into a complete
    peer-to-peer node for distributed computing.
    """

    DEFAULT_PORT = 8765
    HEARTBEAT_INTERVAL = 30.0
    HEARTBEAT_TIMEOUT = 90.0
    DISCOVERY_INTERVAL = 60.0

    def __init__(
        self,
        node_id: str = None,
        port: int = None,
        capabilities: dict[str, Any] = None,
        bootstrap_nodes: list[tuple[str, int]] = None,
    ):
        self.node_id = node_id or self._generate_node_id()
        self.port = port or self.DEFAULT_PORT
        self.capabilities = capabilities or {}

        self.dht = KademliaDHT(self.node_id)
        self.gossip = GossipProtocol(self.node_id, self.dht)
        self.nat = NATTraversal(self.port)

        self.bootstrap_nodes = bootstrap_nodes or []
        self._peers: dict[str, PeerInfo] = {}
        self._running = False
        self._server: Optional[asyncio.Server] = None
        self._tasks: list[asyncio.Task] = []
        self._message_handlers: dict[MessageType, Callable] = {}
        self._start_time = time.time()

        self._register_default_handlers()

    def _generate_node_id(self) -> str:
        import uuid

        return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:32]

    def _register_default_handlers(self):
        self._message_handlers[MessageType.PING] = self._handle_ping
        self._message_handlers[MessageType.PONG] = self._handle_pong
        self._message_handlers[MessageType.FIND_NODE] = self._handle_find_node
        self._message_handlers[MessageType.FIND_NODE_RESPONSE] = self._handle_find_node_response
        self._message_handlers[MessageType.STORE] = self._handle_store
        self._message_handlers[MessageType.FIND_VALUE] = self._handle_find_value
        self._message_handlers[MessageType.FIND_VALUE_RESPONSE] = self._handle_find_value_response
        self._message_handlers[MessageType.GOSSIP] = self._handle_gossip
        self._message_handlers[MessageType.PEER_ANNOUNCE] = self._handle_peer_announce
        self._message_handlers[MessageType.PEER_DISCONNECT] = self._handle_peer_disconnect

    def register_handler(self, message_type: MessageType, handler: Callable):
        self._message_handlers[message_type] = handler

    async def start(self) -> bool:
        if self._running:
            return True

        self._running = True

        await self.nat.discover_nat_type()

        if self.nat.nat_type != NATType.PUBLIC:
            await self.nat.setup_upnp(self.port)

        try:
            self._server = await asyncio.start_server(
                self._handle_connection,
                "0.0.0.0",
                self.port,
            )
        except Exception as e:
            print(f"[P2P] Failed to start server: {e}")
            self._running = False
            return False

        self._tasks = [
            asyncio.create_task(self._run_heartbeat_loop()),
            asyncio.create_task(self._run_discovery_loop()),
            asyncio.create_task(self._run_cleanup_loop()),
        ]

        if self.bootstrap_nodes:
            asyncio.create_task(self._bootstrap())

        print(f"[P2P] Node started on port {self.port}")
        print(f"[P2P] Node ID: {self.node_id}")
        print(f"[P2P] NAT Type: {self.nat.nat_type.value}")

        return True

    async def stop(self):
        if not self._running:
            return

        self._running = False

        for peer in self._peers.values():
            await self._send_to_peer(
                peer,
                Message(
                    type=MessageType.PEER_DISCONNECT,
                    sender_id=self.node_id,
                ),
            )

        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        print("[P2P] Node stopped")

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            data = await reader.read(65536)
            if not data:
                return

            message = Message.from_bytes(data)
            await self._process_message(message, writer)

        except Exception as e:
            print(f"[P2P] Connection error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _process_message(self, message: Message, writer: asyncio.StreamWriter = None):
        handler = self._message_handlers.get(message.type)
        if handler:
            try:
                await handler(message, writer)
            except Exception as e:
                print(f"[P2P] Handler error for {message.type}: {e}")

    async def _handle_ping(self, message: Message, writer: asyncio.StreamReader = None):
        peer_id = message.sender_id
        if peer_id in self._peers:
            self._peers[peer_id].last_seen = time.time()

        pong = Message(
            type=MessageType.PONG,
            sender_id=self.node_id,
            payload={"ping_id": message.message_id},
        )

        if writer:
            writer.write(pong.to_bytes())
            await writer.drain()

    async def _handle_pong(self, message: Message, writer: asyncio.StreamReader = None):
        peer_id = message.sender_id
        if peer_id in self._peers:
            self._peers[peer_id].last_seen = time.time()

    async def _handle_find_node(self, message: Message, writer: asyncio.StreamReader = None):
        target_id = message.payload.get("target_id")
        closest = self.dht.find_closest_peers(target_id)

        response = Message(
            type=MessageType.FIND_NODE_RESPONSE,
            sender_id=self.node_id,
            payload={
                "peers": [p.to_dict() for p in closest],
                "target_id": target_id,
            },
            message_id=message.message_id,
        )

        if writer:
            writer.write(response.to_bytes())
            await writer.drain()

    async def _handle_find_node_response(
        self, message: Message, writer: asyncio.StreamReader = None
    ):
        peers_data = message.payload.get("peers", [])

        for peer_dict in peers_data:
            peer = PeerInfo.from_dict(peer_dict)
            if peer.node_id != self.node_id:
                self.dht.add_peer(peer)
                if peer.node_id not in self._peers:
                    self._peers[peer.node_id] = peer

    async def _handle_store(self, message: Message, writer: asyncio.StreamReader = None):
        key = message.payload.get("key")
        value = message.payload.get("value")
        ttl = message.payload.get("ttl", 3600)

        if key and value:
            self.dht.store(key, value, ttl)

    async def _handle_find_value(self, message: Message, writer: asyncio.StreamReader = None):
        key = message.payload.get("key")
        value = self.dht.get(key)

        closest = []
        if value is None:
            closest = self.dht.find_closest_peers(key)

        response = Message(
            type=MessageType.FIND_VALUE_RESPONSE,
            sender_id=self.node_id,
            payload={
                "key": key,
                "value": value,
                "closest": [p.to_dict() for p in closest],
            },
            message_id=message.message_id,
        )

        if writer:
            writer.write(response.to_bytes())
            await writer.drain()

    async def _handle_find_value_response(
        self, message: Message, writer: asyncio.StreamReader = None
    ):
        key = message.payload.get("key")
        value = message.payload.get("value")
        closest = message.payload.get("closest", [])

        if value is not None:
            self.dht.store(key, value, ttl=300)

        if closest:
            for peer_data in closest:
                try:
                    peer = PeerInfo.from_dict(peer_data)
                    if peer.node_id != self.node_id:
                        self.dht.add_peer(peer)
                except Exception:
                    pass

    async def _handle_gossip(self, message: Message, writer: asyncio.StreamReader = None):
        await self.gossip.handle_message(
            message,
            send_func=self._send_to_peer,
        )

    async def _handle_peer_announce(self, message: Message, writer: asyncio.StreamReader = None):
        peer_data = message.payload.get("peer")
        if peer_data:
            peer = PeerInfo.from_dict(peer_data)
            if peer.node_id != self.node_id:
                self.dht.add_peer(peer)
                self._peers[peer.node_id] = peer

    async def _handle_peer_disconnect(self, message: Message, writer: asyncio.StreamReader = None):
        peer_id = message.sender_id
        if peer_id in self._peers:
            del self._peers[peer_id]
        self.dht.remove_peer(peer_id)

    async def _send_to_peer(self, peer: PeerInfo, message: Message) -> bool:
        try:
            reader, writer = await asyncio.open_connection(peer.ip, peer.port)
            writer.write(message.to_bytes())
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            if peer.node_id in self._peers:
                self._peers[peer.node_id].state = PeerState.OFFLINE
            return False

    async def _bootstrap(self):
        for ip, port in self.bootstrap_nodes:
            try:
                message = Message(
                    type=MessageType.FIND_NODE,
                    sender_id=self.node_id,
                    payload={"target_id": self.node_id},
                )

                reader, writer = await asyncio.open_connection(ip, port)
                writer.write(message.to_bytes())
                await writer.drain()

                data = await reader.read(65536)
                if data:
                    response = Message.from_bytes(data)
                    await self._process_message(response)

                writer.close()
                await writer.wait_closed()

            except Exception as e:
                print(f"[P2P] Bootstrap failed for {ip}:{port}: {e}")

    async def _run_heartbeat_loop(self):
        while self._running:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

            for _peer_id, peer in list(self._peers.items()):
                if time.time() - peer.last_seen > self.HEARTBEAT_TIMEOUT:
                    peer.state = PeerState.OFFLINE
                else:
                    await self._send_to_peer(
                        peer,
                        Message(
                            type=MessageType.PING,
                            sender_id=self.node_id,
                        ),
                    )

    async def _run_discovery_loop(self):
        while self._running:
            await asyncio.sleep(self.DISCOVERY_INTERVAL)

            closest = self.dht.find_closest_peers(self.node_id)
            for peer in closest[:3]:
                await self._send_to_peer(
                    peer,
                    Message(
                        type=MessageType.FIND_NODE,
                        sender_id=self.node_id,
                        payload={"target_id": self.node_id},
                    ),
                )

    async def _run_cleanup_loop(self):
        while self._running:
            await asyncio.sleep(60)

            offline_peers = [
                peer_id for peer_id, peer in self._peers.items() if peer.state == PeerState.OFFLINE
            ]

            for peer_id in offline_peers:
                del self._peers[peer_id]
                self.dht.remove_peer(peer_id)

            self.gossip._cleanup_cache()

    async def broadcast(self, topic: str, data: dict[str, Any]) -> int:
        return await self.gossip.broadcast(
            topic=topic,
            data=data,
            send_func=self._send_to_peer,
        )

    async def store_value(self, key: str, value: Any, ttl: int = 3600) -> bool:
        closest = self.dht.find_closest_peers(key)

        for peer in closest[: self.dht.K]:
            await self._send_to_peer(
                peer,
                Message(
                    type=MessageType.STORE,
                    sender_id=self.node_id,
                    payload={"key": key, "value": value, "ttl": ttl},
                ),
            )

        self.dht.store(key, value, ttl)
        return True

    async def get_value(self, key: str) -> Optional[Any]:
        local_value = self.dht.get(key)
        if local_value is not None:
            return local_value

        closest = self.dht.find_closest_peers(key)

        for peer in closest[: self.dht.ALPHA]:
            try:
                reader, writer = await asyncio.open_connection(peer.ip, peer.port)

                message = Message(
                    type=MessageType.FIND_VALUE,
                    sender_id=self.node_id,
                    payload={"key": key},
                )
                writer.write(message.to_bytes())
                await writer.drain()

                data = await reader.read(65536)
                if data:
                    response = Message.from_bytes(data)
                    value = response.payload.get("value")
                    if value is not None:
                        writer.close()
                        await writer.wait_closed()
                        return value

                writer.close()
                await writer.wait_closed()

            except Exception:
                pass

        return None

    def get_stats(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "port": self.port,
            "running": self._running,
            "uptime": time.time() - self._start_time,
            "peers": len(self._peers),
            "online_peers": sum(1 for p in self._peers.values() if p.state == PeerState.ONLINE),
            "dht": self.dht.get_stats(),
            "gossip": self.gossip.get_stats(),
            "nat": self.nat.get_stats(),
            "capabilities": self.capabilities,
        }


__all__ = [
    "MessageType",
    "NATType",
    "PeerState",
    "PeerInfo",
    "Message",
    "KademliaDHT",
    "GossipProtocol",
    "NATTraversal",
    "P2PNode",
]
