"""
MeritRank 声誉计算引擎

基于论文: MeritRank: Sybil Tolerant Reputation for Merit-based Tokenomics
Nasrulin et al., arXiv 2025

核心机制:
- 传递衰减: 防止远距离刷分
- 连接衰减: 防止多账号互刷
- 周期衰减: 历史贡献自动过期
"""

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Feedback:
    """反馈数据"""

    from_address: str
    to_address: str
    score: float
    timestamp: float = field(default_factory=time.time)
    distance: int = 1


@dataclass
class ReputationEvent:
    """声誉事件记录"""

    address: str
    event_type: str
    score_change: float
    reason: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class MeritRankEngine:
    """MeritRank 声誉计算引擎"""

    # 衰减参数
    TRANSMISSION_DECAY_FACTOR = 0.8  # 传递衰减系数
    CONNECTION_DECAY_BASE = 10.0  # 连接衰减对数基数（更强衰减）
    PERIOD_DECAY_FACTOR = 0.95  # 周期衰减系数 (每周-5%)
    PERIOD_SECONDS = 86400 * 7  # 1周 (秒)

    # 声誉范围
    MIN_REPUTATION = 0.0
    MAX_REPUTATION = 100.0
    DEFAULT_REPUTATION = 50.0

    def __init__(self):
        self._reputations: dict[str, float] = {}
        self._feedbacks: dict[str, list[Feedback]] = {}
        self._connections: dict[str, set[str]] = {}
        self._reputation_events: list[ReputationEvent] = []
        self._last_decay_time: dict[str, float] = {}

    def _transmission_decay(self, score: float, distance: int) -> float:
        """
        传递衰减函数

        公式: score × (factor^distance)

        作用: 防止远距离刷分，距离越远衰减越大
        """
        return score * (self.TRANSMISSION_DECAY_FACTOR**distance)

    def _connection_decay(self, score: float, connections: int) -> float:
        """
        连接衰减函数

        公式: score × (1 / (connections^1.5))

        作用: 防止多账号互刷，连接数越多单连接权重越低（超指数级衰减）
        """
        if connections <= 0:
            return score
        return score * (1.0 / (connections**1.5))

    def _period_decay(self, score: float, periods: int) -> float:
        """
        周期衰减函数

        公式: score × (factor^periods)

        作用: 历史贡献自动过期，鼓励持续贡献
        """
        return score * (self.PERIOD_DECAY_FACTOR**periods)

    def _calculate_periods(self, address: str) -> int:
        """计算经历的周期数"""
        if address not in self._last_decay_time:
            self._last_decay_time[address] = time.time()
            return 0

        elapsed = time.time() - self._last_decay_time[address]
        periods = int(elapsed / self.PERIOD_SECONDS)

        if periods > 0:
            self._last_decay_time[address] = time.time()

        return periods

    def get_reputation(self, address: str) -> float:
        """获取节点声誉"""
        reputation = self._reputations.get(address, self.DEFAULT_REPUTATION)

        # 应用周期衰减
        periods = self._calculate_periods(address)
        if periods > 0:
            reputation = self._period_decay(reputation, periods)
            self._reputations[address] = reputation

        return reputation

    def add_feedback(self, feedback: Feedback) -> None:
        """添加反馈并更新声誉"""
        if feedback.to_address not in self._feedbacks:
            self._feedbacks[feedback.to_address] = []

        self._feedbacks[feedback.to_address].append(feedback)

        # 更新连接关系
        if feedback.to_address not in self._connections:
            self._connections[feedback.to_address] = set()
        self._connections[feedback.to_address].add(feedback.from_address)

        self._calculate_reputation(feedback.to_address)

    def _calculate_reputation(self, address: str) -> None:
        """计算并更新节点声誉"""
        if address not in self._feedbacks:
            return

        total_score = self.DEFAULT_REPUTATION
        feedbacks = self._feedbacks[address]
        connections = len(self._connections.get(address, set()))

        for feedback in feedbacks:
            # 应用传递衰减
            transmission_score = self._transmission_decay(feedback.score, feedback.distance)

            # 应用连接衰减
            connection_score = self._connection_decay(transmission_score, connections)

            total_score += connection_score

        # 限制声誉范围
        reputation = max(self.MIN_REPUTATION, min(self.MAX_REPUTATION, total_score))

        old_reputation = self._reputations.get(address, self.DEFAULT_REPUTATION)
        change = reputation - old_reputation

        # 记录声誉变化事件
        if abs(change) > 0.01:
            self._reputation_events.append(
                ReputationEvent(
                    address=address,
                    event_type="reputation_update",
                    score_change=change,
                    reason="feedback_update",
                    metadata={
                        "old_reputation": old_reputation,
                        "new_reputation": reputation,
                        "feedback_count": len(feedbacks),
                    },
                )
            )

        self._reputations[address] = reputation

    def record_task_completion(
        self, node_address: str, requester_address: str, quality_score: float = 1.0
    ) -> None:
        """
        记录任务完成，更新声誉

        Args:
            node_address: 执行任务的节点地址
            requester_address: 请求者地址
            quality_score: 任务质量评分 (0.0-1.0)
        """
        base_score = 5.0 * quality_score

        feedback = Feedback(
            from_address=requester_address, to_address=node_address, score=base_score, distance=1
        )

        self.add_feedback(feedback)

    def record_task_failure(
        self, node_address: str, requester_address: str, penalty_score: float = -10.0
    ) -> None:
        """
        记录任务失败，惩罚声誉

        Args:
            node_address: 执行任务的节点地址
            requester_address: 请求者地址
            penalty_score: 惩罚分数 (负数)
        """
        feedback = Feedback(
            from_address=requester_address, to_address=node_address, score=penalty_score, distance=1
        )

        self.add_feedback(feedback)

    def record_uptime_reward(
        self, node_address: str, uptime_minutes: int, base_reward_per_minute: float = 0.1
    ) -> None:
        """
        记录在线时间奖励

        Args:
            node_address: 节点地址
            uptime_minutes: 在线分钟数
            base_reward_per_minute: 每分钟基础奖励
        """
        if uptime_minutes < 60:
            return

        reward = base_reward_per_minute * uptime_minutes

        feedback = Feedback(
            from_address="system", to_address=node_address, score=reward, distance=1
        )

        self.add_feedback(feedback)

    def get_reputation_tier(self, reputation: float) -> str:
        """
        获取声誉等级

        等级映射:
        - Platinum: ≥90 (调度优先级 +3)
        - Gold: ≥75 (调度优先级 +2)
        - Silver: ≥60 (调度优先级 +1)
        - Bronze: ≥40 (调度优先级 +0)
        - Untrusted: <40 (任务限制)
        """
        if reputation >= 90:
            return "Platinum"
        elif reputation >= 75:
            return "Gold"
        elif reputation >= 60:
            return "Silver"
        elif reputation >= 40:
            return "Bronze"
        else:
            return "Untrusted"

    def get_scheduling_priority(self, address: str) -> int:
        """
        获取调度优先级加成

        Returns:
            优先级加成 (0-3)
        """
        reputation = self.get_reputation(address)
        tier = self.get_reputation_tier(reputation)

        tier_priorities = {"Platinum": 3, "Gold": 2, "Silver": 1, "Bronze": 0, "Untrusted": -1}

        return tier_priorities.get(tier, 0)

    def is_trusted(self, address: str) -> bool:
        """检查节点是否可信"""
        reputation = self.get_reputation(address)
        return reputation >= 40.0

    def get_reputation_events(
        self, address: Optional[str] = None, limit: int = 100
    ) -> list[ReputationEvent]:
        """获取声誉事件历史"""
        events = self._reputation_events[-limit:]

        if address:
            events = [e for e in events if e.address == address]

        return events

    def get_stats(self) -> dict[str, Any]:
        """获取声誉系统统计"""
        addresses = list(self._reputations.keys())

        if not addresses:
            return {"total_accounts": 0, "avg_reputation": 0.0, "tier_distribution": {}}

        reputations = [self.get_reputation(a) for a in addresses]
        avg_reputation = sum(reputations) / len(reputations)

        tier_counts: dict[str, int] = {}
        for rep in reputations:
            tier = self.get_reputation_tier(rep)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        return {
            "total_accounts": len(addresses),
            "avg_reputation": avg_reputation,
            "min_reputation": min(reputations),
            "max_reputation": max(reputations),
            "tier_distribution": tier_counts,
            "total_feedbacks": sum(len(f) for f in self._feedbacks.values()),
            "total_events": len(self._reputation_events),
        }

    def simulate_sybil_attack(
        self, attacker_count: int = 100, fake_score: float = 5.0
    ) -> dict[str, Any]:
        """
        模拟女巫攻击测试

        展示 MeritRank 的抗女巫攻击效果

        Returns:
            攻击结果统计
        """
        victim_address = "victim"
        initial_reputation = self.DEFAULT_REPUTATION
        self._reputations[victim_address] = initial_reputation
        self._connections[victim_address] = set()
        self._feedbacks[victim_address] = []

        total_score_without_decay = 0.0
        total_score_with_decay = 0.0

        for i in range(attacker_count):
            attacker_address = f"attacker_{i}"
            feedback = Feedback(
                from_address=attacker_address,
                to_address=victim_address,
                score=fake_score,
                distance=1,
            )
            total_score_without_decay += fake_score

            connections = len(self._connections.get(victim_address, set())) + 1
            transmission_score = self._transmission_decay(fake_score, 1)
            connection_score = self._connection_decay(transmission_score, connections)
            total_score_with_decay += connection_score

            self._connections[victim_address].add(attacker_address)
            self._feedbacks[victim_address].append(feedback)

        final_reputation = initial_reputation + total_score_with_decay
        final_reputation = max(self.MIN_REPUTATION, min(self.MAX_REPUTATION, final_reputation))

        self._reputations[victim_address] = final_reputation

        effectiveness = (
            (final_reputation - initial_reputation) / total_score_without_decay
            if total_score_without_decay > 0
            else 0.0
        )

        return {
            "attacker_count": attacker_count,
            "fake_score_per_attacker": fake_score,
            "total_fake_score": total_score_without_decay,
            "effective_score": total_score_with_decay,
            "final_reputation": final_reputation,
            "reputation_increase": final_reputation - initial_reputation,
            "effectiveness": effectiveness,
            "decay_ratio": (
                total_score_with_decay / total_score_without_decay
                if total_score_without_decay > 0
                else 0.0
            ),
        }


__all__ = ["MeritRankEngine", "Feedback", "ReputationEvent"]
