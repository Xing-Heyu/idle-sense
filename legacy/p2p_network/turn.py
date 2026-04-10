"""
TURN Protocol Implementation - TURN Relay Server for NAT Traversal.

Implements RFC 5766 - TURN protocol for NAT traversal when
direct peer-to-peer communication is not possible.
"""

import secrets
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class TURNMethod(IntEnum):
    ALLOCATE = 0x0003
    REFRESH = 0x0004
    SEND = 0x0006
    DATA = 0x0007
    CREATE_PERMISSION = 0x0008
    CHANNEL_BIND = 0x0009


class TURNAttributeType(IntEnum):
    CHANNEL_NUMBER = 0x000C
    LIFETIME = 0x000D
    XOR_PEER_ADDRESS = 0x0012
    DATA = 0x0013
    XOR_RELAYED_ADDRESS = 0x0016
    REQUESTED_TRANSPORT = 0x0019
    XOR_MAPPED_ADDRESS = 0x0020
    SOFTWARE = 0x8022


class AllocationState(IntEnum):
    PENDING = 0
    ACTIVE = 1
    EXPIRED = 2
    DELETED = 3


@dataclass
class TURNAllocation:
    """Represents a TURN allocation."""

    allocation_id: str
    client_address: tuple[str, int]
    relayed_address: tuple[str, int]
    lifetime: int = 600
    created_at: float = field(default_factory=time.time)
    state: AllocationState = AllocationState.PENDING
    permissions: dict[str, float] = field(default_factory=dict)
    channels: dict[int, tuple[str, int]] = field(default_factory=dict)

    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.lifetime

    def time_remaining(self) -> int:
        return max(0, int(self.created_at + self.lifetime - time.time()))

    def has_permission(self, peer_address: tuple[str, int]) -> bool:
        key = f"{peer_address[0]}:{peer_address[1]}"
        if key not in self.permissions:
            return False
        if time.time() > self.permissions[key]:
            del self.permissions[key]
            return False
        return True

    def add_permission(self, peer_address: tuple[str, int], lifetime: int = 300):
        key = f"{peer_address[0]}:{peer_address[1]}"
        self.permissions[key] = time.time() + lifetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "client_address": self.client_address,
            "relayed_address": self.relayed_address,
            "lifetime": self.lifetime,
            "time_remaining": self.time_remaining(),
            "state": self.state.name,
            "permissions": len(self.permissions),
            "channels": len(self.channels),
        }


@dataclass
class TURNMessage:
    """TURN message structure."""

    method: int
    message_class: int
    transaction_id: bytes
    attributes: dict[int, bytes] = field(default_factory=dict)
    magic_cookie: int = 0x2112A442

    def to_bytes(self) -> bytes:
        message_type = (self.method << 4) | self.message_class

        attr_bytes = b""
        for attr_type, attr_value in self.attributes.items():
            length = len(attr_value)
            padding = (4 - (length % 4)) % 4
            attr_bytes += struct.pack("!HH", attr_type, length) + attr_value + b"\x00" * padding

        header = struct.pack("!HHI", message_type, len(attr_bytes), self.magic_cookie)
        header += self.transaction_id

        return header + attr_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional["TURNMessage"]:
        if len(data) < 20:
            return None

        try:
            message_type, length, magic_cookie = struct.unpack("!HHI", data[:8])
            transaction_id = data[8:20]

            if magic_cookie != 0x2112A442:
                return None

            message_class = message_type & 0x0111
            method = (
                (message_type & 0x3E00) >> 2
                | (message_type & 0x00E0) >> 1
                | (message_type & 0x000F)
            )

            attributes = {}
            offset = 20
            while offset + 4 <= len(data) and offset < 20 + length:
                attr_type, attr_length = struct.unpack("!HH", data[offset : offset + 4])
                offset += 4

                if offset + attr_length > len(data):
                    break

                attributes[attr_type] = data[offset : offset + attr_length]

                padding = (4 - (attr_length % 4)) % 4
                offset += attr_length + padding

            return cls(
                method=method,
                message_class=message_class,
                transaction_id=transaction_id,
                attributes=attributes,
                magic_cookie=magic_cookie,
            )
        except Exception:
            return None

    def get_attribute(self, attr_type: int) -> Optional[bytes]:
        return self.attributes.get(attr_type)

    def set_attribute(self, attr_type: int, value: bytes):
        self.attributes[attr_type] = value


class TURNAttribute:
    """Helper class for TURN attributes."""

    @staticmethod
    def lifetime(seconds: int) -> bytes:
        """Create LIFETIME attribute value."""
        return struct.pack("!I", seconds)

    @staticmethod
    def parse_lifetime(data: bytes) -> int:
        """Parse LIFETIME attribute value."""
        if len(data) < 4:
            return 0
        return struct.unpack("!I", data[:4])[0]

    @staticmethod
    def channel_number(channel: int) -> bytes:
        """Create CHANNEL-NUMBER attribute value."""
        return struct.pack("!HH", channel, 0)

    @staticmethod
    def parse_channel_number(data: bytes) -> int:
        """Parse CHANNEL-NUMBER attribute value."""
        if len(data) < 4:
            return 0
        return struct.unpack("!H", data[:2])[0]

    @staticmethod
    def xor_address(
        ip: str, port: int, transaction_id: bytes, magic_cookie: int = 0x2112A442
    ) -> bytes:
        """Create XOR-MAPPED-ADDRESS or XOR-PEER-ADDRESS attribute value."""
        try:
            ip_bytes = socket.inet_pton(socket.AF_INET, ip)
            family = 1
        except OSError:
            ip_bytes = socket.inet_pton(socket.AF_INET6, ip)
            family = 2

        xor_port = port ^ (magic_cookie >> 16)

        xor_key = struct.pack("!I", magic_cookie) + transaction_id
        xor_ip = bytes(a ^ b for a, b in zip(ip_bytes, xor_key[: len(ip_bytes)]))

        return struct.pack("!BBH", 0, family, xor_port) + xor_ip

    @staticmethod
    def parse_xor_address(
        data: bytes, transaction_id: bytes, magic_cookie: int = 0x2112A442
    ) -> Optional[tuple[str, int]]:
        """Parse XOR address from attribute value."""
        if len(data) < 4:
            return None

        try:
            family = data[1]
            xor_port = struct.unpack("!H", data[2:4])[0]
            port = xor_port ^ (magic_cookie >> 16)

            if family == 1:
                if len(data) < 8:
                    return None
                xor_ip = data[4:8]
                xor_key = struct.pack("!I", magic_cookie) + transaction_id
                ip_bytes = bytes(a ^ b for a, b in zip(xor_ip, xor_key[:4]))
                ip = socket.inet_ntop(socket.AF_INET, ip_bytes)
            else:
                if len(data) < 20:
                    return None
                xor_ip = data[4:20]
                xor_key = struct.pack("!I", magic_cookie) + transaction_id
                ip_bytes = bytes(a ^ b for a, b in zip(xor_ip, xor_key[:16]))
                ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)

            return ip, port
        except Exception:
            return None


class TURNServer:
    """TURN Relay Server implementation."""

    DEFAULT_PORT = 3478
    DEFAULT_LIFETIME = 600
    MAX_ALLOCATIONS = 1000
    CHANNEL_BASE = 0x4000

    def __init__(self, host: str = "0.0.0.0", port: int = None):
        self.host = host
        self.port = port or self.DEFAULT_PORT

        self.allocations: dict[str, TURNAllocation] = {}
        self.client_allocations: dict[tuple[str, int], str] = {}

        self._running = False
        self._socket: Optional[socket.socket] = None
        self._relay_ports: dict[str, socket.socket] = {}

        self._stats = {
            "total_allocations": 0,
            "active_allocations": 0,
            "total_bytes_relayed": 0,
            "permissions_granted": 0,
            "channels_bound": 0,
        }

    async def start(self):
        """Start the TURN server."""
        self._running = True

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.setblocking(False)

        print(f"[TURN] Server started on {self.host}:{self.port}")

    async def stop(self):
        """Stop the TURN server."""
        self._running = False

        for sock in self._relay_ports.values():
            sock.close()
        self._relay_ports.clear()

        if self._socket:
            self._socket.close()

        print("[TURN] Server stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get server statistics."""
        return {
            **self._stats,
            "running": self._running,
            "port": self.port,
        }


class TURNClient:
    """TURN Client for NAT traversal with relay support."""

    DEFAULT_LIFETIME = 600

    STUN_SERVERS = [
        ("stun.l.google.com", 19302),
        ("stun1.l.google.com", 19302),
    ]

    def __init__(self, server_host: str, server_port: int = 3478):
        self.server_host = server_host
        self.server_port = server_port

        self._socket: Optional[socket.socket] = None
        self._allocation: Optional[TURNAllocation] = None
        self._transaction_id: Optional[bytes] = None

    async def allocate(self, lifetime: int = None) -> Optional[tuple[str, int]]:
        """Allocate a relay address."""
        if self._allocation and not self._allocation.is_expired():
            return self._allocation.relayed_address

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)

        self._transaction_id = secrets.token_bytes(12)

        return None

    def get_relayed_address(self) -> Optional[tuple[str, int]]:
        """Get the relayed address."""
        if self._allocation and not self._allocation.is_expired():
            return self._allocation.relayed_address
        return None

    def close(self):
        """Close the client."""
        if self._socket:
            self._socket.close()
            self._socket = None
        self._allocation = None


__all__ = [
    "TURNMethod",
    "TURNAttributeType",
    "AllocationState",
    "TURNAllocation",
    "TURNMessage",
    "TURNAttribute",
    "TURNServer",
    "TURNClient",
]
