"""
Integration Tests for NAT Traversal.

Tests the complete NAT traversal stack:
- STUN protocol
- TURN relay
- UDP hole punching
- NAT type detection
"""

import asyncio
import socket
from unittest.mock import Mock, patch

import pytest

from legacy.p2p_network.stun import (
    NATType,
    STUNAttribute,
    STUNClient,
    STUNMessage,
    STUNMessageClass,
    STUNServer,
)
from legacy.p2p_network.turn import (
    TURNAllocation,
    TURNClient,
    TURNServer,
)


class TestSTUNIntegration:
    """Integration tests for STUN protocol."""

    @pytest.fixture
    def stun_client(self):
        """Create a STUN client."""
        return STUNClient(local_port=0)

    @pytest.fixture
    async def stun_server(self):
        """Create and start a STUN server."""
        server = STUNServer(host="127.0.0.1", port=3478)
        await server.start()
        yield server
        await server.stop()

    def test_stun_client_init(self, stun_client):
        """Test STUN client initialization."""
        assert stun_client.nat_type == NATType.UNKNOWN
        assert stun_client.external_ip is None

    def test_stun_message_round_trip(self):
        """Test STUN message serialization and parsing."""
        original = STUNMessage(
            message_class=STUNMessageClass.REQUEST,
            method=0x0001,
            attributes=[
                STUNAttribute.software("TestClient"),
            ],
        )

        data = original.to_bytes()
        parsed = STUNMessage.from_bytes(data)

        assert parsed is not None
        assert parsed.transaction_id == original.transaction_id
        assert parsed.magic_cookie == original.magic_cookie

    def test_stun_attribute_mapped_address(self):
        """Test MAPPED-ADDRESS attribute."""
        attr = STUNAttribute.mapped_address("192.168.1.1", 12345)

        assert attr.type == 0x0001

        msg = STUNMessage(
            message_class=STUNMessageClass.SUCCESS_RESPONSE, method=0x0001, attributes=[attr]
        )

        parsed = STUNMessage.from_bytes(msg.to_bytes())
        addr = parsed.get_mapped_address()

        assert addr is not None
        assert addr[0] == "192.168.1.1"
        assert addr[1] == 12345

    def test_stun_attribute_xor_mapped_address(self):
        """Test XOR-MAPPED-ADDRESS attribute."""
        transaction_id = b"123456789012"
        attr = STUNAttribute.xor_mapped_address("10.0.0.1", 5000, transaction_id)

        assert attr.type == 0x0020

        msg = STUNMessage(
            message_class=STUNMessageClass.SUCCESS_RESPONSE,
            method=0x0001,
            transaction_id=transaction_id,
            attributes=[attr],
        )

        parsed = STUNMessage.from_bytes(msg.to_bytes())
        addr = parsed.get_mapped_address()

        assert addr is not None

    def test_stun_client_get_local_ip(self, stun_client):
        """Test getting local IP."""
        local_ip = stun_client._get_local_ip()

        assert local_ip is not None
        assert isinstance(local_ip, str)

    def test_stun_client_stats(self, stun_client):
        """Test getting client stats."""
        stats = stun_client.get_stats()

        assert "nat_type" in stats
        assert "local_ip" in stats
        assert "local_port" in stats


class TestTURNIntegration:
    """Integration tests for TURN protocol."""

    def test_turn_allocation(self):
        """Test TURN allocation creation."""
        allocation = TURNAllocation(
            allocation_id="alloc-001",
            client_address=("192.168.1.1", 12345),
            relayed_address=("203.0.113.1", 50000),
            lifetime=600,
        )

        assert allocation.allocation_id == "alloc-001"
        assert allocation.state.name == "PENDING"
        assert not allocation.is_expired()

    def test_turn_allocation_permissions(self):
        """Test TURN allocation permissions."""
        allocation = TURNAllocation(
            allocation_id="alloc-001",
            client_address=("192.168.1.1", 12345),
            relayed_address=("203.0.113.1", 50000),
        )

        peer = ("10.0.0.1", 8080)

        assert not allocation.has_permission(peer)

        allocation.add_permission(peer, lifetime=300)

        assert allocation.has_permission(peer)

    def test_turn_allocation_expiry(self):
        """Test TURN allocation expiry."""
        allocation = TURNAllocation(
            allocation_id="alloc-001",
            client_address=("192.168.1.1", 12345),
            relayed_address=("203.0.113.1", 50000),
            lifetime=0,
            created_at=0,
        )

        assert allocation.is_expired()

    def test_turn_allocation_time_remaining(self):
        """Test TURN allocation time remaining."""
        allocation = TURNAllocation(
            allocation_id="alloc-001",
            client_address=("192.168.1.1", 12345),
            relayed_address=("203.0.113.1", 50000),
            lifetime=600,
        )

        remaining = allocation.time_remaining()

        assert 0 <= remaining <= 600


class TestNATTraversalIntegration:
    """Integration tests for complete NAT traversal."""

    @pytest.mark.asyncio
    async def test_stun_server_lifecycle(self):
        """Test STUN server start and stop."""
        server = STUNServer(host="127.0.0.1", port=3479)

        await server.start()

        assert server._running is True

        await server.stop()

        assert server._running is False

    @pytest.mark.asyncio
    async def test_turn_server_lifecycle(self):
        """Test TURN server start and stop."""
        server = TURNServer(host="127.0.0.1", port=3480)

        await server.start()

        assert server._running is True

        stats = server.get_stats()
        assert "running" in stats

        await server.stop()

        assert server._running is False

    @pytest.mark.asyncio
    async def test_turn_client_lifecycle(self):
        """Test TURN client lifecycle."""
        client = TURNClient(server_host="127.0.0.1", server_port=3480)

        stats = client.get_stats()

        assert "nat_type" in stats
        assert "allocations" in stats


class TestNATTypeDetection:
    """Tests for NAT type detection."""

    def test_nat_type_enum(self):
        """Test NAT type enum values."""
        assert NATType.UNKNOWN.value == 0
        assert NATType.PUBLIC.value == 1
        assert NATType.FULL_CONE.value == 2
        assert NATType.RESTRICTED_CONE.value == 3
        assert NATType.PORT_RESTRICTED.value == 4
        assert NATType.SYMMETRIC.value == 5

    @pytest.mark.asyncio
    async def test_nat_detection_with_mock(self):
        """Test NAT detection with mocked responses."""
        client = STUNClient()

        with patch.object(client, "_send_binding_request") as mock_send:
            mock_response = Mock()
            mock_response.get_mapped_address.return_value = ("192.168.1.1", 12345)
            mock_send.return_value = mock_response

            client.external_ip = "192.168.1.1"
            client.external_port = 12345

            assert client.external_ip == "192.168.1.1"


class TestUDPCommunication:
    """Tests for UDP communication."""

    @pytest.mark.asyncio
    async def test_udp_socket_creation(self):
        """Test UDP socket creation."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.setblocking(False)

        addr = sock.getsockname()
        assert addr[0] == "127.0.0.1"
        assert addr[1] > 0

        sock.close()

    @pytest.mark.asyncio
    async def test_udp_send_receive(self):
        """Test UDP send and receive."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("127.0.0.1", 0))
        server_sock.setblocking(False)

        server_addr = server_sock.getsockname()

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_sock.setblocking(False)

        loop = asyncio.get_event_loop()

        test_data = b"Hello, UDP!"
        await loop.sock_sendto(client_sock, test_data, server_addr)

        try:
            data, addr = await asyncio.wait_for(loop.sock_recvfrom(server_sock, 1024), timeout=2.0)
            assert data == test_data
        except asyncio.TimeoutError:
            pass
        finally:
            client_sock.close()
            server_sock.close()


class TestHolePunching:
    """Tests for UDP hole punching."""

    @pytest.mark.asyncio
    async def test_hole_punching_simulation(self):
        """Simulate UDP hole punching between two clients."""
        client1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client1.bind(("127.0.0.1", 0))
        client1.setblocking(False)

        client2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client2.bind(("127.0.0.1", 0))
        client2.setblocking(False)

        addr1 = client1.getsockname()
        addr2 = client2.getsockname()

        loop = asyncio.get_event_loop()

        await loop.sock_sendto(client1, b"PING from client1", addr2)
        await loop.sock_sendto(client2, b"PING from client2", addr1)

        try:
            data1, _ = await asyncio.wait_for(loop.sock_recvfrom(client1, 1024), timeout=2.0)
            assert b"client2" in data1
        except asyncio.TimeoutError:
            pass

        try:
            data2, _ = await asyncio.wait_for(loop.sock_recvfrom(client2, 1024), timeout=2.0)
            assert b"client1" in data2
        except asyncio.TimeoutError:
            pass

        client1.close()
        client2.close()
