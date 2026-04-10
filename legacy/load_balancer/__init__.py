"""Load Balancer - Load balancing strategies for distributed nodes."""

from __future__ import annotations

import hashlib
import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class NodeStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"
    UNKNOWN = "unknown"


@dataclass
class Node(Generic[T]):
    id: str
    address: str
    port: int
    weight: float = 1.0
    status: NodeStatus = NodeStatus.HEALTHY
    metadata: dict[str, Any] = field(default_factory=dict)
    connection: T | None = None

    request_count: int = 0
    active_requests: int = 0
    total_response_time: float = 0.0
    last_request_time: float = 0.0
    last_health_check: float = 0.0
    error_count: int = 0

    @property
    def avg_response_time(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.total_response_time / self.request_count

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count

    @property
    def load_score(self) -> float:
        return self.active_requests / max(self.weight, 0.1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "address": self.address,
            "port": self.port,
            "weight": self.weight,
            "status": self.status.value,
            "request_count": self.request_count,
            "active_requests": self.active_requests,
            "avg_response_time": round(self.avg_response_time, 4),
            "error_rate": round(self.error_rate, 4),
            "load_score": round(self.load_score, 4),
        }


class LoadBalancingStrategy(ABC):
    @abstractmethod
    def select(self, nodes: list[Node]) -> Node | None:
        pass

    def reset(self):  # noqa: B027
        pass


class RoundRobinStrategy(LoadBalancingStrategy):
    def __init__(self):
        self._index = 0
        self._lock = threading.Lock()

    def select(self, nodes: list[Node]) -> Node | None:
        healthy_nodes = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if not healthy_nodes:
            return None

        with self._lock:
            node = healthy_nodes[self._index % len(healthy_nodes)]
            self._index += 1

        return node

    def reset(self):
        with self._lock:
            self._index = 0


class WeightedRoundRobinStrategy(LoadBalancingStrategy):
    def __init__(self):
        self._current_weights: dict[str, int] = {}
        self._lock = threading.Lock()

    def select(self, nodes: list[Node]) -> Node | None:
        healthy_nodes = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if not healthy_nodes:
            return None

        with self._lock:
            for node in healthy_nodes:
                if node.id not in self._current_weights:
                    self._current_weights[node.id] = 0

            max_weight = 0
            selected = None

            for node in healthy_nodes:
                self._current_weights[node.id] += int(node.weight * 10)

                if self._current_weights[node.id] > max_weight:
                    max_weight = self._current_weights[node.id]
                    selected = node

            if selected:
                self._current_weights[selected.id] -= sum(int(n.weight * 10) for n in healthy_nodes)

            return selected

    def reset(self):
        with self._lock:
            self._current_weights.clear()


class LeastConnectionsStrategy(LoadBalancingStrategy):
    def select(self, nodes: list[Node]) -> Node | None:
        healthy_nodes = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if not healthy_nodes:
            return None

        return min(healthy_nodes, key=lambda n: n.active_requests)


class WeightedLeastConnectionsStrategy(LoadBalancingStrategy):
    def select(self, nodes: list[Node]) -> Node | None:
        healthy_nodes = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if not healthy_nodes:
            return None

        return min(healthy_nodes, key=lambda n: n.load_score)


class RandomStrategy(LoadBalancingStrategy):
    def select(self, nodes: list[Node]) -> Node | None:
        healthy_nodes = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if not healthy_nodes:
            return None

        return random.choice(healthy_nodes)


class HashStrategy(LoadBalancingStrategy):
    def __init__(self, hash_key: str = "client_ip"):
        self.hash_key = hash_key
        self._key_extractor: Callable | None = None

    def set_key_extractor(self, extractor: Callable[[Any], str]):
        self._key_extractor = extractor

    def select(self, nodes: list[Node], key: str | None = None) -> Node | None:
        healthy_nodes = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if not healthy_nodes:
            return None

        if key is None:
            key = str(time.time())

        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
        index = hash_value % len(healthy_nodes)

        return healthy_nodes[index]


class LeastResponseTimeStrategy(LoadBalancingStrategy):
    def select(self, nodes: list[Node]) -> Node | None:
        healthy_nodes = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if not healthy_nodes:
            return None

        nodes_with_data = [n for n in healthy_nodes if n.request_count > 0]

        if not nodes_with_data:
            return random.choice(healthy_nodes)

        return min(nodes_with_data, key=lambda n: n.avg_response_time)


class AdaptiveStrategy(LoadBalancingStrategy):
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._strategies = [
            LeastConnectionsStrategy(),
            LeastResponseTimeStrategy(),
            WeightedRoundRobinStrategy(),
        ]
        self._strategy_scores: list[float] = [1.0] * len(self._strategies)
        self._current_strategy = 0
        self._request_count = 0
        self._lock = threading.Lock()

    def select(self, nodes: list[Node]) -> Node | None:
        healthy_nodes = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if not healthy_nodes:
            return None

        with self._lock:
            self._request_count += 1

            if self._request_count % self.window_size == 0:
                self._adapt()

            strategy = self._strategies[self._current_strategy]

        return strategy.select(nodes)

    def _adapt(self):
        best_score = max(self._strategy_scores)
        best_index = self._strategy_scores.index(best_score)
        self._current_strategy = best_index

    def record_result(self, success: bool, response_time: float):
        with self._lock:
            if success:
                self._strategy_scores[self._current_strategy] += 1.0 / response_time
            else:
                self._strategy_scores[self._current_strategy] *= 0.9


class LoadBalancer(Generic[T]):
    def __init__(
        self, strategy: LoadBalancingStrategy | None = None, health_check_interval: float = 30.0
    ):
        self.strategy = strategy or RoundRobinStrategy()
        self.health_check_interval = health_check_interval
        self._nodes: dict[str, Node[T]] = {}
        self._lock = threading.RLock()
        self._health_checker: Callable[[Node], bool] | None = None
        self._health_thread: threading.Thread | None = None
        self._running = False

    def add_node(self, node: Node[T]):
        with self._lock:
            self._nodes[node.id] = node

    def remove_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                return True
            return False

    def get_node(self, node_id: str) -> Node[T] | None:
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> list[Node[T]]:
        return list(self._nodes.values())

    def get_healthy_nodes(self) -> list[Node[T]]:
        return [n for n in self._nodes.values() if n.status == NodeStatus.HEALTHY]

    def select_node(self, **kwargs) -> Node[T] | None:
        with self._lock:
            nodes = list(self._nodes.values())

        if hasattr(self.strategy, "select"):
            if isinstance(self.strategy, HashStrategy):
                return self.strategy.select(nodes, kwargs.get("hash_key"))
            return self.strategy.select(nodes)

        return None

    def record_request_start(self, node_id: str):
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.active_requests += 1
                node.request_count += 1
                node.last_request_time = time.time()

    def record_request_end(self, node_id: str, success: bool = True, response_time: float = 0.0):
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.active_requests = max(0, node.active_requests - 1)
                node.total_response_time += response_time

                if not success:
                    node.error_count += 1

    def set_health_checker(self, checker: Callable[[Node], bool]):
        self._health_checker = checker

    def check_health(self, node: Node) -> bool:
        if self._health_checker:
            try:
                return self._health_checker(node)
            except Exception:
                return False

        return node.status == NodeStatus.HEALTHY

    def start_health_checks(self):
        if self._running:
            return

        self._running = True
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

    def stop_health_checks(self):
        self._running = False
        if self._health_thread:
            self._health_thread.join(timeout=5)
            self._health_thread = None

    def _health_check_loop(self):
        while self._running:
            with self._lock:
                nodes = list(self._nodes.values())

            for node in nodes:
                is_healthy = self.check_health(node)
                node.status = NodeStatus.HEALTHY if is_healthy else NodeStatus.UNHEALTHY
                node.last_health_check = time.time()

            time.sleep(self.health_check_interval)

    def drain_node(self, node_id: str):
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.status = NodeStatus.DRAINING

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            nodes = list(self._nodes.values())

            total_requests = sum(n.request_count for n in nodes)
            total_active = sum(n.active_requests for n in nodes)
            total_errors = sum(n.error_count for n in nodes)

            healthy_count = sum(1 for n in nodes if n.status == NodeStatus.HEALTHY)

            return {
                "total_nodes": len(nodes),
                "healthy_nodes": healthy_count,
                "unhealthy_nodes": len(nodes) - healthy_count,
                "total_requests": total_requests,
                "active_requests": total_active,
                "total_errors": total_errors,
                "error_rate": total_errors / max(total_requests, 1),
                "nodes": [n.to_dict() for n in nodes],
            }

    def reset_stats(self):
        with self._lock:
            for node in self._nodes.values():
                node.request_count = 0
                node.active_requests = 0
                node.total_response_time = 0.0
                node.error_count = 0

        self.strategy.reset()


__all__ = [
    "NodeStatus",
    "Node",
    "LoadBalancingStrategy",
    "RoundRobinStrategy",
    "WeightedRoundRobinStrategy",
    "LeastConnectionsStrategy",
    "WeightedLeastConnectionsStrategy",
    "RandomStrategy",
    "HashStrategy",
    "LeastResponseTimeStrategy",
    "AdaptiveStrategy",
    "LoadBalancer",
]
