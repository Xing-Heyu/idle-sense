"""
声誉驱动的调度插件

基于 MeritRank 声誉系统的优先级插件
- 高声誉节点获得调度优先级加成
- 低声誉节点任务受限
"""

from src.core.services.merit_rank_service import MeritRankEngine
from src.infrastructure.scheduler import PriorityPlugin, TaskInfo, NodeInfo


class ReputationPriorityPlugin(PriorityPlugin):
    """
    声誉优先级插件

    基于节点声誉计算调度优先级分数
    """

    def __init__(self, merit_rank_engine: MeritRankEngine):
        """
        初始化声誉优先级插件

        Args:
            merit_rank_engine: MeritRank 声誉引擎实例
        """
        self._merit_rank = merit_rank_engine

    def calculate_score(self, task: TaskInfo, node: NodeInfo) -> float:
        """
        计算任务在节点上的优先级分数

        分数组成:
        - 基础分: 0.5
        - 声誉分: 0.3 * (声誉 / 100)
        - 在线时间分: 0.2 * (如果节点在线)

        Args:
            task: 任务信息
            node: 节点信息

        Returns:
            优先级分数 (0.0 - 1.0)
        """
        score = 0.5

        node_address = node.node_id

        reputation = self._merit_rank.get_reputation(node_address)
        reputation_score = (reputation / 100.0) * 0.3
        score += reputation_score

        if node.is_idle and node.is_available:
            score += 0.2

        scheduling_priority = self._merit_rank.get_scheduling_priority(node_address)
        if scheduling_priority > 0:
            score += (scheduling_priority / 3.0) * 0.1

        return min(score, 1.0)

    def is_node_trusted(self, node_id: str) -> bool:
        """
        检查节点是否可信

        Args:
            node_id: 节点ID

        Returns:
            是否可信
        """
        return self._merit_rank.is_trusted(node_id)


class ReputationPredicate:
    """
    声誉谓词

    检查节点声誉是否满足任务要求
    """

    def __init__(self, merit_rank_engine: MeritRankEngine, min_reputation: float = 40.0):
        """
        初始化声誉谓词

        Args:
            merit_rank_engine: MeritRank 声誉引擎实例
            min_reputation: 最小声誉要求
        """
        self._merit_rank = merit_rank_engine
        self._min_reputation = min_reputation

    def evaluate(self, task: TaskInfo, node: NodeInfo) -> bool:
        """
        评估节点是否满足声誉要求

        Args:
            task: 任务信息
            node: 节点信息

        Returns:
            是否满足要求
        """
        reputation = self._merit_rank.get_reputation(node.node_id)
        return reputation >= self._min_reputation


__all__ = ["ReputationPriorityPlugin", "ReputationPredicate"]
