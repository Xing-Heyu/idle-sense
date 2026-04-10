"""
Tests for Data Locality.
"""

from legacy.distributed_task_v2.data_locality import (
    DataLocalityManager,
    DataLocation,
    DataType,
    LocalityLevel,
    NodeInfo,
)


class TestDataLocation:
    """Test DataLocation class."""

    def test_create_location(self):
        """Test creating a data location."""
        loc = DataLocation(
            data_id="data-001",
            data_type=DataType.FILE,
            node_id="node-001",
            path="/data/file.txt",
            size_bytes=1024,
        )

        assert loc.data_id == "data-001"
        assert loc.data_type == DataType.FILE
        assert loc.node_id == "node-001"

    def test_record_access(self):
        """Test recording access."""
        loc = DataLocation(data_id="data-001", data_type=DataType.FILE, node_id="node-001")

        initial_count = loc.access_count
        loc.record_access()

        assert loc.access_count == initial_count + 1

    def test_to_dict(self):
        """Test serialization."""
        loc = DataLocation(
            data_id="data-001", data_type=DataType.MEMORY, node_id="node-001", size_bytes=2048
        )

        data = loc.to_dict()

        assert data["data_id"] == "data-001"
        assert data["data_type"] == DataType.MEMORY.value
        assert data["size_bytes"] == 2048


class TestNodeInfo:
    """Test NodeInfo class."""

    def test_create_node_info(self):
        """Test creating node info."""
        info = NodeInfo(node_id="node-001", rack_id="rack-1", data_center="dc-1")

        assert info.node_id == "node-001"
        assert info.rack_id == "rack-1"

    def test_has_data(self):
        """Test checking if node has data."""
        info = NodeInfo(node_id="node-001")
        info.available_data.add("data-001")

        assert info.has_data("data-001") is True
        assert info.has_data("data-002") is False


class TestDataLocalityManager:
    """Test DataLocalityManager class."""

    def test_init(self):
        """Test manager initialization."""
        manager = DataLocalityManager()

        assert len(manager.nodes) == 0
        assert len(manager.data_locations) == 0

    def test_register_node(self):
        """Test registering a node."""
        manager = DataLocalityManager()

        manager.register_node("node-001", rack_id="rack-1", data_center="dc-1")

        assert "node-001" in manager.nodes
        assert manager.nodes["node-001"].rack_id == "rack-1"

    def test_unregister_node(self):
        """Test unregistering a node."""
        manager = DataLocalityManager()
        manager.register_node("node-001")

        manager.unregister_node("node-001")

        assert "node-001" not in manager.nodes

    def test_register_data(self):
        """Test registering data."""
        manager = DataLocalityManager()
        manager.register_node("node-001")

        manager.register_data("data-001", "node-001", DataType.FILE)

        assert "data-001" in manager.data_locations
        assert "data-001" in manager.nodes["node-001"].available_data

    def test_get_data_nodes(self):
        """Test getting nodes with data."""
        manager = DataLocalityManager()
        manager.register_node("node-001")
        manager.register_node("node-002")

        manager.register_data("data-001", "node-001")
        manager.register_data("data-001", "node-002")

        nodes = manager.get_data_nodes("data-001")

        assert len(nodes) == 2
        assert "node-001" in nodes
        assert "node-002" in nodes

    def test_calculate_locality_score(self):
        """Test calculating locality score."""
        manager = DataLocalityManager()
        manager.register_node("node-001")
        manager.register_data("data-001", "node-001")
        manager.register_data("data-002", "node-002")

        score = manager.calculate_locality_score("node-001", ["data-001"])

        assert score.level == LocalityLevel.PROCESS_LOCAL
        assert score.score == 1.0

    def test_select_best_node(self):
        """Test selecting best node."""
        manager = DataLocalityManager()
        manager.register_node("node-001")
        manager.register_node("node-002")
        manager.register_data("data-001", "node-001")

        best = manager.select_best_node(["data-001"])

        assert best == "node-001"

    def test_get_stats(self):
        """Test getting statistics."""
        manager = DataLocalityManager()
        manager.register_node("node-001")

        stats = manager.get_stats()

        assert stats["total_nodes"] == 1


class TestLocalityLevel:
    """Test LocalityLevel enum."""

    def test_levels(self):
        """Test all levels are defined."""
        assert LocalityLevel.PROCESS_LOCAL.value == 0
        assert LocalityLevel.NODE_LOCAL.value == 1
        assert LocalityLevel.RACK_LOCAL.value == 2
        assert LocalityLevel.ANY.value == 3


class TestDataType:
    """Test DataType enum."""

    def test_types(self):
        """Test all data types are defined."""
        assert DataType.FILE.value == 0
        assert DataType.DATABASE.value == 1
        assert DataType.MEMORY.value == 2
        assert DataType.DISTRIBUTED.value == 3
