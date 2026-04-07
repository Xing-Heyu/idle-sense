"""
Node Reputation System for P2P Network.

Implements a reputation system to identify and isolate malicious nodes:
- EigenTrust algorithm for decentralized reputation
- Trust score calculation based on behavior
- Malicious node detection and blacklisting
- Reputation-based peer selection

References:
- EigenTrust: Kamvar et al., "The EigenTrust Algorithm for Reputation Management" (2003)
- PeerTrust: Xiong & Liu, "A Peer-to-Peer Reputation System" (2004)
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class NodeType(Enum):
    HONEST = "honest"
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    UNKNOWN = "unknown"


class ReputationEvent(Enum):
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    INVALID_RESULT = "invalid_result"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    MALICIOUS_BEHAVIOR = "malicious_behavior"
    GOOD_BEHAVIOR = "good_behavior"
    BLACKLIST_VIOLATION = "blacklist_violation"


@dataclass
class ReputationRecord:
    """A record of a reputation event."""
    node_id: str
    event_type: ReputationEvent
    score_delta: float
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "event_type": self.event_type.value,
            "score_delta": self.score_delta,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class NodeReputation:
    """Reputation information for a node."""
    node_id: str
    trust_score: float = 0.5
    total_interactions: int = 0
    successful_interactions: int = 0
    failed_interactions: int = 0
    last_interaction: Optional[float] = None
    reputation_history: list[ReputationRecord] = field(default_factory=list)
    node_type: NodeType = NodeType.UNKNOWN
    is_blacklisted: bool = False
    blacklist_reason: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.total_interactions == 0:
            return 0.5
        return self.successful_interactions / self.total_interactions

    @property
    def reliability_score(self) -> float:
        if self.total_interactions < 5:
            return 0.5
        return self.success_rate * 0.7 + self.trust_score * 0.3

    def add_event(self, event: ReputationRecord):
        """Add a reputation event."""
        self.reputation_history.append(event)
        self.trust_score = max(0.0, min(1.0, self.trust_score + event.score_delta))
        self.last_interaction = event.timestamp

        if len(self.reputation_history) > 100:
            self.reputation_history = self.reputation_history[-100:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "trust_score": round(self.trust_score, 3),
            "total_interactions": self.total_interactions,
            "successful_interactions": self.successful_interactions,
            "failed_interactions": self.failed_interactions,
            "success_rate": round(self.success_rate, 3),
            "reliability_score": round(self.reliability_score, 3),
            "node_type": self.node_type.value,
            "is_blacklisted": self.is_blacklisted,
            "blacklist_reason": self.blacklist_reason,
            "last_interaction": self.last_interaction,
        }


class ReputationConfig:
    """Configuration for reputation system."""

    SCORE_DELTAS = {
        ReputationEvent.TASK_COMPLETED: 0.05,
        ReputationEvent.TASK_FAILED: -0.03,
        ReputationEvent.INVALID_RESULT: -0.15,
        ReputationEvent.TIMEOUT: -0.02,
        ReputationEvent.CONNECTION_ERROR: -0.01,
        ReputationEvent.MALICIOUS_BEHAVIOR: -0.5,
        ReputationEvent.GOOD_BEHAVIOR: 0.02,
        ReputationEvent.BLACKLIST_VIOLATION: -0.3,
    }

    BLACKLIST_THRESHOLD = 0.2
    SUSPICIOUS_THRESHOLD = 0.4
    HONEST_THRESHOLD = 0.7
    MIN_INTERACTIONS_FOR_RATING = 5
    TRUST_DECAY_RATE = 0.001
    MAX_HISTORY_SIZE = 100


class ReputationManager:
    """
    Manages node reputation in the P2P network.

    Features:
    - EigenTrust-inspired trust calculation
    - Event-based reputation updates
    - Blacklist management
    - Reputation-based peer selection
    """

    def __init__(self, local_node_id: str, config: ReputationConfig = None):
        self.local_node_id = local_node_id
        self.config = config or ReputationConfig()

        self.reputations: dict[str, NodeReputation] = {}
        self.blacklist: set[str] = set()
        self.trust_matrix: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        self._stats = {
            "total_events": 0,
            "nodes_blacklisted": 0,
            "nodes_suspicious": 0,
            "nodes_honest": 0,
        }

    def get_or_create_reputation(self, node_id: str) -> NodeReputation:
        """Get or create reputation for a node."""
        if node_id not in self.reputations:
            self.reputations[node_id] = NodeReputation(node_id=node_id)
        return self.reputations[node_id]

    def record_event(
        self,
        node_id: str,
        event_type: ReputationEvent,
        details: dict[str, Any] = None
    ) -> float:
        """
        Record a reputation event for a node.

        Args:
            node_id: The node ID
            event_type: Type of event
            details: Additional details

        Returns:
            The new trust score
        """
        if node_id == self.local_node_id:
            return 1.0

        reputation = self.get_or_create_reputation(node_id)

        score_delta = self.config.SCORE_DELTAS.get(event_type, 0.0)

        record = ReputationRecord(
            node_id=node_id,
            event_type=event_type,
            score_delta=score_delta,
            details=details or {},
        )

        reputation.add_event(record)
        reputation.total_interactions += 1

        if event_type in (ReputationEvent.TASK_COMPLETED, ReputationEvent.GOOD_BEHAVIOR):
            reputation.successful_interactions += 1
        elif event_type in (ReputationEvent.TASK_FAILED, ReputationEvent.INVALID_RESULT,
                           ReputationEvent.TIMEOUT, ReputationEvent.CONNECTION_ERROR):
            reputation.failed_interactions += 1

        self._update_node_type(node_id)
        self._check_blacklist(node_id)

        self._stats["total_events"] += 1

        return reputation.trust_score

    def _update_node_type(self, node_id: str):
        """Update the node type based on trust score."""
        reputation = self.reputations.get(node_id)
        if not reputation:
            return

        old_type = reputation.node_type

        if reputation.trust_score < self.config.BLACKLIST_THRESHOLD:
            reputation.node_type = NodeType.MALICIOUS
        elif reputation.trust_score < self.config.SUSPICIOUS_THRESHOLD:
            reputation.node_type = NodeType.SUSPICIOUS
        elif reputation.trust_score >= self.config.HONEST_THRESHOLD:
            reputation.node_type = NodeType.HONEST
        else:
            reputation.node_type = NodeType.UNKNOWN

        if old_type != reputation.node_type:
            self._update_stats()

    def _check_blacklist(self, node_id: str):
        """Check if a node should be blacklisted."""
        reputation = self.reputations.get(node_id)
        if not reputation:
            return

        if reputation.trust_score < self.config.BLACKLIST_THRESHOLD and node_id not in self.blacklist:
            self.blacklist.add(node_id)
            reputation.is_blacklisted = True
            reputation.blacklist_reason = "Low trust score"
            self._stats["nodes_blacklisted"] += 1

    def _update_stats(self):
        """Update statistics."""
        self._stats["nodes_honest"] = sum(
            1 for r in self.reputations.values()
            if r.node_type == NodeType.HONEST
        )
        self._stats["nodes_suspicious"] = sum(
            1 for r in self.reputations.values()
            if r.node_type == NodeType.SUSPICIOUS
        )

    def is_trusted(self, node_id: str) -> bool:
        """Check if a node is trusted."""
        if node_id in self.blacklist:
            return False

        reputation = self.reputations.get(node_id)
        if not reputation:
            return True

        return reputation.trust_score >= self.config.SUSPICIOUS_THRESHOLD

    def is_blacklisted(self, node_id: str) -> bool:
        """Check if a node is blacklisted."""
        return node_id in self.blacklist

    def blacklist_node(self, node_id: str, reason: str = "Manual blacklist"):
        """Manually blacklist a node."""
        self.blacklist.add(node_id)
        reputation = self.get_or_create_reputation(node_id)
        reputation.is_blacklisted = True
        reputation.blacklist_reason = reason
        reputation.node_type = NodeType.MALICIOUS
        self._stats["nodes_blacklisted"] += 1

    def unblacklist_node(self, node_id: str):
        """Remove a node from the blacklist."""
        self.blacklist.discard(node_id)
        if node_id in self.reputations:
            self.reputations[node_id].is_blacklisted = False
            self.reputations[node_id].blacklist_reason = None

    def get_trust_score(self, node_id: str) -> float:
        """Get the trust score for a node."""
        reputation = self.reputations.get(node_id)
        if not reputation:
            return 0.5
        return reputation.trust_score

    def select_best_peers(self, count: int = 5, exclude: set[str] = None) -> list[str]:
        """
        Select the best peers based on reputation.

        Args:
            count: Number of peers to select
            exclude: Set of node IDs to exclude

        Returns:
            List of node IDs sorted by reputation
        """
        exclude = exclude or set()
        exclude.add(self.local_node_id)
        exclude.update(self.blacklist)

        candidates = [
            (node_id, rep.reliability_score)
            for node_id, rep in self.reputations.items()
            if node_id not in exclude and not rep.is_blacklisted
        ]

        candidates.sort(key=lambda x: x[1], reverse=True)

        return [node_id for node_id, _ in candidates[:count]]

    def update_trust_matrix(self, from_node: str, to_node: str, score: float):
        """Update the trust matrix for EigenTrust calculation."""
        self.trust_matrix[from_node][to_node] = score

    def calculate_eigen_trust(self, iterations: int = 10) -> dict[str, float]:
        """
        Calculate global trust scores using EigenTrust algorithm.

        Args:
            iterations: Number of iterations for convergence

        Returns:
            Dictionary of node_id -> global trust score
        """
        nodes = list(set(
            list(self.trust_matrix.keys()) +
            [n for d in self.trust_matrix.values() for n in d]
        ))

        if not nodes:
            return {}

        n = len(nodes)
        node_index = {node: i for i, node in enumerate(nodes)}

        C = [[0.0] * n for _ in range(n)]
        for from_node, scores in self.trust_matrix.items():
            i = node_index[from_node]
            total = sum(scores.values()) if scores else 1.0
            for to_node, score in scores.items():
                j = node_index[to_node]
                C[i][j] = score / total if total > 0 else 0.0

        t = [1.0 / n] * n

        for _ in range(iterations):
            new_t = [0.0] * n
            for i in range(n):
                for j in range(n):
                    new_t[i] += C[j][i] * t[j]

            total = sum(new_t)
            if total > 0:
                t = [v / total for v in new_t]

        return {nodes[i]: t[i] for i in range(n)}

    def apply_trust_decay(self):
        """Apply trust decay to all reputations."""
        decay = self.config.TRUST_DECAY_RATE
        for reputation in self.reputations.values():
            if reputation.last_interaction:
                time_since = time.time() - reputation.last_interaction
                decay_amount = decay * time_since / 3600
                reputation.trust_score = max(
                    0.5,
                    reputation.trust_score - decay_amount
                )

    def get_reputation(self, node_id: str) -> Optional[NodeReputation]:
        """Get reputation for a node."""
        return self.reputations.get(node_id)

    def get_all_reputations(self) -> dict[str, NodeReputation]:
        """Get all reputations."""
        return self.reputations

    def get_stats(self) -> dict[str, Any]:
        """Get reputation system statistics."""
        return {
            **self._stats,
            "total_nodes": len(self.reputations),
            "blacklisted_nodes": len(self.blacklist),
            "average_trust_score": sum(
                r.trust_score for r in self.reputations.values()
            ) / len(self.reputations) if self.reputations else 0.5,
        }

    def export_reputations(self) -> dict[str, Any]:
        """Export all reputation data."""
        return {
            "local_node_id": self.local_node_id,
            "reputations": {
                node_id: rep.to_dict()
                for node_id, rep in self.reputations.items()
            },
            "blacklist": list(self.blacklist),
            "stats": self.get_stats(),
        }

    def import_reputations(self, data: dict[str, Any]):
        """Import reputation data."""
        self.local_node_id = data.get("local_node_id", self.local_node_id)

        for node_id, rep_data in data.get("reputations", {}).items():
            reputation = NodeReputation(
                node_id=node_id,
                trust_score=rep_data.get("trust_score", 0.5),
                total_interactions=rep_data.get("total_interactions", 0),
                successful_interactions=rep_data.get("successful_interactions", 0),
                failed_interactions=rep_data.get("failed_interactions", 0),
                node_type=NodeType(rep_data.get("node_type", "unknown")),
                is_blacklisted=rep_data.get("is_blacklisted", False),
                blacklist_reason=rep_data.get("blacklist_reason"),
            )
            self.reputations[node_id] = reputation

        self.blacklist = set(data.get("blacklist", []))
        self._update_stats()


__all__ = [
    "NodeType",
    "ReputationEvent",
    "ReputationRecord",
    "NodeReputation",
    "ReputationConfig",
    "ReputationManager",
]
