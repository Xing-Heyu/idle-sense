"""
Tests for Shuffle Implementation.
"""

from legacy.distributed_task_v2.shuffle import (
    ShuffleManager,
    ShufflePartition,
    ShuffleResult,
)


class TestShufflePartition:
    """Test ShufflePartition class."""

    def test_create_partition(self):
        """Test creating a partition."""
        partition = ShufflePartition(
            partition_id=0,
            key="test-key"
        )

        assert partition.partition_id == 0
        assert partition.key == "test-key"
        assert partition.size == 0
        assert len(partition.values) == 0

    def test_add_value(self):
        """Test adding values to partition."""
        partition = ShufflePartition(partition_id=0, key="key1")

        partition.add_value("value1")
        partition.add_value("value2")

        assert partition.size == 2
        assert len(partition.values) == 2
        assert partition.values == ["value1", "value2"]

    def test_to_dict(self):
        """Test partition serialization."""
        partition = ShufflePartition(
            partition_id=1,
            key="key1",
            node_id="node-1"
        )
        partition.add_value("value1")

        data = partition.to_dict()

        assert data["partition_id"] == 1
        assert data["key"] == "key1"
        assert data["size"] == 1
        assert data["node_id"] == "node-1"


class TestShuffleResult:
    """Test ShuffleResult class."""

    def test_create_result(self):
        """Test creating a shuffle result."""
        result = ShuffleResult(
            shuffle_id="shuffle-001",
            stage_id="stage-1",
            task_id="task-001"
        )

        assert result.shuffle_id == "shuffle-001"
        assert result.status == "pending"
        assert len(result.partitions) == 0

    def test_total_size(self):
        """Test total size calculation."""
        result = ShuffleResult(
            shuffle_id="shuffle-001",
            stage_id="stage-1",
            task_id="task-001",
            partitions={
                0: ShufflePartition(0, "k1", values=["v1", "v2"]),
                1: ShufflePartition(1, "k2", values=["v3"]),
            }
        )

        assert result.total_size == 3

    def test_is_complete(self):
        """Test completion check."""
        result = ShuffleResult(
            shuffle_id="shuffle-001",
            stage_id="stage-1",
            task_id="task-001",
            partitions={
                0: ShufflePartition(0, "k1", node_id="node-1"),
                1: ShufflePartition(1, "k2", node_id=None),
            }
        )

        assert result.is_complete is False

        result.partitions[1].node_id = "node-2"
        assert result.is_complete is True


class TestShuffleManager:
    """Test ShuffleManager class."""

    def test_init(self):
        """Test manager initialization."""
        manager = ShuffleManager(num_partitions=4)

        assert manager.num_partitions == 4
        assert len(manager._shuffle_results) == 0

    def test_get_partition_id(self):
        """Test partition ID calculation."""
        manager = ShuffleManager(num_partitions=4)

        id1 = manager.get_partition_id("key1")
        id2 = manager.get_partition_id("key2")

        assert 0 <= id1 < 4
        assert 0 <= id2 < 4

    def test_start_shuffle(self):
        """Test starting a shuffle."""
        manager = ShuffleManager(num_partitions=4)

        shuffle_id = manager.start_shuffle("task-001", "stage-1")

        assert shuffle_id is not None
        assert shuffle_id in manager._shuffle_results
        assert manager._stats["shuffles_started"] == 1

    def test_add_data(self):
        """Test adding data to shuffle."""
        manager = ShuffleManager(num_partitions=4)
        shuffle_id = manager.start_shuffle("task-001", "stage-1")

        success = manager.add_data(shuffle_id, "key1", "value1")

        assert success is True
        assert manager._stats["total_records_shuffled"] == 1

    def test_add_data_invalid_shuffle(self):
        """Test adding data to invalid shuffle."""
        manager = ShuffleManager()

        success = manager.add_data("invalid-id", "key1", "value1")

        assert success is False

    def test_get_partition(self):
        """Test getting a partition."""
        manager = ShuffleManager(num_partitions=4)
        shuffle_id = manager.start_shuffle("task-001", "stage-1")
        manager.add_data(shuffle_id, "key1", "value1")

        partition_id = manager.get_partition_id("key1")
        partition = manager.get_partition(shuffle_id, partition_id)

        assert partition is not None
        assert partition.size == 1

    def test_assign_partition(self):
        """Test assigning a partition to a node."""
        manager = ShuffleManager(num_partitions=4)
        shuffle_id = manager.start_shuffle("task-001", "stage-1")

        success = manager.assign_partition(shuffle_id, 0, "node-1")

        assert success is True
        assert manager._shuffle_results[shuffle_id].partitions[0].node_id == "node-1"

    def test_complete_shuffle(self):
        """Test completing a shuffle."""
        manager = ShuffleManager()
        shuffle_id = manager.start_shuffle("task-001", "stage-1")

        success = manager.complete_shuffle(shuffle_id)

        assert success is True
        assert manager._shuffle_results[shuffle_id].status == "completed"
        assert manager._stats["shuffles_completed"] == 1

    def test_get_stats(self):
        """Test getting statistics."""
        manager = ShuffleManager()

        stats = manager.get_stats()

        assert "shuffles_started" in stats
        assert "shuffles_completed" in stats
        assert "total_records_shuffled" in stats


class TestDefaultHash:
    """Test default hash function."""

    def test_consistent_hash(self):
        """Test that hash is consistent for same key."""
        manager = ShuffleManager()

        hash1 = manager._default_hash("test-key")
        hash2 = manager._default_hash("test-key")

        assert hash1 == hash2

    def test_different_keys_different_hash(self):
        """Test that different keys produce different hashes."""
        manager = ShuffleManager()

        hash1 = manager._default_hash("key1")
        hash2 = manager._default_hash("key2")

        assert hash1 != hash2
