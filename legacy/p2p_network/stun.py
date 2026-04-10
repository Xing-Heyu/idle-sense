"""
STUN Protocol Implementation for NAT Traversal.

Implements RFC 5389 - Session Traversal Utilities for NAT
with NAT type detection following RFC 3489.

References:
- RFC 5389: https://tools.ietf.org/html/rfc5389
- RFC 3489: https://tools.ietf.org/html/rfc3489 (Classic STUN)
"""

import asyncio
import binascii
import secrets
import socket
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class STUNMessageClass(IntEnum):
    REQUEST = 0x0001
    INDICATION = 0x0011
    SUCCESS_RESPONSE = 0x0101
    ERROR_RESPONSE = 0x0111


class STUNAttributeType(IntEnum):
    MAPPED_ADDRESS = 0x0001
    RESPONSE_ADDRESS = 0x0002
    CHANGE_REQUEST = 0x0003
    SOURCE_ADDRESS = 0x0004
    CHANGED_ADDRESS = 0x0005
    USERNAME = 0x0006
    PASSWORD = 0x0007
    MESSAGE_INTEGRITY = 0x0008
    ERROR_CODE = 0x0009
    UNKNOWN_ATTRIBUTES = 0x000A
    REFLECTED_FROM = 0x000B
    REALM = 0x0014
    NONCE = 0x0015
    XOR_MAPPED_ADDRESS = 0x0020
    SOFTWARE = 0x8022
    ALTERNATE_SERVER = 0x8023
    FINGERPRINT = 0x8028


class NATType(IntEnum):
    UNKNOWN = 0
    PUBLIC = 1
    FULL_CONE = 2
    RESTRICTED_CONE = 3
    PORT_RESTRICTED = 4
    SYMMETRIC = 5
    BLOCKED = 6
    UDP_BLOCKED = 7


@dataclass
class STUNAttribute:
    """STUN attribute."""

    type: int
    value: bytes

    def to_bytes(self) -> bytes:
        length = len(self.value)
        padding = (4 - (length % 4)) % 4
        return struct.pack("!HH", self.type, length) + self.value + b"\x00" * padding

    @classmethod
    def mapped_address(cls, ip: str, port: int, family: int = 1) -> "STUNAttribute":
        """Create a MAPPED-ADDRESS attribute."""
        ip_bytes = socket.inet_pton(socket.AF_INET if family == 1 else socket.AF_INET6, ip)
        value = struct.pack("!BBH", 0, family, port) + ip_bytes
        return cls(STUNAttributeType.MAPPED_ADDRESS, value)

    @classmethod
    def xor_mapped_address(
        cls, ip: str, port: int, _transaction_id: bytes, magic_cookie: int = 0x2112A442
    ) -> "STUNAttribute":
        """Create a XOR-MAPPED-ADDRESS attribute."""
        ip_bytes = socket.inet_pton(socket.AF_INET, ip)
        family = 1

        xor_port = port ^ (magic_cookie >> 16)
        xor_ip = bytes(a ^ b for a, b in zip(ip_bytes, struct.pack("!I", magic_cookie)))

        value = struct.pack("!BBH", 0, family, xor_port) + xor_ip
        return cls(STUNAttributeType.XOR_MAPPED_ADDRESS, value)

    @classmethod
    def change_request(cls, change_ip: bool = False, change_port: bool = False) -> "STUNAttribute":
        """Create a CHANGE-REQUEST attribute."""
        flags = (0x02 if change_ip else 0) | (0x04 if change_port else 0)
        value = struct.pack("!I", flags)
        return cls(STUNAttributeType.CHANGE_REQUEST, value)

    @classmethod
    def software(cls, name: str = "Idle-Sense STUN") -> "STUNAttribute":
        """Create a SOFTWARE attribute."""
        return cls(STUNAttributeType.SOFTWARE, name.encode())

    @classmethod
    def fingerprint(cls, message: bytes) -> "STUNAttribute":
        """Create a FINGERPRINT attribute."""
        crc = binascii.crc32(message) ^ 0x5354554E
        return cls(STUNAttributeType.FINGERPRINT, struct.pack("!I", crc))


@dataclass
class STUNMessage:
    """STUN message."""

    message_class: int
    method: int = 0x0001
    transaction_id: bytes = field(default_factory=lambda: secrets.token_bytes(12))
    attributes: list[STUNAttribute] = field(default_factory=list)
    magic_cookie: int = 0x2112A442

    def to_bytes(self) -> bytes:
        message_type = (self.method << 4) | self.message_class
        header = struct.pack("!HHI", message_type, 0, self.magic_cookie) + self.transaction_id

        attr_bytes = b""
        for attr in self.attributes:
            attr_bytes += attr.to_bytes()

        header = (
            struct.pack("!HHI", message_type, len(attr_bytes), self.magic_cookie)
            + self.transaction_id
        )

        return header + attr_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional["STUNMessage"]:
        """Parse a STUN message from bytes."""
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

            attributes = []
            offset = 20
            while offset + 4 <= len(data) and offset < 20 + length:
                attr_type, attr_length = struct.unpack("!HH", data[offset : offset + 4])
                offset += 4

                if offset + attr_length > len(data):
                    break

                attr_value = data[offset : offset + attr_length]
                attributes.append(STUNAttribute(attr_type, attr_value))

                padding = (4 - (attr_length % 4)) % 4
                offset += attr_length + padding

            return cls(
                message_class=message_class,
                method=method,
                transaction_id=transaction_id,
                attributes=attributes,
                magic_cookie=magic_cookie,
            )
        except Exception:
            return None

    def get_attribute(self, attr_type: int) -> Optional[STUNAttribute]:
        """Get an attribute by type."""
        for attr in self.attributes:
            if attr.type == attr_type:
                return attr
        return None

    def get_mapped_address(self) -> Optional[tuple[str, int]]:
        """Extract the mapped address from XOR-MAPPED-ADDRESS or MAPPED-ADDRESS."""
        xor_attr = self.get_attribute(STUNAttributeType.XOR_MAPPED_ADDRESS)
        if xor_attr:
            return self._parse_xor_mapped_address(xor_attr.value)

        mapped_attr = self.get_attribute(STUNAttributeType.MAPPED_ADDRESS)
        if mapped_attr:
            return self._parse_mapped_address(mapped_attr.value)

        return None

    def _parse_mapped_address(self, value: bytes) -> Optional[tuple[str, int]]:
        """Parse MAPPED-ADDRESS attribute value."""
        if len(value) < 8:
            return None

        _, family, port = struct.unpack("!BBH", value[:4])
        ip_bytes = value[4:8] if family == 1 else value[4:20]

        try:
            af = socket.AF_INET if family == 1 else socket.AF_INET6
            ip = socket.inet_ntop(af, ip_bytes)
            return ip, port
        except Exception:
            return None

    def _parse_xor_mapped_address(self, value: bytes) -> Optional[tuple[str, int]]:
        """Parse XOR-MAPPED-ADDRESS attribute value."""
        if len(value) < 8:
            return None

        _, family, xor_port = struct.unpack("!BBH", value[:4])
        xor_ip_bytes = value[4:8] if family == 1 else value[4:20]

        port = xor_port ^ (self.magic_cookie >> 16)

        magic_bytes = struct.pack("!I", self.magic_cookie)
        ip_bytes = bytes(a ^ b for a, b in zip(xor_ip_bytes, magic_bytes))

        try:
            ip = socket.inet_ntop(socket.AF_INET, ip_bytes)
            return ip, port
        except Exception:
            return None


class STUNClient:
    """STUN client for NAT traversal."""

    STUN_SERVERS = [
        ("stun.l.google.com", 19302),
        ("stun1.l.google.com", 19302),
        ("stun2.l.google.com", 19302),
        ("stun3.l.google.com", 19302),
        ("stun4.l.google.com", 19302),
        ("stun.cloudflare.com", 3478),
        ("stun.stunprotocol.org", 3478),
    ]

    DEFAULT_TIMEOUT = 5.0

    def __init__(self, local_port: int = 0):
        self.local_port = local_port
        self.socket: Optional[socket.socket] = None
        self.nat_type = NATType.UNKNOWN
        self.external_ip: Optional[str] = None
        self.external_port: Optional[int] = None

    async def discover_nat_type(self) -> NATType:
        """
        Discover NAT type using RFC 3489 algorithm.

        Test flow:
        1. Test I: Get mapped address from primary STUN server
        2. Test II: Send change request to different IP and port
        3. Test I(II): Get mapped address from secondary STUN server
        4. Test III: Send change request to different port only

        Returns:
            NATType enum value
        """
        try:
            if not self.STUN_SERVERS:
                return NATType.UNKNOWN

            primary_server = self.STUN_SERVERS[0]

            result1 = await self._send_binding_request(primary_server)
            if not result1:
                return NATType.UDP_BLOCKED

            mapped_addr1 = result1.get_mapped_address()
            if not mapped_addr1:
                return NATType.UNKNOWN

            self.external_ip, self.external_port = mapped_addr1

            local_ip = self._get_local_ip()
            if mapped_addr1[0] == local_ip:
                self.nat_type = NATType.PUBLIC
                return NATType.PUBLIC

            result2 = await self._send_binding_request(
                primary_server, change_ip=True, change_port=True
            )

            if result2:
                self.nat_type = NATType.FULL_CONE
                return NATType.FULL_CONE

            if len(self.STUN_SERVERS) < 2:
                return NATType.UNKNOWN

            secondary_server = self.STUN_SERVERS[1]
            result3 = await self._send_binding_request(secondary_server)

            if not result3:
                return NATType.UNKNOWN

            mapped_addr2 = result3.get_mapped_address()

            if mapped_addr1[1] == mapped_addr2[1]:
                result4 = await self._send_binding_request(
                    primary_server, change_ip=False, change_port=True
                )

                if result4:
                    self.nat_type = NATType.RESTRICTED_CONE
                    return NATType.RESTRICTED_CONE
                else:
                    self.nat_type = NATType.PORT_RESTRICTED
                    return NATType.PORT_RESTRICTED
            else:
                self.nat_type = NATType.SYMMETRIC
                return NATType.SYMMETRIC

        except Exception:
            return NATType.UNKNOWN

    async def _send_binding_request(
        self,
        server: tuple[str, int],
        change_ip: bool = False,
        change_port: bool = False,
        timeout: float = None,
    ) -> Optional[STUNMessage]:
        """Send a STUN binding request and receive response."""
        timeout = timeout or self.DEFAULT_TIMEOUT

        request = STUNMessage(
            message_class=STUNMessageClass.REQUEST,
            method=0x0001,
            attributes=[
                STUNAttribute.software(),
            ],
        )

        if change_ip or change_port:
            request.attributes.append(STUNAttribute.change_request(change_ip, change_port))

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.local_port or 0))
            sock.setblocking(False)

            if self.local_port == 0:
                self.local_port = sock.getsockname()[1]

            loop = asyncio.get_event_loop()

            await loop.sock_sendto(sock, request.to_bytes(), server)

            try:
                data, addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 4096), timeout=timeout)

                response = STUNMessage.from_bytes(data)

                if response and response.transaction_id == request.transaction_id:
                    return response

            except asyncio.TimeoutError:
                return None
            finally:
                sock.close()

        except Exception:
            return None

        return None

    async def get_external_address(self) -> Optional[tuple[str, int]]:
        """Get the external IP and port mapping."""
        if self.external_ip and self.external_port:
            return self.external_ip, self.external_port

        for server in self.STUN_SERVERS:
            result = await self._send_binding_request(server)
            if result:
                mapped_addr = result.get_mapped_address()
                if mapped_addr:
                    self.external_ip, self.external_port = mapped_addr
                    return mapped_addr

        return None

    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"

    def get_stats(self) -> dict[str, Any]:
        """Get STUN client statistics."""
        return {
            "nat_type": self.nat_type.name,
            "external_ip": self.external_ip,
            "external_port": self.external_port,
            "local_ip": self._get_local_ip(),
            "local_port": self.local_port,
        }


class STUNServer:
    """Simple STUN server implementation."""

    def __init__(self, host: str = "0.0.0.0", port: int = 3478):
        self.host = host
        self.port = port
        self.running = False
        self.socket: Optional[socket.socket] = None

    async def start(self):
        """Start the STUN server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.setblocking(False)
        self.running = True

        loop = asyncio.get_event_loop()

        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(self.socket, 4096)
                await self._handle_request(data, addr)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[STUN Server] Error: {e}")

    async def stop(self):
        """Stop the STUN server."""
        self.running = False
        if self.socket:
            self.socket.close()

    async def _handle_request(self, data: bytes, addr: tuple[str, int]):
        """Handle a STUN request."""
        request = STUNMessage.from_bytes(data)

        if not request:
            return

        if request.message_class == STUNMessageClass.REQUEST and request.method == 0x0001:
            response = STUNMessage(
                message_class=STUNMessageClass.SUCCESS_RESPONSE,
                method=0x0001,
                transaction_id=request.transaction_id,
                attributes=[
                    STUNAttribute.xor_mapped_address(addr[0], addr[1], request.transaction_id),
                    STUNAttribute.software(),
                ],
            )

            await asyncio.get_event_loop().sock_sendto(self.socket, response.to_bytes(), addr)


__all__ = [
    "STUNMessageClass",
    "STUNAttributeType",
    "NATType",
    "STUNAttribute",
    "STUNMessage",
    "STUNClient",
    "STUNServer",
]
