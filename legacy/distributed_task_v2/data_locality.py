"""
Data Locality Optimization for Distributed Tasks.

Implements data locality optimization to minimize network transfer:
- Node selection based on data location
- Data-aware task scheduling
- Network topology awareness
- Locality-aware task assignment

References:
- Hadoop Data Locality: "Hadoop: The Definitive Guide" (White, 2015)
- Spark Data Locality: "Learning Spark" (Karau et al., 2015)
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class LocalityLevel(IntEnum):
    PROCESS_LOCAL = 0
    NODE_LOCAL = 1
    RACK_LOCAL = 2
    ANY = 3
    UNKNOWN = 4


class DataType(IntEnum):
    FILE = 0
    DATABASE = 1
    MEMORY = 2
    DISTRIBUTED = 3


@dataclass
class DataLocation:
    """Represents the location of a piece of data."""
    data_id: str
    data_type: DataType
    node_id: str
    path: Optional[str] = None
    size_bytes: int = 0
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    def record_access(self):
        """Record an access to this data."""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_id": self.data_id,
            "data_type": self.data_type.value,
            "node_id": self.node_id,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
        }


@dataclass
class NodeInfo:
    """Information about a node for locality calculations."""
    node_id: str
    rack_id: Optional[str] = None
    data_center: Optional[str] = None
    available_data: set[str] = field(default_factory=set)
    network_distance: dict[str, int] = field(default_factory=dict)

    def has_data(self, data_id: str) -> bool:
        return data_id in self.available_data

    def distance_to(self, other_node_id: str) -> int:
        return self.network_distance.get(other_node_id, 999)


@dataclass
class LocalityScore:
    """Score for data locality."""
    node_id: str
    level: LocalityLevel
    score: float
    data_ids: list[str] = field(default_factory=list)
    transfer_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "level": self.level.name,
            "score": self.score,
            "data_ids": self.data_ids,
            "transfer_cost": self.transfer_cost,
        }


class DataLocalityManager:
    """
    Manages data locality for distributed task scheduling.
    
    Features:
    - Track data locations across nodes
    - Calculate locality scores for task assignment
    - Optimize task placement based on data location
    - Network topology awareness
    """

    DEFAULT_NETWORK_COSTS = {
        "same_process": 0,
        "same_node": 1,
        "same_rack": 10,
        "same_data_center": 100,
        "remote": 1000,
    }

    def __init__(self):
        self.data_locations: dict[str, list[DataLocation]] = defaultdict(list)
        self.nodes: dict[str, NodeInfo] = {}
        self.network_costs: dict[str, int] = self.DEFAULT_NETWORK_COSTS.copy()

        self._stats = {
            "tasks_local": 0,
            "tasks_rack_local": 0,
            "tasks_remote": 0,
            "data_transferred": 0,
            "locality_hit_rate": 0.0,
        }

    def register_node(
        self,
        node_id: str,
        rack_id: str = None,
        data_center: str = None
    ):
        """Register a node with its topology information."""
        self.nodes[node_id] = NodeInfo(
            node_id=node_id,
            rack_id=rack_id,
            data_center=data_center,
        )

    def unregister_node(self, node_id: str):
        """Unregister a node."""
        if node_id in self.nodes:
            del self.nodes[node_id]

        for data_id in list(self.data_locations.keys()):
            self.data_locations[data_id] = [
                loc for loc in self.data_locations[data_id]
                if loc.node_id != node_id
            ]

    def register_data(
        self,
        data_id: str,
        node_id: str,
        data_type: DataType = DataType.FILE,
        path: str = None,
        size_bytes: int = 0
    ):
        """Register data location on a node."""
        location = DataLocation(
            data_id=data_id,
            data_type=data_type,
            node_id=node_id,
            path=path,
            size_bytes=size_bytes,
        )

        self.data_locations[data_id].append(location)

        if node_id in self.nodes:
            self.nodes[node_id].available_data.add(data_id)

    def unregister_data(self, data_id: str, node_id: str = None):
        """Unregister data location."""
        if node_id:
            self.data_locations[data_id] = [
                loc for loc in self.data_locations[data_id]
                if loc.node_id != node_id
            ]
            if node_id in self.nodes:
                self.nodes[node_id].available_data.discard(data_id)
        else:
            del self.data_locations[data_id]

    def get_data_nodes(self, data_id: str) -> list[str]:
        """Get all nodes that have a piece of data."""
        return [
            loc.node_id for loc in self.data_locations.get(data_id, [])
        ]

    def calculate_locality_score(
        self,
        node_id: str,
        required_data: list[str]
    ) -> LocalityScore:
        """
        Calculate locality score for a node given required data.
        
        Args:
            node_id: The node to evaluate
            required_data: List of data IDs required by the task
            
        Returns:
            LocalityScore with level and score
        """
        if node_id not in self.nodes:
            return LocalityScore(
                node_id=node_id,
                level=LocalityLevel.UNKNOWN,
                score=0.0,
                data_ids=required_data,
            )

        node = self.nodes[node_id]
        local_data = []
        rack_local_data = []
        data_center_local_data = []
        remote_data = []

        for data_id in required_data:
            locations = self.data_locations.get(data_id, [])

            if not locations:
                remote_data.append(data_id)
                continue

            found_local = False
            found_rack = False
            found_dc = False

            for loc in locations:
                if loc.node_id == node_id:
                    local_data.append(data_id)
                    found_local = True
                    break
                elif node.rack_id and self.nodes.get(loc.node_id, {}).rack_id == node.rack_id:
                    found_rack = True
                elif node.data_center and self.nodes.get(loc.node_id, {}).data_center == node.data_center:
                    found_dc = True

            if not found_local:
                if found_rack:
                    rack_local_data.append(data_id)
                elif found_dc:
                    data_center_local_data.append(data_id)
                else:
                    remote_data.append(data_id)

        total_data = len(required_data)
        if total_data == 0:
            level = LocalityLevel.ANY
            score = 1.0
        else:
            local_ratio = len(local_data) / total_data
            rack_ratio = len(rack_local_data) / total_data
            dc_ratio = len(data_center_local_data) / total_data

            if local_ratio == 1.0:
                level = LocalityLevel.PROCESS_LOCAL
            elif local_ratio > 0.5:
                level = LocalityLevel.NODE_LOCAL
            elif local_ratio + rack_ratio > 0.5:
                level = LocalityLevel.RACK_LOCAL
            else:
                level = LocalityLevel.ANY

            score = (
                local_ratio * 1.0 +
                rack_ratio * 0.5 +
                dc_ratio * 0.2 +
                (len(remote_data) / total_data) * 0.0
            )

        transfer_cost = self._calculate_transfer_cost(
            local_data, rack_local_data, data_center_local_data, remote_data
        )

        return LocalityScore(
            node_id=node_id,
            level=level,
            score=score,
            data_ids=required_data,
            transfer_cost=transfer_cost,
        )

    def _calculate_transfer_cost(
        self,
        local: list[str],
        rack_local: list[str],
        dc_local: list[str],
        remote: list[str]
    ) -> float:
        """Calculate the network transfer cost."""
        cost = 0.0

        for data_id in local:
            cost += self.network_costs["same_node"]

        for data_id in rack_local:
            cost += self.network_costs["same_rack"]

        for data_id in dc_local:
            cost += self.network_costs["same_data_center"]

        for data_id in remote:
            cost += self.network_costs["remote"]

        return cost

    def select_best_node(
        self,
        required_data: list[str],
        available_nodes: list[str] = None
    ) -> Optional[str]:
        """
        Select the best node for a task based on data locality.
        
        Args:
            required_data: List of data IDs required by the task
            available_nodes: List of available node IDs (all if None)
            
        Returns:
            The best node ID or None
        """
        nodes = available_nodes or list(self.nodes.keys())

        if not nodes:
            return None

        scores = []
        for node_id in nodes:
            score = self.calculate_locality_score(node_id, required_data)
            scores.append((node_id, score))

        scores.sort(key=lambda x: (-x[1].score, x[1].transfer_cost))

        best_node, best_score = scores[0]

        self._update_stats(best_score.level)

        return best_node

    def _update_stats(self, level: LocalityLevel):
        """Update locality statistics."""
        if level in (LocalityLevel.PROCESS_LOCAL, LocalityLevel.NODE_LOCAL):
            self._stats["tasks_local"] += 1
        elif level == LocalityLevel.RACK_LOCAL:
            self._stats["tasks_rack_local"] += 1
        else:
            self._stats["tasks_remote"] += 1

        total = (
            self._stats["tasks_local"] +
            self._stats["tasks_rack_local"] +
            self._stats["tasks_remote"]
        )
        if total > 0:
            self._stats["locality_hit_rate"] = (
                self._stats["tasks_local"] / total
            )

    def get_locality_recommendations(
        self,
        required_data: list[str],
        available_nodes: list[str] = None
    ) -> list[LocalityScore]:
        """
        Get locality recommendations for all available nodes.
        
        Args:
            required_data: List of data IDs required by the task
            available_nodes: List of available node IDs
            
        Returns:
            List of LocalityScores sorted by score
        """
        nodes = available_nodes or list(self.nodes.keys())

        scores = [
            self.calculate_locality_score(node_id, required_data)
            for node_id in nodes
        ]

        scores.sort(key=lambda x: (-x.score, x.transfer_cost))
        return scores

    def optimize_data_placement(
        self,
        data_id: str,
        replication_factor: int = 3
    ) -> list[str]:
        """
        Recommend optimal nodes for data placement.
        
        Args:
            data_id: The data ID to place
            replication_factor: Number of replicas
            
        Returns:
            List of recommended node IDs
        """
        current_nodes = self.get_data_nodes(data_id)

        if len(current_nodes) >= replication_factor:
            return current_nodes[:replication_factor]

        needed = replication_factor - len(current_nodes)

        candidates = [
            node_id for node_id in self.nodes.keys()
            if node_id not in current_nodes
        ]

        if not candidates:
            return current_nodes

        selected = []

        if current_nodes:
            first_node = self.nodes.get(current_nodes[0])
            if first_node:
                same_rack = [
                    n for n in candidates
                    if self.nodes.get(n, {}).rack_id == first_node.rack_id
                ]
                same_dc = [
                    n for n in candidates
                    if self.nodes.get(n, {}).data_center == first_node.data_center
                ]

                for n in same_rack:
                    if len(selected) < needed:
                        selected.append(n)

                for n in same_dc:
                    if n not in selected and len(selected) < needed:
                        selected.append(n)

        for n in candidates:
            if n not in selected and len(selected) < needed:
                selected.append(n)

        return current_nodes + selected[:needed]

    def get_stats(self) -> dict[str, Any]:
        """Get locality statistics."""
        return {
            **self._stats,
            "total_nodes": len(self.nodes),
            "total_data_items": len(self.data_locations),
        }

    def get_data_stats(self) -> dict[str, Any]:
        """Get data distribution statistics."""
        stats = {
            "total_data_items": len(self.data_locations),
            "replication_counts": defaultdict(int),
            "total_size_bytes": 0,
        }

        for data_id, locations in self.data_locations.items():
            stats["replication_counts"][len(locations)] += 1
            for loc in locations:
                stats["total_size_bytes"] += loc.size_bytes

        return stats


__all__ = [
    "LocalityLevel",
    "DataType",
    "DataLocation",
    "NodeInfo",
    "LocalityScore",
    "DataLocalityManager",
]
