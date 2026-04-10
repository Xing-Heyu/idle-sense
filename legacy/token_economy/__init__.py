"""
Token Economy Module - Incentive Mechanism for Distributed Computing.

Implements:
- Token system for resource accounting
- Pricing mechanism based on resource consumption
- Reward system for task completion
- Staking mechanism for security deposits
- Reputation system for trust scoring
- Payment settlement for task rewards

References:
- Ethereum Gas Mechanism (EIP-1559)
- Filecoin Proof-of-Replication/Proof-of-Spacetime
- Golem Network Token (GLM) Economics
- Buterin, "A Next-Generation Smart Contract Platform" (2014)
"""

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TokenType(Enum):
    NATIVE = "native"
    REWARD = "reward"
    STAKE = "stake"
    PENALTY = "penalty"


class TransactionType(Enum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    STAKE = "stake"
    UNSTAKE = "unstake"
    REWARD = "reward"
    PENALTY = "penalty"
    TRANSFER = "transfer"
    TASK_PAYMENT = "task_payment"


class ReputationAction(Enum):
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_TIMEOUT = "task_timeout"
    MALICIOUS_BEHAVIOR = "malicious_behavior"
    UPTIME_GOOD = "uptime_good"
    UPTIME_POOR = "uptime_poor"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"


@dataclass
class ResourceMetrics:
    cpu_seconds: float = 0.0
    memory_gb_seconds: float = 0.0
    storage_gb: float = 0.0
    network_gb: float = 0.0
    gpu_seconds: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "cpu_seconds": self.cpu_seconds,
            "memory_gb_seconds": self.memory_gb_seconds,
            "storage_gb": self.storage_gb,
            "network_gb": self.network_gb,
            "gpu_seconds": self.gpu_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "ResourceMetrics":
        return cls(
            cpu_seconds=data.get("cpu_seconds", 0.0),
            memory_gb_seconds=data.get("memory_gb_seconds", 0.0),
            storage_gb=data.get("storage_gb", 0.0),
            network_gb=data.get("network_gb", 0.0),
            gpu_seconds=data.get("gpu_seconds", 0.0),
        )


@dataclass
class Transaction:
    tx_id: str
    tx_type: TransactionType
    from_address: str
    to_address: str
    amount: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "tx_type": self.tx_type.value,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transaction":
        return cls(
            tx_id=data["tx_id"],
            tx_type=TransactionType(data["tx_type"]),
            from_address=data["from_address"],
            to_address=data["to_address"],
            amount=data["amount"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Account:
    address: str
    balance: float = 0.0
    staked: float = 0.0
    locked: float = 0.0
    reputation: float = 50.0
    total_earned: float = 0.0
    total_spent: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "balance": self.balance,
            "staked": self.staked,
            "locked": self.locked,
            "reputation": self.reputation,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Account":
        return cls(
            address=data["address"],
            balance=data.get("balance", 0.0),
            staked=data.get("staked", 0.0),
            locked=data.get("locked", 0.0),
            reputation=data.get("reputation", 50.0),
            total_earned=data.get("total_earned", 0.0),
            total_spent=data.get("total_spent", 0.0),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_failed=data.get("tasks_failed", 0),
            created_at=data.get("created_at", time.time()),
        )


class PricingEngine:
    """Pricing engine for computing resources.

    Based on Ethereum EIP-1559 gas mechanism with base fee and priority fee.
    """

    BASE_CPU_PRICE = 0.001  # Token per CPU second
    BASE_MEMORY_PRICE = 0.0001  # Token per GB-second
    BASE_STORAGE_PRICE = 0.01  # Token per GB
    BASE_NETWORK_PRICE = 0.005  # Token per GB
    BASE_GPU_PRICE = 0.01  # Token per GPU second

    PRIORITY_FEE_MULTIPLIER = 0.1  # 10% priority fee
    NETWORK_CONGESTION_FACTOR = 1.0

    def __init__(self):
        self._congestion_level = 1.0
        self._demand_history: list[float] = []
        self._supply_history: list[float] = []

    def update_congestion(self, demand: float, supply: float):
        self._demand_history.append(demand)
        self._supply_history.append(supply)

        if len(self._demand_history) > 100:
            self._demand_history.pop(0)
            self._supply_history.pop(0)

        if supply > 0:
            ratio = demand / supply
            self._congestion_level = max(0.5, min(5.0, ratio))

    def calculate_price(
        self, resources: ResourceMetrics, priority: int = 0, urgency_multiplier: float = 1.0
    ) -> float:
        base_cost = (
            resources.cpu_seconds * self.BASE_CPU_PRICE
            + resources.memory_gb_seconds * self.BASE_MEMORY_PRICE
            + resources.storage_gb * self.BASE_STORAGE_PRICE
            + resources.network_gb * self.BASE_NETWORK_PRICE
            + resources.gpu_seconds * self.BASE_GPU_PRICE
        )

        congestion_cost = base_cost * self._congestion_level

        priority_fee = congestion_cost * self.PRIORITY_FEE_MULTIPLIER * (1 + priority * 0.1)

        total = (congestion_cost + priority_fee) * urgency_multiplier

        return float(round(total, 6))

    def estimate_resources(
        self,
        task_complexity: str = "medium",
        estimated_duration: float = 60.0,
        memory_requirement: float = 1.0,
        storage_requirement: float = 0.1,
        network_requirement: float = 0.01,
        gpu_required: bool = False,
    ) -> ResourceMetrics:
        complexity_multipliers = {
            "low": 0.5,
            "medium": 1.0,
            "high": 2.0,
            "extreme": 5.0,
        }

        multiplier = complexity_multipliers.get(task_complexity, 1.0)

        return ResourceMetrics(
            cpu_seconds=estimated_duration * multiplier,
            memory_gb_seconds=memory_requirement * estimated_duration,
            storage_gb=storage_requirement,
            network_gb=network_requirement,
            gpu_seconds=estimated_duration * multiplier if gpu_required else 0,
        )

    def get_market_stats(self) -> dict[str, Any]:
        return {
            "congestion_level": self._congestion_level,
            "base_prices": {
                "cpu_per_second": self.BASE_CPU_PRICE,
                "memory_per_gb_second": self.BASE_MEMORY_PRICE,
                "storage_per_gb": self.BASE_STORAGE_PRICE,
                "network_per_gb": self.BASE_NETWORK_PRICE,
                "gpu_per_second": self.BASE_GPU_PRICE,
            },
            "demand_avg": (
                sum(self._demand_history) / len(self._demand_history) if self._demand_history else 0
            ),
            "supply_avg": (
                sum(self._supply_history) / len(self._supply_history) if self._supply_history else 0
            ),
        }


class ReputationSystem:
    """Reputation system for trust scoring.

    Based on EigenTrust algorithm and PageRank-style reputation propagation.
    """

    MIN_REPUTATION = 0.0
    MAX_REPUTATION = 100.0
    DEFAULT_REPUTATION = 50.0

    REPUTATION_DECAY = 0.99
    REPUTATION_GAIN_MULTIPLIER = 1.0
    REPUTATION_LOSS_MULTIPLIER = 2.0

    ACTION_SCORES = {
        ReputationAction.TASK_COMPLETED: 5.0,
        ReputationAction.TASK_FAILED: -10.0,
        ReputationAction.TASK_TIMEOUT: -5.0,
        ReputationAction.MALICIOUS_BEHAVIOR: -50.0,
        ReputationAction.UPTIME_GOOD: 1.0,
        ReputationAction.UPTIME_POOR: -2.0,
        ReputationAction.VERIFICATION_PASSED: 3.0,
        ReputationAction.VERIFICATION_FAILED: -15.0,
    }

    def __init__(self):
        self._reputation_history: dict[str, list[tuple[float, ReputationAction]]] = {}

    def update_reputation(
        self, account: Account, action: ReputationAction, weight: float = 1.0
    ) -> float:
        base_score = self.ACTION_SCORES.get(action, 0.0)

        if base_score > 0:
            score = base_score * self.REPUTATION_GAIN_MULTIPLIER * weight
        else:
            score = base_score * self.REPUTATION_LOSS_MULTIPLIER * weight

        reputation_factor = account.reputation / self.DEFAULT_REPUTATION
        adjusted_score = score * (1.0 / max(0.1, reputation_factor))

        new_reputation = account.reputation + adjusted_score
        new_reputation = max(self.MIN_REPUTATION, min(self.MAX_REPUTATION, new_reputation))

        account.reputation = new_reputation

        if account.address not in self._reputation_history:
            self._reputation_history[account.address] = []
        self._reputation_history[account.address].append((time.time(), action))

        if action == ReputationAction.TASK_COMPLETED:
            account.tasks_completed += 1
        elif action in [ReputationAction.TASK_FAILED, ReputationAction.TASK_TIMEOUT]:
            account.tasks_failed += 1

        return new_reputation

    def decay_reputation(self, account: Account) -> float:
        if account.reputation > self.DEFAULT_REPUTATION:
            account.reputation = (
                self.DEFAULT_REPUTATION
                + (account.reputation - self.DEFAULT_REPUTATION) * self.REPUTATION_DECAY
            )
        return account.reputation

    def get_trust_score(self, account: Account) -> float:
        base_trust = account.reputation / 100.0

        total_tasks = account.tasks_completed + account.tasks_failed
        success_rate = account.tasks_completed / total_tasks if total_tasks > 0 else 0.5

        trust_score = base_trust * 0.6 + success_rate * 0.4

        return min(1.0, max(0.0, trust_score))

    def get_reputation_tier(self, reputation: float) -> str:
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

    def get_history(self, address: str, limit: int = 100) -> list[tuple[float, str]]:
        history = self._reputation_history.get(address, [])
        return [(ts, action.value) for ts, action in history[-limit:]]

    def get_reputation(
        self, address: str, accounts: Optional[dict[str, "Account"]] = None
    ) -> float:
        """Get reputation score for an address."""
        if accounts and address in accounts:
            return accounts[address].reputation
        return self.DEFAULT_REPUTATION


class StakingManager:
    """Staking manager for security deposits.

    Implements Proof-of-Stake style security mechanism.
    """

    MIN_STAKE = 10.0
    STAKE_LOCK_PERIOD = 86400  # 24 hours in seconds
    SLASH_PERCENTAGE = 0.1  # 10% slash for violations

    def __init__(self):
        self._stakes: dict[str, dict[str, Any]] = {}
        self._slash_events: list[dict[str, Any]] = []

    def stake(self, account: Account, amount: float) -> bool:
        if amount < self.MIN_STAKE:
            return False

        if account.balance < amount:
            return False

        account.balance -= amount
        account.staked += amount

        stake_id = hashlib.sha256(f"{account.address}:{time.time()}".encode()).hexdigest()[:16]

        self._stakes[stake_id] = {
            "address": account.address,
            "amount": amount,
            "staked_at": time.time(),
            "unlock_at": time.time() + self.STAKE_LOCK_PERIOD,
            "status": "active",
        }

        return True

    def unstake(self, account: Account, amount: Optional[float] = None) -> float:
        unstaked = 0.0

        for _stake_id, stake in list(self._stakes.items()):
            if stake["address"] != account.address:
                continue
            if stake["status"] != "active":
                continue
            if time.time() < stake["unlock_at"]:
                continue

            unstake_amount = (
                stake["amount"] if amount is None else min(amount - unstaked, stake["amount"])
            )

            if unstake_amount <= 0:
                continue

            account.staked -= unstake_amount
            account.balance += unstake_amount
            unstaked += unstake_amount

            stake["amount"] -= unstake_amount
            if stake["amount"] <= 0:
                stake["status"] = "withdrawn"

            if amount is not None and unstaked >= amount:
                break

        return unstaked

    def slash(self, account: Account, reason: str, percentage: Optional[float] = None) -> float:
        percentage = percentage or self.SLASH_PERCENTAGE

        slash_amount = account.staked * percentage
        slash_amount = min(slash_amount, account.staked)

        if slash_amount <= 0:
            return 0.0

        account.staked -= slash_amount

        self._slash_events.append(
            {
                "address": account.address,
                "amount": slash_amount,
                "reason": reason,
                "timestamp": time.time(),
            }
        )

        return slash_amount

    def get_stake_info(self, address: str) -> dict[str, Any]:
        total_staked = 0.0
        active_stakes = []

        for stake_id, stake in self._stakes.items():
            if stake["address"] == address:
                total_staked += stake["amount"]
                active_stakes.append(
                    {
                        "stake_id": stake_id,
                        "amount": stake["amount"],
                        "staked_at": stake["staked_at"],
                        "unlock_at": stake["unlock_at"],
                        "status": stake["status"],
                    }
                )

        return {
            "total_staked": total_staked,
            "active_stakes": active_stakes,
            "slash_count": sum(1 for e in self._slash_events if e["address"] == address),
        }


_PERSISTENCE_ENABLED = os.getenv("TOKEN_ECONOMY_PERSISTENCE", "true").lower() in (
    "true",
    "1",
    "yes",
)


class TokenEconomyPersistenceAdapter:
    """Bridge between synchronous TokenEconomy and asynchronous SQLiteTokenRepository.

    Wraps SQLiteTokenRepository to provide a sync interface that TokenEconomy
    can call. All async operations are internally resolved via asyncio.
    """

    def __init__(self, repository):
        self._repo = repository
        self._enabled = _PERSISTENCE_ENABLED
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stake_id_map: dict[str, int] = {}

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run_async(self, coro):
        if not self._enabled:
            return None
        try:
            loop = self._get_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(coro)
        except Exception:
            return None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def ensure_account(self, address: str) -> Optional[Any]:
        return self._run_async(self._repo.get_or_create_account(address))

    def persist_reward(
        self,
        to_address: str,
        amount: float,
        from_address: str = "treasury",
        reward_type: str = "reward",
    ) -> Optional[Any]:
        return self._run_async(
            self._repo.add_transaction(
                to_user_id=to_address,
                amount=amount,
                tx_type="reward",
                from_user_id=from_address,
                description=f"token_economy:{reward_type}",
            )
        )

    def persist_transfer(
        self, from_address: str, to_address: str, amount: float, tx_type: str = "transfer"
    ) -> Optional[Any]:
        return self._run_async(
            self._repo.transfer(
                from_user_id=from_address,
                to_user_id=to_address,
                amount=amount,
                tx_type=tx_type,
            )
        )

    def persist_deposit(self, address: str, amount: float) -> Optional[Any]:
        return self._run_async(
            self._repo.add_transaction(
                to_user_id=address,
                amount=amount,
                tx_type="deposit",
                description="token_economy:deposit",
            )
        )

    def persist_withdraw(self, address: str, amount: float) -> Optional[Any]:
        return self._run_async(
            self._repo.transfer(
                from_user_id=address,
                to_user_id="external",
                amount=amount,
                tx_type="withdraw",
            )
        )

    def persist_stake(self, address: str, amount: float) -> Optional[Any]:
        result = self._run_async(self._repo.stake(address, amount))
        if result and hasattr(result, "id"):
            self._stake_id_map[address] = result.id
        return result

    def persist_unstake(self, address: str) -> Optional[Any]:
        stake_id = self._stake_id_map.get(address)
        if stake_id is None:
            return None
        try:
            result = self._run_async(self._repo.unstake(stake_id))
            if result:
                self._stake_id_map.pop(address, None)
            return result
        except Exception:
            return None

    def get_persisted_balance(self, address: str) -> Optional[float]:
        result = self._run_async(self._repo.get_balance(address))
        return result

    def close(self):
        self._run_async(self._repo.close())


class TokenEconomy:
    """Main token economy system for distributed computing platform.

    Combines pricing, reputation, staking, and payment systems.
    """

    TOKEN_NAME = "ComputeToken"
    TOKEN_SYMBOL = "CMP"
    INITIAL_SUPPLY = 1_000_000_000.0

    def __init__(self, repository=None):
        self.pricing = PricingEngine()
        self.reputation = ReputationSystem()
        self.staking = StakingManager()

        self._accounts: dict[str, Account] = {}
        self._transactions: list[Transaction] = []
        self._task_payments: dict[str, dict[str, Any]] = {}
        self._total_supply = self.INITIAL_SUPPLY
        self._treasury_address = "treasury"

        self._persistence: Optional[TokenEconomyPersistenceAdapter] = None
        if repository is not None:
            self._persistence = TokenEconomyPersistenceAdapter(repository)

        self._create_account(self._treasury_address)
        self._accounts[self._treasury_address].balance = self.INITIAL_SUPPLY

        if self._persistence:
            self._persistence.ensure_account(self._treasury_address)

    def _generate_tx_id(self) -> str:
        return hashlib.sha256(f"{time.time()}:{len(self._transactions)}".encode()).hexdigest()[:16]

    def _create_account(self, address: str) -> Account:
        if address not in self._accounts:
            self._accounts[address] = Account(address=address)
            if self._persistence:
                self._persistence.ensure_account(address)
        return self._accounts[address]

    def get_account(self, address: str) -> Optional[Account]:
        return self._accounts.get(address)

    def create_account(self, address: str, initial_balance: float = 0.0) -> Account:
        account = self._create_account(address)

        if initial_balance > 0:
            self._transfer(self._treasury_address, address, initial_balance)

        return account

    def _transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Transaction:
        from_account = self._accounts.get(from_address)
        to_account = self._create_account(to_address)

        if from_account and from_account.balance < amount:
            raise ValueError(f"Insufficient balance: {from_account.balance} < {amount}")

        if from_account:
            from_account.balance -= amount
            from_account.total_spent += amount

        to_account.balance += amount
        to_account.total_earned += amount

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.TRANSFER,
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            metadata=metadata or {},
        )

        self._transactions.append(tx)

        if self._persistence and from_account:
            self._persistence.persist_transfer(from_address, to_address, amount, tx_type="transfer")

        return tx

    def deposit(self, address: str, amount: float) -> Transaction:
        account = self._create_account(address)

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.DEPOSIT,
            from_address="external",
            to_address=address,
            amount=amount,
        )

        account.balance += amount
        self._transactions.append(tx)

        if self._persistence:
            self._persistence.persist_deposit(address, amount)

        return tx

    def withdraw(self, address: str, amount: float) -> Transaction:
        account = self.get_account(address)
        if not account or account.balance < amount:
            raise ValueError("Insufficient balance for withdrawal")

        account.balance -= amount

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.WITHDRAW,
            from_address=address,
            to_address="external",
            amount=amount,
        )

        self._transactions.append(tx)

        if self._persistence:
            self._persistence.persist_withdraw(address, amount)

        return tx

    def stake(self, address: str, amount: float) -> tuple[bool, Optional[Transaction]]:
        account = self.get_account(address)
        if not account:
            return False, None

        success = self.staking.stake(account, amount)
        if not success:
            return False, None

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.STAKE,
            from_address=address,
            to_address="staking",
            amount=amount,
        )

        self._transactions.append(tx)
        if self._persistence:
            self._persistence.persist_stake(address, amount)
        return True, tx

    def unstake(
        self, address: str, amount: Optional[float] = None
    ) -> tuple[float, Optional[Transaction]]:
        account = self.get_account(address)
        if not account:
            return 0.0, None

        unstaked = self.staking.unstake(account, amount)
        if unstaked <= 0:
            return 0.0, None

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.UNSTAKE,
            from_address="staking",
            to_address=address,
            amount=unstaked,
        )

        self._transactions.append(tx)
        if self._persistence:
            self._persistence.persist_unstake(address)
        return unstaked, tx

    def create_task_payment(
        self,
        task_id: str,
        requester: str,
        total_budget: float,
        resources: ResourceMetrics,
        priority: int = 0,
    ) -> dict[str, Any]:
        estimated_price = self.pricing.calculate_price(resources, priority)

        if estimated_price > total_budget:
            raise ValueError(f"Estimated price {estimated_price} exceeds budget {total_budget}")

        account = self.get_account(requester)
        if not account or account.balance < total_budget:
            raise ValueError("Insufficient balance for task")

        account.balance -= total_budget
        account.locked += total_budget

        payment_info = {
            "task_id": task_id,
            "requester": requester,
            "total_budget": total_budget,
            "estimated_price": estimated_price,
            "priority": priority,
            "resources": resources.to_dict(),
            "status": "pending",
            "created_at": time.time(),
            "workers": [],
            "total_paid": 0.0,
        }

        self._task_payments[task_id] = payment_info

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.TASK_PAYMENT,
            from_address=requester,
            to_address="escrow",
            amount=total_budget,
            metadata={"task_id": task_id},
        )

        self._transactions.append(tx)

        return payment_info

    def reward_worker(
        self,
        task_id: str,
        worker_address: str,
        actual_resources: ResourceMetrics,
        quality_score: float = 1.0,
    ) -> tuple[float, Optional[Transaction]]:
        payment_info = self._task_payments.get(task_id)
        if not payment_info:
            return 0.0, None

        base_reward = self.pricing.calculate_price(actual_resources, payment_info["priority"])

        adjusted_reward = base_reward * quality_score

        remaining_budget = payment_info["total_budget"] - payment_info["total_paid"]
        actual_reward = min(adjusted_reward, remaining_budget)

        if actual_reward <= 0:
            return 0.0, None

        worker_account = self._create_account(worker_address)
        worker_account.balance += actual_reward
        worker_account.total_earned += actual_reward

        payment_info["total_paid"] += actual_reward
        payment_info["workers"].append(
            {
                "address": worker_address,
                "reward": actual_reward,
                "resources": actual_resources.to_dict(),
                "quality_score": quality_score,
                "timestamp": time.time(),
            }
        )

        requester_account = self._accounts.get(payment_info["requester"])
        if requester_account:
            requester_account.locked -= actual_reward

        self.reputation.update_reputation(
            worker_account, ReputationAction.TASK_COMPLETED, weight=quality_score
        )

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.REWARD,
            from_address="escrow",
            to_address=worker_address,
            amount=actual_reward,
            metadata={"task_id": task_id, "quality_score": quality_score},
        )

        self._transactions.append(tx)

        if self._persistence:
            self._persistence.persist_reward(
                to_address=worker_address,
                amount=actual_reward,
                from_address="escrow",
                reward_type="task_reward",
            )

        return actual_reward, tx

    def penalize_worker(
        self, task_id: str, worker_address: str, reason: str, penalty_percentage: float = 0.1
    ) -> tuple[float, Optional[Transaction]]:
        worker_account = self.get_account(worker_address)
        if not worker_account:
            return 0.0, None

        slash_amount = self.staking.slash(worker_account, reason, penalty_percentage)

        if slash_amount > 0:
            action = (
                ReputationAction.MALICIOUS_BEHAVIOR
                if "malicious" in reason.lower()
                else ReputationAction.TASK_FAILED
            )
            self.reputation.update_reputation(worker_account, action)

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.PENALTY,
            from_address=worker_address,
            to_address="treasury",
            amount=slash_amount,
            metadata={"task_id": task_id, "reason": reason},
        )

        self._transactions.append(tx)

        return slash_amount, tx

    def finalize_task(self, task_id: str) -> dict[str, Any]:
        payment_info = self._task_payments.get(task_id)
        if not payment_info:
            return {}

        remaining = payment_info["total_budget"] - payment_info["total_paid"]

        if remaining > 0:
            requester_account = self._accounts.get(payment_info["requester"])
            if requester_account:
                requester_account.balance += remaining
                requester_account.locked -= remaining

        payment_info["status"] = "completed"

        return payment_info

    def get_balance(self, address: str) -> float:
        account = self.get_account(address)
        return account.balance if account else 0.0

    def get_transaction_history(
        self, address: Optional[str] = None, limit: int = 100
    ) -> list[Transaction]:
        if address:
            transactions = [
                tx
                for tx in self._transactions
                if tx.from_address == address or tx.to_address == address
            ]
        else:
            transactions = self._transactions.copy()

        return transactions[-limit:]

    def get_stats(self) -> dict[str, Any]:
        total_balance = sum(acc.balance for acc in self._accounts.values())
        total_staked = sum(acc.staked for acc in self._accounts.values())
        total_locked = sum(acc.locked for acc in self._accounts.values())

        return {
            "token_name": self.TOKEN_NAME,
            "token_symbol": self.TOKEN_SYMBOL,
            "total_supply": self._total_supply,
            "circulating_supply": total_balance + total_staked + total_locked,
            "total_staked": total_staked,
            "total_locked": total_locked,
            "total_accounts": len(self._accounts),
            "total_transactions": len(self._transactions),
            "active_tasks": sum(
                1 for p in self._task_payments.values() if p["status"] == "pending"
            ),
            "pricing": self.pricing.get_market_stats(),
        }

    def calculate_uptime_reward(
        self, node_id: str, uptime_seconds: float, capacity: Optional[dict[str, Any]] = None
    ) -> float:
        """
        Calculate uptime reward for a node.

        Nodes earn rewards for staying online and available.
        Reward is based on:
        - Uptime duration (minimum 60 seconds to qualify)
        - Node capacity (CPU, memory)
        - Network congestion factor

        Args:
            node_id: Node identifier
            uptime_seconds: Time online in seconds
            capacity: Node capacity dict with 'cpu' and 'memory' keys

        Returns:
            Reward amount in CMP tokens
        """
        MIN_UPTIME_SECONDS = 60
        BASE_REWARD_PER_MINUTE = 1.0
        CPU_MULTIPLIER = 0.5
        MEMORY_MULTIPLIER = 0.0001

        if uptime_seconds < MIN_UPTIME_SECONDS:
            return 0.0

        uptime_minutes = uptime_seconds / 60.0

        capacity = capacity or {}
        cpu_cores = capacity.get("cpu", 1.0)
        memory_mb = capacity.get("memory", 1024)

        base_reward = BASE_REWARD_PER_MINUTE * uptime_minutes

        capacity_bonus = (
            cpu_cores * CPU_MULTIPLIER + memory_mb * MEMORY_MULTIPLIER
        ) * uptime_minutes

        congestion_factor = float(self.pricing._congestion_level)

        total_reward = (base_reward + capacity_bonus) * congestion_factor

        return float(round(total_reward, 4))

    def reward_node_uptime(
        self, node_id: str, uptime_seconds: float, capacity: Optional[dict[str, Any]] = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Reward a node for uptime.

        Args:
            node_id: Node identifier (used as account address)
            uptime_seconds: Time online in seconds
            capacity: Node capacity dict

        Returns:
            (success, result_dict) tuple
        """
        reward_amount = self.calculate_uptime_reward(node_id, uptime_seconds, capacity)

        if reward_amount <= 0:
            return False, {"error": "Uptime too short for reward", "min_uptime_seconds": 60}

        node_account = self._create_account(node_id)

        tx = Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=TransactionType.REWARD,
            from_address=self._treasury_address,
            to_address=node_id,
            amount=reward_amount,
            metadata={
                "reward_type": "uptime",
                "uptime_seconds": uptime_seconds,
                "capacity": capacity,
            },
        )

        node_account.balance += reward_amount
        node_account.total_earned += reward_amount

        treasury = self._accounts.get(self._treasury_address)
        if treasury:
            treasury.balance -= reward_amount

        self._transactions.append(tx)

        if self._persistence:
            self._persistence.persist_reward(
                to_address=node_id,
                amount=reward_amount,
                from_address=self._treasury_address,
                reward_type="uptime",
            )

        self.reputation.update_reputation(node_account, ReputationAction.UPTIME_GOOD)

        return True, {
            "tx_id": tx.tx_id,
            "amount": reward_amount,
            "uptime_seconds": uptime_seconds,
            "new_balance": node_account.balance,
        }

    def get_node_earnings(self, node_id: str) -> dict[str, Any]:
        """
        Get earnings summary for a node.

        Args:
            node_id: Node identifier

        Returns:
            Dict with earnings breakdown
        """
        account = self.get_account(node_id)
        if not account:
            return {"error": "Node account not found"}

        uptime_rewards = sum(
            tx.amount
            for tx in self._transactions
            if tx.to_address == node_id
            and tx.tx_type == TransactionType.REWARD
            and tx.metadata.get("reward_type") == "uptime"
        )

        task_rewards = sum(
            tx.amount
            for tx in self._transactions
            if tx.to_address == node_id
            and tx.tx_type == TransactionType.REWARD
            and tx.metadata.get("reward_type") != "uptime"
        )

        return {
            "node_id": node_id,
            "balance": account.balance,
            "total_earned": account.total_earned,
            "uptime_rewards": uptime_rewards,
            "task_rewards": task_rewards,
            "staked": account.staked,
            "reputation": account.reputation,
        }


__all__ = [
    "TokenType",
    "TransactionType",
    "ReputationAction",
    "ResourceMetrics",
    "Transaction",
    "Account",
    "PricingEngine",
    "ReputationSystem",
    "StakingManager",
    "TokenEconomyPersistenceAdapter",
    "TokenEconomy",
]
