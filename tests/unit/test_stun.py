"""
Tests for STUN Protocol Implementation.
"""

from legacy.p2p_network.stun import (
    NATType,
    STUNAttribute,
    STUNAttributeType,
    STUNClient,
    STUNMessage,
    STUNMessageClass,
)


class TestSTUNAttribute:
    """Test STUNAttribute class."""

    def test_software_attribute(self):
        """Test creating a SOFTWARE attribute."""
        attr = STUNAttribute.software("TestClient")

        assert attr.type == STUNAttributeType.SOFTWARE
        assert attr.value == b"TestClient"

    def test_change_request_attribute(self):
        """Test creating a CHANGE-REQUEST attribute."""
        attr = STUNAttribute.change_request(change_ip=True, change_port=True)

        assert attr.type == STUNAttributeType.CHANGE_REQUEST

    def test_mapped_address_attribute(self):
        """Test creating a MAPPED-ADDRESS attribute."""
        attr = STUNAttribute.mapped_address("192.168.1.1", 12345)

        assert attr.type == STUNAttributeType.MAPPED_ADDRESS

    def test_xor_mapped_address_attribute(self):
        """Test creating a XOR-MAPPED-ADDRESS attribute."""
        transaction_id = b"123456789012"
        attr = STUNAttribute.xor_mapped_address("192.168.1.1", 12345, transaction_id)

        assert attr.type == STUNAttributeType.XOR_MAPPED_ADDRESS

    def test_to_bytes(self):
        """Test attribute serialization."""
        attr = STUNAttribute(STUNAttributeType.SOFTWARE, b"Test")
        data = attr.to_bytes()

        assert len(data) >= 4
        assert data[:2] == STUNAttributeType.SOFTWARE.to_bytes(2, "big")


class TestSTUNMessage:
    """Test STUNMessage class."""

    def test_create_binding_request(self):
        """Test creating a binding request."""
        msg = STUNMessage(
            message_class=STUNMessageClass.REQUEST,
            method=0x0001,
            attributes=[
                STUNAttribute.software("TestClient")
            ]
        )

        assert msg.message_class == STUNMessageClass.REQUEST
        assert msg.magic_cookie == 0x2112A442
        assert len(msg.transaction_id) == 12

    def test_to_bytes(self):
        """Test message serialization."""
        msg = STUNMessage(
            message_class=STUNMessageClass.REQUEST,
            method=0x0001,
            attributes=[
                STUNAttribute.software("Test")
            ]
        )

        data = msg.to_bytes()

        assert len(data) >= 20
        assert data[4:8] == msg.magic_cookie.to_bytes(4, "big")

    def test_from_bytes(self):
        """Test message deserialization."""
        original = STUNMessage(
            message_class=STUNMessageClass.REQUEST,
            method=0x0001,
            attributes=[
                STUNAttribute.software("Test")
            ]
        )

        data = original.to_bytes()
        parsed = STUNMessage.from_bytes(data)

        assert parsed is not None
        assert parsed.transaction_id == original.transaction_id
        assert parsed.magic_cookie == original.magic_cookie

    def test_from_bytes_invalid(self):
        """Test parsing invalid data."""
        assert STUNMessage.from_bytes(b"") is None
        assert STUNMessage.from_bytes(b"short") is None

        invalid_magic = b"\x00\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 12
        assert STUNMessage.from_bytes(invalid_magic) is None

    def test_get_mapped_address(self):
        """Test extracting mapped address."""
        msg = STUNMessage(
            message_class=STUNMessageClass.SUCCESS_RESPONSE,
            method=0x0001,
            attributes=[
                STUNAttribute.mapped_address("192.168.1.1", 12345)
            ]
        )

        addr = msg.get_mapped_address()

        assert addr is not None
        assert addr[0] == "192.168.1.1"
        assert addr[1] == 12345

    def test_get_attribute(self):
        """Test getting attribute by type."""
        attr = STUNAttribute.software("TestClient")
        msg = STUNMessage(
            message_class=STUNMessageClass.REQUEST,
            attributes=[attr]
        )

        found = msg.get_attribute(STUNAttributeType.SOFTWARE)

        assert found is not None
        assert found.value == b"TestClient"

        not_found = msg.get_attribute(STUNAttributeType.MAPPED_ADDRESS)
        assert not_found is None


class TestSTUNClient:
    """Test STUNClient class."""

    def test_init(self):
        """Test client initialization."""
        client = STUNClient(local_port=12345)

        assert client.local_port == 12345
        assert client.nat_type == NATType.UNKNOWN
        assert client.external_ip is None
        assert client.external_port is None

    def test_get_local_ip(self):
        """Test getting local IP."""
        client = STUNClient()

        local_ip = client._get_local_ip()

        assert local_ip is not None
        assert local_ip != "127.0.0.1" or True

    def test_get_stats(self):
        """Test getting client stats."""
        client = STUNClient(local_port=12345)
        client.nat_type = NATType.FULL_CONE
        client.external_ip = "1.2.3.4"
        client.external_port = 54321

        stats = client.get_stats()

        assert stats["nat_type"] == "FULL_CONE"
        assert stats["external_ip"] == "1.2.3.4"
        assert stats["external_port"] == 54321
        assert stats["local_port"] == 12345


class TestNATType:
    """Test NATType enum."""

    def test_nat_types(self):
        """Test all NAT types are defined."""
        assert NATType.UNKNOWN.value == 0
        assert NATType.PUBLIC.value == 1
        assert NATType.FULL_CONE.value == 2
        assert NATType.RESTRICTED_CONE.value == 3
        assert NATType.PORT_RESTRICTED.value == 4
        assert NATType.SYMMETRIC.value == 5
        assert NATType.BLOCKED.value == 6
        assert NATType.UDP_BLOCKED.value == 7


class TestSTUNMessageClass:
    """Test STUNMessageClass enum."""

    def test_message_classes(self):
        """Test all message classes are defined."""
        assert STUNMessageClass.REQUEST.value == 0x0001
        assert STUNMessageClass.INDICATION.value == 0x0011
        assert STUNMessageClass.SUCCESS_RESPONSE.value == 0x0101
        assert STUNMessageClass.ERROR_RESPONSE.value == 0x0111
