"""
IPv6 Support Module for P2P Network.

Implements IPv6 support including:
- Dual-stack (IPv4/IPv6) support
- IPv6 address parsing and validation
- IPv6 socket operations
- Address preference selection

References:
- RFC 4291: IPv6 Address Architecture
- RFC 3493: IPv6 Default Address Selection
"""

import ipaddress
import socket
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AddressFamily(Enum):
    IPv4 = "IPv4"
    IPv6 = "IPv6"
    DUAL_STACK = "dual_stack"


class AddressPreference(Enum):
    IPv4_ONLY = "ipv4_only"
    IPv6_ONLY = "ipv6_only"
    IPv6_PREFERRED = "ipv6_preferred"
    IPv4_PREFERRED = "ipv4_preferred"
    DUAL_STACK = "dual_stack"


@dataclass
class IPAddress:
    """Represents an IP address (IPv4 or IPv6)."""
    address: str
    port: int
    family: AddressFamily

    @property
    def is_ipv6(self) -> bool:
        return self.family == AddressFamily.IPv6

    @property
    def is_ipv4(self) -> bool:
        return self.family == AddressFamily.IPv4

    @property
    def is_loopback(self) -> bool:
        try:
            addr = ipaddress.ip_address(self.address)
            return addr.is_loopback
        except ValueError:
            return False

    @property
    def is_private(self) -> bool:
        try:
            addr = ipaddress.ip_address(self.address)
            return addr.is_private
        except ValueError:
            return False

    @property
    def is_link_local(self) -> bool:
        try:
            addr = ipaddress.ip_address(self.address)
            return addr.is_link_local
        except ValueError:
            return False

    @property
    def is_global(self) -> bool:
        try:
            addr = ipaddress.ip_address(self.address)
            return addr.is_global
        except ValueError:
            return False

    def to_tuple(self) -> tuple[str, int]:
        return (self.address, self.port)

    def __str__(self) -> str:
        if self.is_ipv6:
            return f"[{self.address}]:{self.port}"
        return f"{self.address}:{self.port}"

    @classmethod
    def from_string(cls, addr_str: str) -> "IPAddress":
        """Parse address from string."""
        if ":" in addr_str:
            if addr_str.startswith("["):
                end = addr_str.rfind("]")
                if end > 0:
                    ip = addr_str[1:end]
                    port = int(addr_str[end + 2:])
                    return cls(
                        address=ip,
                        port=port,
                        family=AddressFamily.IPv6
                    )
            else:
                parts = addr_str.rsplit(":", 1)
                if len(parts) == 2:
                    return cls(
                        address=parts[0],
                        port=int(parts[1]),
                        family=AddressFamily.IPv4
                    )
        raise ValueError(f"Invalid address format: {addr_str}")


class IPv6Support:
    """
    IPv6 support utilities.
    
    Features:
    - IPv6 address validation
    - Dual-stack socket creation
    - Address preference selection
    """

    def __init__(self, preference: AddressPreference = AddressPreference.DUAL_STACK):
        self.preference = preference
        self._ipv6_available = self._check_ipv6_support()

    @staticmethod
    def _check_ipv6_support() -> bool:
        """Check if IPv6 is supported on this system."""
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.close()
            return True
        except OSError:
            return False

    @property
    def is_ipv6_available(self) -> bool:
        return self._ipv6_available

    def validate_address(self, address: str) -> Optional[AddressFamily]:
        """Validate an IP address and return its family."""
        try:
            addr = ipaddress.ip_address(address)
            if isinstance(addr, ipaddress.IPv4Address):
                return AddressFamily.IPv4
            elif isinstance(addr, ipaddress.IPv6Address):
                return AddressFamily.IPv6
        except ValueError:
            return None

    def is_valid_ipv6(self, address: str) -> bool:
        """Check if address is a valid IPv6 address."""
        try:
            ipaddress.IPv6Address(address)
            return True
        except ValueError:
            return False

    def normalize_ipv6(self, address: str) -> str:
        """Normalize an IPv6 address."""
        try:
            addr = ipaddress.IPv6Address(address)
            return str(addr)
        except ValueError:
            return address

    def get_address_type(self, address: str) -> str:
        """Get the type of an IPv6 address."""
        try:
            addr = ipaddress.IPv6Address(address)
            if addr.is_loopback:
                return "loopback"
            elif addr.is_link_local:
                return "link_local"
            elif addr.is_private:
                return "private"
            elif addr.is_multicast:
                return "multicast"
            elif addr.is_global:
                return "global"
            else:
                return "other"
        except ValueError:
            return "invalid"

    def create_socket(
        self,
        family: AddressFamily = None,
        sock_type: int = socket.SOCK_STREAM
    ) -> Optional[socket.socket]:
        """Create a socket with the appropriate address family."""
        if family is None:
            family = self._get_preferred_family()

        if family == AddressFamily.IPv6 and not self._ipv6_available:
            family = AddressFamily.IPv4

        addr_family = socket.AF_INET6 if family == AddressFamily.IPv6 else socket.AF_INET

        try:
            sock = socket.socket(addr_family, sock_type)
            if family == AddressFamily.IPv6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            return sock
        except OSError:
            return None

    def create_dual_stack_socket(
        self,
        port: int = 0,
        sock_type: int = socket.SOCK_STREAM
    ) -> Optional[socket.socket]:
        """Create a dual-stack socket that handles both IPv4 and IPv6."""
        if not self._ipv6_available:
            return self.create_socket(AddressFamily.IPv4, sock_type)

        try:
            sock = socket.socket(socket.AF_INET6, sock_type)
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("::", port))
            return sock
        except OSError:
            return self.create_socket(AddressFamily.IPv4, sock_type)

    def _get_preferred_family(self) -> AddressFamily:
        """Get the preferred address family based on preference."""
        if self.preference == AddressPreference.IPv4_ONLY:
            return AddressFamily.IPv4
        elif self.preference == AddressPreference.IPv6_ONLY or self.preference == AddressPreference.IPv6_PREFERRED:
            return AddressFamily.IPv6 if self._ipv6_available else AddressFamily.IPv4
        elif self.preference == AddressPreference.IPv4_PREFERRED:
            return AddressFamily.IPv4
        else:
            return AddressFamily.IPv6 if self._ipv6_available else AddressFamily.IPv4

    def resolve_hostname(
        self,
        hostname: str,
        port: int = 0
    ) -> list[IPAddress]:
        """Resolve a hostname to IP addresses."""
        addresses = []

        try:
            infos = socket.getaddrinfo(
                hostname,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM
            )

            for family, _, _, _, sockaddr in infos:
                if family == socket.AF_INET:
                    addresses.append(IPAddress(
                        address=sockaddr[0],
                        port=sockaddr[1],
                        family=AddressFamily.IPv4
                    ))
                elif family == socket.AF_INET6:
                    addresses.append(IPAddress(
                        address=sockaddr[0],
                        port=sockaddr[1],
                        family=AddressFamily.IPv6
                    ))
        except socket.gaierror:
            pass

        return self._sort_by_preference(addresses)

    def _sort_by_preference(self, addresses: list[IPAddress]) -> list[IPAddress]:
        """Sort addresses by preference."""
        if not addresses:
            return addresses

        ipv4_addrs = [a for a in addresses if a.is_ipv4]
        ipv6_addrs = [a for a in addresses if a.is_ipv6]

        if self.preference == AddressPreference.IPv6_PREFERRED:
            return ipv6_addrs + ipv4_addrs
        elif self.preference == AddressPreference.IPv4_PREFERRED:
            return ipv4_addrs + ipv6_addrs
        elif self.preference == AddressPreference.IPv4_ONLY:
            return ipv4_addrs
        elif self.preference == AddressPreference.IPv6_ONLY:
            return ipv6_addrs
        else:
            return ipv6_addrs + ipv4_addrs

    def get_local_addresses(self) -> list[IPAddress]:
        """Get all local IP addresses."""
        addresses = []

        try:
            hostname = socket.gethostname()
            infos = socket.getaddrinfo(
                hostname,
                None,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM
            )

            for family, _, _, _, sockaddr in infos:
                if family == socket.AF_INET:
                    addresses.append(IPAddress(
                        address=sockaddr[0],
                        port=0,
                        family=AddressFamily.IPv4
                    ))
                elif family == socket.AF_INET6:
                    addresses.append(IPAddress(
                        address=sockaddr[0],
                        port=0,
                        family=AddressFamily.IPv6
                    ))
        except socket.gaierror:
            pass

        return addresses

    def get_best_address(self, target: str = None) -> Optional[IPAddress]:
        """Get the best local address for connecting to a target."""
        local_addrs = self.get_local_addresses()

        if target:
            target_addrs = self.resolve_hostname(target)
            if target_addrs:
                target_family = target_addrs[0].family
                for addr in local_addrs:
                    if addr.family == target_family:
                        return addr

        sorted_addrs = self._sort_by_preference(local_addrs)
        return sorted_addrs[0] if sorted_addrs else None


__all__ = [
    "AddressFamily",
    "AddressPreference",
    "IPAddress",
    "IPv6Support",
]
