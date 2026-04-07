"""
SQLite代币仓储实现

提供基于SQLite的代币经济持久化存储，支持：
- 账户余额管理（CRUD）
- 交易记录（原子性转账）
- 质押生命周期管理
- 按时间范围/类型查询交易历史
- 连接池管理（解决并发问题）
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import aiosqlite

from src.infrastructure.repositories.sqlite_base import SQLiteConnectionPool


class TransactionType(Enum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    STAKE = "stake"
    UNSTAKE = "unstake"
    REWARD = "reward"
    PENALTY = "penalty"
    TRANSFER = "transfer"
    TASK_PAYMENT = "task_payment"
    INTEREST = "interest"


class StakeStatus(Enum):
    ACTIVE = "active"
    UNLOCKED = "unlocked"
    WITHDRAWN = "withdrawn"
    SLASHED = "slashed"


@dataclass
class Account:
    user_id: str
    balance: float = 0.0
    frozen_balance: float = 0.0
    total_earned: float = 0.0
    total_spent: float = 0.0
    updated_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "balance": self.balance,
            "frozen_balance": self.frozen_balance,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "updated_at": self.updated_at,
            "created_at": self.created_at,
        }


@dataclass
class Transaction:
    id: int
    tx_hash: str
    from_user_id: Optional[str]
    to_user_id: str
    amount: float
    tx_type: str
    description: Optional[str]
    reference_id: Optional[str]
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tx_hash": self.tx_hash,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "amount": self.amount,
            "tx_type": self.tx_type,
            "description": self.description,
            "reference_id": self.reference_id,
            "created_at": self.created_at,
        }


@dataclass
class Stake:
    id: int
    user_id: str
    amount: float
    staked_at: str
    unlocked_at: Optional[str]
    status: str
    apy: float
    earned_interest: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": self.amount,
            "staked_at": self.staked_at,
            "unlocked_at": self.unlocked_at,
            "status": self.status,
            "apy": self.apy,
            "earned_interest": self.earned_interest,
        }


class InsufficientBalanceError(Exception):
    """余额不足异常"""


class StakeNotFoundError(Exception):
    """质押记录不存在异常"""


class StakeNotUnlockedError(Exception):
    """质押未解锁异常"""


class DuplicateTransactionError(Exception):
    """重复交易异常"""


class ITokenRepository:
    """代币仓储接口"""

    async def get_or_create_account(self, user_id: str) -> Account:
        """获取或创建用户账户"""
        ...

    async def get_account(self, user_id: str) -> Optional[Account]:
        """获取用户账户（不存在返回None）"""
        ...

    async def get_balance(self, user_id: str) -> float:
        """获取用户可用余额"""
        ...

    async def add_transaction(
        self,
        to_user_id: str,
        amount: float,
        tx_type: str,
        from_user_id: Optional[str] = None,
        description: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> Transaction:
        """添加交易记录并更新账户余额"""
        ...

    async def transfer(
        self,
        from_user_id: str,
        to_user_id: str,
        amount: float,
        tx_type: str = "transfer",
        description: Optional[str] = None,
    ) -> Transaction:
        """原子性转账（事务保证）"""
        ...

    async def get_transaction_history(
        self,
        user_id: str,
        limit: int = 50,
        tx_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[Transaction]:
        """获取交易历史，支持按类型和时间范围过滤"""
        ...

    async def get_transaction_by_hash(self, tx_hash: str) -> Optional[Transaction]:
        """根据交易哈希获取交易记录"""
        ...

    async def stake(self, user_id: str, amount: float, apy: float = 0.05) -> Stake:
        """质押代币"""
        ...

    async def unstake(self, stake_id: int) -> Stake:
        """解除质押"""
        ...

    async def get_stake(self, stake_id: int) -> Optional[Stake]:
        """获取质押记录"""
        ...

    async def get_user_stakes(
        self, user_id: str, status: Optional[str] = None
    ) -> list[Stake]:
        """获取用户的质押列表，可按状态过滤"""
        ...

    async def calculate_stake_interest(self, stake_id: int) -> float:
        """计算质押利息"""
        ...

    async def unlock_stake(self, stake_id: int) -> Stake:
        """解锁质押（标记为可提取状态）"""
        ...

    async def close(self) -> None:
        """关闭数据库连接"""
        ...


class SQLiteTokenRepository(ITokenRepository):
    """
    基于SQLite的代币仓储实现（使用连接池）

    提供代币经济系统的完整持久化存储：
    - 自动建表与索引
    - 异步IO操作（aiosqlite）
    - 原子性事务保证
    - 完整的CRUD与业务方法
    - 连接池管理（解决并发问题）
    """

    def __init__(self, db_path: str = "data/token_economy.db", pool_size: int = 5):
        self.db_path = db_path
        self._pool: Optional[SQLiteConnectionPool] = None
        self._pool_size = pool_size

    async def _get_pool(self) -> SQLiteConnectionPool:
        """获取或初始化连接池"""
        if self._pool is None:
            self._pool = SQLiteConnectionPool(
                db_path=self.db_path,
                max_connections=self._pool_size,
            )
            await self._pool.initialize()
            await self._init_tables()
        return self._pool

    async def _init_tables(self) -> None:
        """初始化数据库表结构"""
        if self._pool is None:
            return

        conn = await self._pool.get_connection()
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_accounts (
                    user_id TEXT PRIMARY KEY,
                    balance REAL NOT NULL DEFAULT 0.0,
                    frozen_balance REAL NOT NULL DEFAULT 0.0,
                    total_earned REAL NOT NULL DEFAULT 0.0,
                    total_spent REAL NOT NULL DEFAULT 0.0,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_accounts_balance ON token_accounts(balance DESC)
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_hash TEXT UNIQUE NOT NULL,
                    from_user_id TEXT,
                    to_user_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    tx_type TEXT NOT NULL,
                    description TEXT,
                    reference_id TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tx_to_user ON token_transactions(to_user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tx_from_user ON token_transactions(from_user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tx_type ON token_transactions(tx_type)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tx_created_at ON token_transactions(created_at)
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_stakes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    staked_at TEXT NOT NULL,
                    unlocked_at TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    apy REAL DEFAULT 0.05,
                    earned_interest REAL DEFAULT 0.0
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stakes_user ON token_stakes(user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stakes_status ON token_stakes(status)
            """)

            await conn.commit()
        finally:
            await self._pool.release_connection(conn)

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()

    @staticmethod
    def _generate_tx_hash() -> str:
        import os as _os
        raw = f"{datetime.utcnow().isoformat()}:{_os.urandom(16).hex()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _row_to_account(self, row: aiosqlite.Row) -> Account:
        return Account(
            user_id=row["user_id"],
            balance=row["balance"],
            frozen_balance=row["frozen_balance"],
            total_earned=row["total_earned"],
            total_spent=row["total_spent"],
            updated_at=row["updated_at"],
            created_at=row["created_at"],
        )

    def _row_to_transaction(self, row: aiosqlite.Row) -> Transaction:
        return Transaction(
            id=row["id"],
            tx_hash=row["tx_hash"],
            from_user_id=row["from_user_id"],
            to_user_id=row["to_user_id"],
            amount=row["amount"],
            tx_type=row["tx_type"],
            description=row["description"],
            reference_id=row["reference_id"],
            created_at=row["created_at"],
        )

    def _row_to_stake(self, row: aiosqlite.Row) -> Stake:
        return Stake(
            id=row["id"],
            user_id=row["user_id"],
            amount=row["amount"],
            staked_at=row["staked_at"],
            unlocked_at=row["unlocked_at"],
            status=row["status"],
            apy=row["apy"],
            earned_interest=row["earned_interest"],
        )

    # ==================== 账户管理 ====================

    async def get_or_create_account(self, user_id: str) -> Account:
        """
        获取或创建用户账户

        如果账户已存在则直接返回，否则创建一个余额为0的新账户
        """
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            now = self._now()

            async with conn.execute(
                "SELECT * FROM token_accounts WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()

            if row:
                return self._row_to_account(row)

            await conn.execute(
                """
                INSERT INTO token_accounts
                (user_id, balance, frozen_balance, total_earned, total_spent, updated_at, created_at)
                VALUES (?, 0.0, 0.0, 0.0, 0.0, ?, ?)
                """,
                (user_id, now, now),
            )
            await conn.commit()

            return Account(
                user_id=user_id,
                balance=0.0,
                frozen_balance=0.0,
                total_earned=0.0,
                total_spent=0.0,
                updated_at=now,
                created_at=now,
            )
        finally:
            await pool.release_connection(conn)

    async def get_account(self, user_id: str) -> Optional[Account]:
        """获取用户账户，不存在则返回None"""
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM token_accounts WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
            return self._row_to_account(row) if row else None
        finally:
            await pool.release_connection(conn)

    async def get_balance(self, user_id: str) -> float:
        """获取用户可用余额（不包含冻结金额）"""
        account = await self.get_account(user_id)
        return account.balance if account else 0.0

    async def update_balance(
        self, user_id: str, delta: float, is_earning: bool = True
    ) -> Account:
        """
        更新用户余额（内部方法）

        Args:
            user_id: 用户ID
            delta: 变动金额（正数增加/负数减少）
            is_earning: 是否为收入（影响total_earned/total_spent统计）
        """
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            now = self._now()
            account = await self.get_or_create_account(user_id)

            new_balance = account.balance + delta
            if new_balance < 0:
                raise InsufficientBalanceError(
                    f"用户 {user_id} 余额不足: 当前 {account.balance}, 需要 {-delta}"
                )

            if is_earning and delta > 0:
                await conn.execute(
                    """
                    UPDATE token_accounts SET
                        balance = balance + ?,
                        frozen_balance = frozen_balance,
                        total_earned = total_earned + ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (delta, delta, now, user_id),
                )
            elif not is_earning and delta > 0:
                await conn.execute(
                    """
                    UPDATE token_accounts SET
                        balance = balance + ?,
                        frozen_balance = frozen_balance,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (delta, now, user_id),
                )
            elif delta < 0:
                spend_delta = abs(delta)
                await conn.execute(
                    """
                    UPDATE token_accounts SET
                        balance = balance + ?,
                        frozen_balance = frozen_balance,
                        total_spent = total_spent + ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (delta, spend_delta, now, user_id),
                )
            else:
                await conn.execute(
                    """
                    UPDATE token_accounts SET
                        balance = balance + ?,
                        frozen_balance = frozen_balance,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (delta, now, user_id),
                )
            await conn.commit()

            return await self.get_account(user_id)
        finally:
            await pool.release_connection(conn)

    # ==================== 交易管理 ====================

    async def add_transaction(
        self,
        to_user_id: str,
        amount: float,
        tx_type: str,
        from_user_id: Optional[str] = None,
        description: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> Transaction:
        """
        添加单条交易记录并更新收款方余额

        用于充值、奖励、惩罚等单向资金流入场景
        """
        if amount <= 0:
            raise ValueError("交易金额必须大于0")

        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            tx_hash = self._generate_tx_hash()
            now = self._now()

            try:
                async with conn.execute(
                    """
                    INSERT INTO token_transactions
                    (tx_hash, from_user_id, to_user_id, amount, tx_type, description, reference_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tx_hash,
                        from_user_id,
                        to_user_id,
                        amount,
                        tx_type,
                        description,
                        reference_id,
                        now,
                    ),
                ):
                    pass

                is_earning = tx_type in ("deposit", "reward", "interest", "unstake")
                await self.update_balance(to_user_id, amount, is_earning=is_earning)

                await conn.commit()
            except aiosqlite.IntegrityError:
                raise DuplicateTransactionError(f"交易哈希冲突: {tx_hash}") from None

            return await self.get_transaction_by_hash(tx_hash)
        finally:
            await pool.release_connection(conn)

    async def transfer(
        self,
        from_user_id: str,
        to_user_id: str,
        amount: float,
        tx_type: str = "transfer",
        description: Optional[str] = None,
    ) -> Transaction:
        """
        原子性转账（事务保证）

        在单个数据库事务中完成：
        1. 扣减转出方余额
        2. 增加接收方余额
        3. 记录交易流水

        任一步骤失败则整体回滚
        """
        if amount <= 0:
            raise ValueError("转账金额必须大于0")

        if from_user_id == to_user_id:
            raise ValueError("不能向自己转账")

        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            tx_hash = self._generate_tx_hash()
            now = self._now()

            try:
                async with conn.execute(
                    "SELECT balance FROM token_accounts WHERE user_id = ?",
                    (from_user_id,),
                ) as cursor:
                    from_row = await cursor.fetchone()

                if not from_row or from_row["balance"] < amount:
                    raise InsufficientBalanceError(
                        f"转出方 {from_user_id} 余额不足"
                    )

                await conn.execute(
                    """
                    INSERT INTO token_transactions
                    (tx_hash, from_user_id, to_user_id, amount, tx_type, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (tx_hash, from_user_id, to_user_id, amount, tx_type, description, now),
                )

                await conn.execute(
                    """
                    UPDATE token_accounts SET
                        balance = balance - ?,
                        total_spent = total_spent + ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (amount, amount, now, from_user_id),
                )

                await conn.execute(
                    """
                    UPDATE token_accounts SET
                        balance = balance + ?,
                        total_earned = total_earned + ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (amount, amount, now, to_user_id),
                )

                await conn.commit()
            except aiosqlite.IntegrityError:
                await conn.rollback()
                raise DuplicateTransactionError(f"交易哈希冲突: {tx_hash}") from None

            return await self.get_transaction_by_hash(tx_hash)
        finally:
            await pool.release_connection(conn)

    async def get_transaction_history(
        self,
        user_id: str,
        limit: int = 50,
        tx_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[Transaction]:
        """
        获取交易历史

        支持以下过滤条件：
        - tx_type: 按交易类型过滤
        - start_time / end_time: 按时间范围过滤（ISO格式）
        - limit: 返回条数上限
        """
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            conditions = ["(from_user_id = ? OR to_user_id = ?)"]
            params: list = [user_id, user_id]

            if tx_type:
                conditions.append("tx_type = ?")
                params.append(tx_type)

            if start_time:
                conditions.append("created_at >= ?")
                params.append(start_time)

            if end_time:
                conditions.append("created_at <= ?")
                params.append(end_time)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            query = f"""
                SELECT * FROM token_transactions
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
            """

            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()

            return [self._row_to_transaction(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def get_transaction_by_hash(self, tx_hash: str) -> Optional[Transaction]:
        """根据交易哈希查询交易记录"""
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM token_transactions WHERE tx_hash = ?", (tx_hash,)
            ) as cursor:
                row = await cursor.fetchone()
            return self._row_to_transaction(row) if row else None
        finally:
            await pool.release_connection(conn)

    # ==================== 质押管理 ====================

    async def stake(self, user_id: str, amount: float, apy: float = 0.05) -> Stake:
        """
        质押代币

        从可用余额中冻结指定数量作为质押，
        创建一条active状态的质押记录
        """
        if amount <= 0:
            raise ValueError("质押金额必须大于0")

        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            now = self._now()

            async with conn.execute(
                "SELECT balance, frozen_balance FROM token_accounts WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row or row["balance"] < amount:
                raise InsufficientBalanceError(f"用户 {user_id} 余额不足，无法质押")

            cursor = await conn.execute(
                """
                INSERT INTO token_stakes
                (user_id, amount, staked_at, status, apy, earned_interest)
                VALUES (?, ?, ?, 'active', ?, 0.0)
                """,
                (user_id, amount, now, apy),
            )

            stake_id = cursor.lastrowid

            await conn.execute(
                """
                UPDATE token_accounts SET
                    balance = balance - ?,
                    frozen_balance = frozen_balance + ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (amount, amount, now, user_id),
            )

            await conn.commit()

            return Stake(
                id=stake_id,
                user_id=user_id,
                amount=amount,
                staked_at=now,
                unlocked_at=None,
                status="active",
                apy=apy,
                earned_interest=0.0,
            )
        finally:
            await pool.release_connection(conn)

    async def unstake(self, stake_id: int) -> Stake:
        """
        解除质押

        要求质押必须处于unlocked状态，
        将本金+利息返还至用户可用余额
        """
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            now = self._now()

            async with conn.execute(
                "SELECT * FROM token_stakes WHERE id = ?", (stake_id,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                raise StakeNotFoundError(f"质押记录不存在: stake_id={stake_id}")

            stake = self._row_to_stake(row)

            if stake.status == "withdrawn":
                raise StakeNotFoundError(f"该质押已被提取: stake_id={stake_id}")

            if stake.status != "unlocked":
                raise StakeNotUnlockedError(
                    f"质押尚未解锁，当前状态: {stake.status}"
                )

            interest = await self.calculate_stake_interest(stake_id)
            total_return = stake.amount + interest

            await conn.execute(
                """
                UPDATE token_stakes SET
                    status = 'withdrawn',
                    earned_interest = ?
                WHERE id = ?
                """,
                (interest, stake_id),
            )

            await conn.execute(
                """
                UPDATE token_accounts SET
                    balance = balance + ?,
                    frozen_balance = frozen_balance - ?,
                    total_earned = total_earned + ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (total_return, stake.amount, interest, now, stake.user_id),
            )

            await conn.commit()

            stake.status = "withdrawn"
            stake.earned_interest = interest
            return stake
        finally:
            await pool.release_connection(conn)

    async def get_stake(self, stake_id: int) -> Optional[Stake]:
        """根据ID查询单条质押记录"""
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM token_stakes WHERE id = ?", (stake_id,)
            ) as cursor:
                row = await cursor.fetchone()
            return self._row_to_stake(row) if row else None
        finally:
            await pool.release_connection(conn)

    async def get_user_stakes(
        self, user_id: str, status: Optional[str] = None
    ) -> list[Stake]:
        """
        获取用户的质押列表

        Args:
            user_id: 用户ID
            status: 按状态过滤（active/unlocked/withdrawn/slashed），为空则返回全部
        """
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            if status:
                async with conn.execute(
                    "SELECT * FROM token_stakes WHERE user_id = ? AND status = ? ORDER BY staked_at DESC",
                    (user_id, status),
                ) as cursor:
                    rows = await cursor.fetchall()
            else:
                async with conn.execute(
                    "SELECT * FROM token_stakes WHERE user_id = ? ORDER BY staked_at DESC",
                    (user_id,),
                ) as cursor:
                    rows = await cursor.fetchall()

            return [self._row_to_stake(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def calculate_stake_interest(self, stake_id: int) -> float:
        """
        计算质押应得利息

        使用简单年化利率公式：interest = principal × APY × (days_held / 365)
        仅在质押处于active或unlocked状态时计算
        """
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM token_stakes WHERE id = ?", (stake_id,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                raise StakeNotFoundError(f"质押记录不存在: stake_id={stake_id}")

            stake = self._row_to_stake(row)

            if stake.status in ("withdrawn", "slashed"):
                return 0.0

            staked_at = datetime.fromisoformat(stake.staked_at)

            if stake.status == "unlocked" and stake.unlocked_at:
                end_time = datetime.fromisoformat(stake.unlocked_at)
            else:
                end_time = datetime.utcnow()

            days_held = (end_time - staked_at).total_seconds() / 86400
            interest = round(stake.amount * stake.apy * (days_held / 365), 6)

            return max(0.0, interest)
        finally:
            await pool.release_connection(conn)

    async def unlock_stake(self, stake_id: int) -> Stake:
        """
        解锁质押

        将质押状态从 active 变更为 unlocked，
        标记解锁时间，此时用户可调用 unstake 提取资金
        """
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            now = self._now()

            async with conn.execute(
                "SELECT * FROM token_stakes WHERE id = ?", (stake_id,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                raise StakeNotFoundError(f"质押记录不存在: stake_id={stake_id}")

            stake = self._row_to_stake(row)

            if stake.status != "active":
                raise ValueError(f"只有active状态的质押才能解锁，当前状态: {stake.status}")

            await conn.execute(
                "UPDATE token_stakes SET status = 'unlocked', unlocked_at = ? WHERE id = ?",
                (now, stake_id),
            )
            await conn.commit()

            stake.status = "unlocked"
            stake.unlocked_at = now
            return stake
        finally:
            await pool.release_connection(conn)

    async def slash_stake(self, stake_id: int, reason: str) -> Stake:
        """
        惩罚质押（ slashing ）

        将质押状态置为 slashed，冻结金额归零且不予返还
        """
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            now = self._now()

            async with conn.execute(
                "SELECT * FROM token_stakes WHERE id = ?", (stake_id,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                raise StakeNotFoundError(f"质押记录不存在: stake_id={stake_id}")

            stake = self._row_to_stake(row)

            if stake.status not in ("active", "unlocked"):
                raise ValueError(f"无法惩罚非活跃质押，当前状态: {stake.status}")

            await conn.execute(
                """
                UPDATE token_stakes SET
                    status = 'slashed',
                    earned_interest = 0.0
                WHERE id = ?
                """,
                (stake_id,),
            )

            await conn.execute(
                """
                UPDATE token_accounts SET
                    frozen_balance = frozen_balance - ?,
                    total_spent = total_spent + ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (stake.amount, stake.amount, now, stake.user_id),
            )

            await conn.commit()

            stake.status = "slashed"
            stake.earned_interest = 0.0
            return stake
        finally:
            await pool.release_connection(conn)

    async def get_all_active_stakes(self) -> list[Stake]:
        """获取所有活跃状态的质押记录（用于批量计息等系统任务）"""
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM token_stakes WHERE status = 'active' ORDER BY staked_at ASC"
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_stake(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    # ==================== 连接管理 ====================

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None


__all__ = [
    "TransactionType",
    "StakeStatus",
    "Account",
    "Transaction",
    "Stake",
    "InsufficientBalanceError",
    "StakeNotFoundError",
    "StakeNotUnlockedError",
    "DuplicateTransactionError",
    "ITokenRepository",
    "SQLiteTokenRepository",
]
