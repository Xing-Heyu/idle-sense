"""
Tests for Reputation System.
"""

from legacy.p2p_network.reputation import (
    NodeReputation,
    NodeType,
    ReputationEvent,
    ReputationManager,
    ReputationRecord,
)


class TestReputationRecord:
    """Test ReputationRecord class."""

    def test_create_record(self):
        """Test creating a reputation record."""
        record = ReputationRecord(
            node_id="node-001", event_type=ReputationEvent.TASK_COMPLETED, score_delta=0.05
        )

        assert record.node_id == "node-001"
        assert record.event_type == ReputationEvent.TASK_COMPLETED
        assert record.score_delta == 0.05

    def test_to_dict(self):
        """Test record serialization."""
        record = ReputationRecord(
            node_id="node-001",
            event_type=ReputationEvent.TASK_FAILED,
            score_delta=-0.03,
            details={"error": "timeout"},
        )

        data = record.to_dict()

        assert data["node_id"] == "node-001"
        assert data["event_type"] == "task_failed"
        assert data["score_delta"] == -0.03


class TestNodeReputation:
    """Test NodeReputation class."""

    def test_create_reputation(self):
        """Test creating node reputation."""
        rep = NodeReputation(node_id="node-001")

        assert rep.node_id == "node-001"
        assert rep.trust_score == 0.5
        assert rep.total_interactions == 0
        assert rep.node_type == NodeType.UNKNOWN

    def test_success_rate(self):
        """Test success rate calculation."""
        rep = NodeReputation(node_id="node-001", total_interactions=10, successful_interactions=8)

        assert rep.success_rate == 0.8

    def test_success_rate_no_interactions(self):
        """Test success rate with no interactions."""
        rep = NodeReputation(node_id="node-001")

        assert rep.success_rate == 0.5

    def test_add_event(self):
        """Test adding events."""
        rep = NodeReputation(node_id="node-001")

        event = ReputationRecord(
            node_id="node-001", event_type=ReputationEvent.TASK_COMPLETED, score_delta=0.05
        )

        rep.add_event(event)

        assert rep.trust_score == 0.55
        assert len(rep.reputation_history) == 1

    def test_trust_score_bounds(self):
        """Test trust score stays within bounds."""
        rep = NodeReputation(node_id="node-001", trust_score=0.99)

        event = ReputationRecord(
            node_id="node-001", event_type=ReputationEvent.TASK_COMPLETED, score_delta=0.1
        )

        rep.add_event(event)

        assert rep.trust_score == 1.0

    def test_to_dict(self):
        """Test reputation serialization."""
        rep = NodeReputation(
            node_id="node-001",
            trust_score=0.7,
            total_interactions=10,
            successful_interactions=8,
            node_type=NodeType.HONEST,
        )

        data = rep.to_dict()

        assert data["node_id"] == "node-001"
        assert data["trust_score"] == 0.7
        assert data["node_type"] == "honest"


class TestReputationManager:
    """Test ReputationManager class."""

    def test_init(self):
        """Test manager initialization."""
        manager = ReputationManager(local_node_id="local-node")

        assert manager.local_node_id == "local-node"
        assert len(manager.reputations) == 0

    def test_get_or_create_reputation(self):
        """Test getting or creating reputation."""
        manager = ReputationManager(local_node_id="local-node")

        rep = manager.get_or_create_reputation("node-001")

        assert rep.node_id == "node-001"
        assert "node-001" in manager.reputations

    def test_record_event(self):
        """Test recording an event."""
        manager = ReputationManager(local_node_id="local-node")

        score = manager.record_event(node_id="node-001", event_type=ReputationEvent.TASK_COMPLETED)

        assert score == 0.55
        assert manager._stats["total_events"] == 1

    def test_record_event_local_node(self):
        """Test recording event for local node returns 1.0."""
        manager = ReputationManager(local_node_id="local-node")

        score = manager.record_event(
            node_id="local-node", event_type=ReputationEvent.TASK_COMPLETED
        )

        assert score == 1.0

    def test_is_trusted(self):
        """Test trust checking."""
        manager = ReputationManager(local_node_id="local-node")

        assert manager.is_trusted("node-001") is True

        for _ in range(20):
            manager.record_event("node-001", ReputationEvent.MALICIOUS_BEHAVIOR)

        assert manager.is_trusted("node-001") is False

    def test_blacklist_node(self):
        """Test blacklisting a node."""
        manager = ReputationManager(local_node_id="local-node")

        manager.blacklist_node("node-001", "Test blacklist")

        assert manager.is_blacklisted("node-001") is True
        assert manager._stats["nodes_blacklisted"] == 1

    def test_unblacklist_node(self):
        """Test unblacklisting a node."""
        manager = ReputationManager(local_node_id="local-node")

        manager.blacklist_node("node-001", "Test")
        manager.unblacklist_node("node-001")

        assert manager.is_blacklisted("node-001") is False

    def test_select_best_peers(self):
        """Test selecting best peers."""
        manager = ReputationManager(local_node_id="local-node")

        manager.record_event("node-001", ReputationEvent.TASK_COMPLETED)
        manager.record_event("node-001", ReputationEvent.TASK_COMPLETED)
        manager.record_event("node-002", ReputationEvent.TASK_FAILED)

        best = manager.select_best_peers(count=2)

        assert len(best) == 2
        assert "node-001" in best

    def test_get_stats(self):
        """Test getting statistics."""
        manager = ReputationManager(local_node_id="local-node")

        manager.record_event("node-001", ReputationEvent.TASK_COMPLETED)

        stats = manager.get_stats()

        assert stats["total_nodes"] == 1
        assert stats["total_events"] == 1

    def test_export_import(self):
        """Test exporting and importing reputations."""
        manager = ReputationManager(local_node_id="local-node")

        manager.record_event("node-001", ReputationEvent.TASK_COMPLETED)
        manager.blacklist_node("node-002", "Test")

        data = manager.export_reputations()

        new_manager = ReputationManager(local_node_id="new-node")
        new_manager.import_reputations(data)

        assert "node-001" in new_manager.reputations
        assert new_manager.is_blacklisted("node-002")


class TestNodeType:
    """Test NodeType enum."""

    def test_node_types(self):
        """Test all node types are defined."""
        assert NodeType.HONEST.value == "honest"
        assert NodeType.MALICIOUS.value == "malicious"
        assert NodeType.SUSPICIOUS.value == "suspicious"
        assert NodeType.UNKNOWN.value == "unknown"


class TestReputationEvent:
    """Test ReputationEvent enum."""

    def test_events(self):
        """Test all events are defined."""
        assert ReputationEvent.TASK_COMPLETED.value == "task_completed"
        assert ReputationEvent.TASK_FAILED.value == "task_failed"
        assert ReputationEvent.MALICIOUS_BEHAVIOR.value == "malicious_behavior"
