"""
代币经济服务

封装 legacy.token_economy 模块，提供统一的业务接口
"""

from typing import Any, Optional

from config.settings import settings
from legacy.token_economy import (
    Account,
    PricingEngine,
    ResourceMetrics,
    TokenEconomy,
)


class TokenEconomyService:
    """
    代币经济服务

    封装代币经济系统的核心功能，提供业务层接口

    Examples:
        >>> service = TokenEconomyService()
        >>> account = service.get_or_create_account("user_123")
        >>> print(f"Balance: {account.balance}")
    """

    def __init__(self, token_economy: Optional[TokenEconomy] = None):
        """
        初始化代币经济服务

        Args:
            token_economy: TokenEconomy 实例（可选，默认创建新实例）
        """
        self._economy = token_economy or TokenEconomy()
        self._initial_balance = settings.TOKEN.INITIAL_BALANCE

    @property
    def economy(self) -> TokenEconomy:
        """获取底层 TokenEconomy 实例"""
        return self._economy

    @property
    def pricing(self) -> PricingEngine:
        """获取定价引擎"""
        return self._economy.pricing

    @property
    def reputation(self):
        """获取声誉系统"""
        return self._economy.reputation

    def get_or_create_account(self, user_id: str) -> Account:
        """
        获取或创建用户账户

        Args:
            user_id: 用户ID

        Returns:
            用户账户
        """
        account = self._economy.get_account(user_id)
        if not account:
            account = self._economy.create_account(user_id, initial_balance=self._initial_balance)
        return account

    def get_account_info(self, user_id: str) -> dict[str, Any]:
        """
        获取账户信息

        Args:
            user_id: 用户ID

        Returns:
            账户信息字典
        """
        account = self.get_or_create_account(user_id)
        return {
            "balance": account.balance,
            "staked": account.staked,
            "locked": account.locked,
            "reputation": account.reputation,
            "total_earned": account.total_earned,
            "total_spent": account.total_spent,
            "tasks_completed": account.tasks_completed,
            "tasks_failed": account.tasks_failed,
            "tier": self._economy.reputation.get_reputation_tier(account.reputation),
        }

    def estimate_task_cost(
        self, cpu: float, memory: int, timeout: int, priority: float = 0.0
    ) -> dict[str, Any]:
        """
        估算任务成本

        Args:
            cpu: CPU 核心数
            memory: 内存大小（MB）
            timeout: 超时时间（秒）
            priority: 优先级

        Returns:
            成本估算信息
        """
        resources = ResourceMetrics(
            cpu_seconds=cpu * timeout, memory_gb_seconds=(memory / 1024) * timeout
        )

        base_price = self._economy.pricing.calculate_price(resources, priority=priority)
        congestion = self._economy.pricing.get_market_stats()["congestion_level"]

        return {
            "base_price": round(base_price, 4),
            "congestion_factor": round(congestion, 2),
            "final_price": round(base_price * congestion, 4),
            "priority_fee": round(base_price * 0.1 * priority, 4) if priority > 0 else 0,
        }

    def stake_tokens(self, user_id: str, amount: float) -> tuple[bool, dict[str, Any]]:
        """
        质押代币

        Args:
            user_id: 用户ID
            amount: 质押数量

        Returns:
            (是否成功, 结果信息)
        """
        try:
            success, tx = self._economy.stake(user_id, amount)
            if success:
                return True, {
                    "amount": amount,
                    "message": f"成功质押 {amount} CMP",
                    "tx_id": tx.tx_id if tx else None,
                }
            return False, {"error": "质押失败"}
        except Exception as e:
            return False, {"error": str(e)}

    def unstake_tokens(self, user_id: str, amount: float) -> tuple[bool, dict[str, Any]]:
        """
        解除质押

        Args:
            user_id: 用户ID
            amount: 解除数量

        Returns:
            (是否成功, 结果信息)
        """
        try:
            unstaked, tx = self._economy.unstake(user_id, amount)
            if unstaked > 0:
                return True, {
                    "amount": unstaked,
                    "message": f"成功解除质押 {unstaked} CMP",
                    "tx_id": tx.tx_id if tx else None,
                }
            return False, {"error": "没有可解除的质押"}
        except Exception as e:
            return False, {"error": str(e)}

    def reward_node_uptime(
        self, node_id: str, uptime_seconds: float, capacity: Optional[dict[str, Any]] = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        奖励节点在线时间

        Args:
            node_id: 节点ID
            uptime_seconds: 在线时间（秒）
            capacity: 节点容量信息

        Returns:
            (是否成功, 奖励信息)
        """
        return self._economy.reward_node_uptime(
            node_id=node_id, uptime_seconds=uptime_seconds, capacity=capacity or {}
        )

    def get_node_earnings(self, node_id: str) -> dict[str, Any]:
        """
        获取节点收益信息

        Args:
            node_id: 节点ID

        Returns:
            收益信息
        """
        return self._economy.get_node_earnings(node_id)

    def get_system_stats(self) -> dict[str, Any]:
        """
        获取系统统计信息

        Returns:
            系统统计
        """
        return self._economy.get_stats()

    def get_transaction_history(self, user_id: Optional[str] = None, limit: int = 100) -> list:
        """
        获取交易历史

        Args:
            user_id: 用户ID（可选）
            limit: 返回记录数量限制

        Returns:
            交易历史列表
        """
        transactions = self._economy.get_transaction_history(user_id, limit)
        return [tx.to_dict() for tx in transactions]


__all__ = ["TokenEconomyService"]
