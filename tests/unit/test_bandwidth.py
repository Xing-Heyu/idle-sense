"""
Tests for Bandwidth Limiting.
"""

import time

from legacy.p2p_network.bandwidth import (
    BandwidthConfig,
    BandwidthManager,
    ConnectionStats,
    TokenBucket,
    TrafficPriority,
)


class TestTokenBucket:
    """Test TokenBucket class."""

    def test_create_bucket(self):
        """Test creating a token bucket."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)

        assert bucket.capacity == 100
        assert bucket.tokens == 0.0

    def test_consume(self):
        """Test consuming tokens."""
        bucket = TokenBucket(capacity=100, refill_rate=100.0)
        bucket.tokens = 50

        result = bucket.consume(30)

        assert result is True
        assert bucket.tokens < 25

    def test_consume_insufficient(self):
        """Test consuming with insufficient tokens."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket.tokens = 10

        result = bucket.consume(50)

        assert result is False

    def test_refill(self):
        """Test token refill."""
        bucket = TokenBucket(capacity=100, refill_rate=100.0)
        bucket.tokens = 0
        bucket.last_refill = time.time() - 1.0

        bucket.refill()

        assert bucket.tokens > 0

    def test_refill_cap(self):
        """Test refill doesn't exceed capacity."""
        bucket = TokenBucket(capacity=100, refill_rate=1000.0)
        bucket.tokens = 90
        bucket.last_refill = time.time() - 10.0

        bucket.refill()

        assert bucket.tokens == 100

    def test_wait_time(self):
        """Test wait time calculation."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket.tokens = 5

        wait = bucket.wait_time(15)

        assert 0.9 < wait < 1.1


class TestConnectionStats:
    """Test ConnectionStats class."""

    def test_create_stats(self):
        """Test creating connection stats."""
        stats = ConnectionStats(connection_id="conn-001")

        assert stats.connection_id == "conn-001"
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0

    def test_total_bytes(self):
        """Test total bytes calculation."""
        stats = ConnectionStats(
            connection_id="conn-001",
            bytes_sent=100,
            bytes_received=200
        )

        assert stats.total_bytes == 300

    def test_age(self):
        """Test age calculation."""
        stats = ConnectionStats(
            connection_id="conn-001",
            created_at=time.time() - 10.0
        )

        assert stats.age >= 10.0


class TestBandwidthManager:
    """Test BandwidthManager class."""

    def test_init(self):
        """Test manager initialization."""
        manager = BandwidthManager()

        assert manager.config is not None
        assert len(manager._connections) == 0

    def test_register_connection(self):
        """Test registering a connection."""
        manager = BandwidthManager()

        result = manager.register_connection("conn-001")

        assert result is True
        assert "conn-001" in manager._connections

    def test_max_connections(self):
        """Test max connections limit."""
        config = BandwidthConfig(max_connections=2)
        manager = BandwidthManager(config)

        manager.register_connection("conn-001")
        manager.register_connection("conn-002")
        result = manager.register_connection("conn-003")

        assert result is False

    def test_unregister_connection(self):
        """Test unregistering a connection."""
        manager = BandwidthManager()
        manager.register_connection("conn-001")

        manager.unregister_connection("conn-001")

        assert "conn-001" not in manager._connections

    def test_can_send(self):
        """Test send check."""
        manager = BandwidthManager()
        manager.upload_bucket.tokens = 1000

        result = manager.can_send(500)

        assert result is True

    def test_can_send_insufficient(self):
        """Test send check with insufficient tokens."""
        manager = BandwidthManager()
        manager.upload_bucket.tokens = 100

        result = manager.can_send(500)

        assert result is False

    def test_record_send(self):
        """Test recording sent data."""
        manager = BandwidthManager()
        manager.register_connection("conn-001")

        manager.record_send(100, "conn-001")

        assert manager._stats["total_bytes_sent"] == 100
        assert manager._connections["conn-001"].bytes_sent == 100

    def test_record_receive(self):
        """Test recording received data."""
        manager = BandwidthManager()
        manager.register_connection("conn-001")

        manager.record_receive(200, "conn-001")

        assert manager._stats["total_bytes_received"] == 200
        assert manager._connections["conn-001"].bytes_received == 200

    def test_get_stats(self):
        """Test getting statistics."""
        manager = BandwidthManager()
        manager.register_connection("conn-001")

        stats = manager.get_stats()

        assert "total_bytes_sent" in stats
        assert "active_connections" in stats
        assert stats["active_connections"] == 1

    def test_cleanup_idle_connections(self):
        """Test cleaning up idle connections."""
        manager = BandwidthManager()
        manager.register_connection("conn-001")
        manager._connections["conn-001"].last_activity = time.time() - 400.0

        cleaned = manager.cleanup_idle_connections(max_idle_time=300.0)

        assert cleaned == 1
        assert "conn-001" not in manager._connections


class TestTrafficPriority:
    """Test TrafficPriority enum."""

    def test_priorities(self):
        """Test all priorities are defined."""
        assert TrafficPriority.LOW.value == 0
        assert TrafficPriority.NORMAL.value == 1
        assert TrafficPriority.HIGH.value == 2
        assert TrafficPriority.CRITICAL.value == 3


class TestBandwidthConfig:
    """Test BandwidthConfig class."""

    def test_default_config(self):
        """Test default configuration."""
        config = BandwidthConfig()

        assert config.max_upload_bytes_per_sec == 1024 * 1024
        assert config.max_download_bytes_per_sec == 10 * 1024 * 1024
        assert config.max_connections == 100
