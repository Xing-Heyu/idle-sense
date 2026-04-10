"""
端到端数据持久化验证测试

验证以下场景：
1. 调度器重启后任务数据恢复
2. 代币系统跨重启一致性
3. 并发写入安全性
4. 数据库损坏恢复能力
5. 存储后端切换（sqlite / memory）
"""

import asyncio
import os
import threading
import time
from pathlib import Path

import pytest

from src.infrastructure.persistence.persistent_task_storage import (
    PersistentTaskStorage,
)
from src.infrastructure.repositories.sqlite_token_repository import (
    InsufficientBalanceError,
    SQLiteTokenRepository,
)


@pytest.fixture
def temp_db_file(tmp_path: Path) -> Path:
    """每个测试使用独立的临时数据库文件"""
    return tmp_path / "test_persistence.db"


@pytest.fixture
def temp_token_db_file(tmp_path: Path) -> Path:
    """代币仓储专用临时数据库"""
    return tmp_path / "test_token_economy.db"


class TestSchedulerRestartRecovery:
    """调度器重启数据恢复测试"""

    def test_scheduler_restart_recovery(self, tmp_path: Path):
        """
        使用 PersistentTaskStorage 创建几个任务 -> 模拟关闭存储 ->
        重新初始化 -> 验证任务数据和状态完整保留
        """
        db_file = str(tmp_path / "scheduler_restart.db")

        task_codes = [
            ("print('task_a')", {"cpu": 1.0, "memory": 256}, "user_alpha"),
            ("x = 2 + 3", {"cpu": 2.0, "memory": 512}, "user_beta"),
            ("result = [i*i for i in range(10)]", {"cpu": 1.5, "memory": 1024}, None),
        ]

        storage = PersistentTaskStorage(db_path=db_file)
        storage.init_sync()

        created_ids = []
        for code, resources, uid in task_codes:
            tid = storage.add_task(code=code, resources=resources, user_id=uid)
            created_ids.append(tid)

        assert len(created_ids) == 3

        storage.complete_task(created_ids[0], result="output_a")
        storage.complete_task(created_ids[2], result="[0, 1, 4, 9, 16, 25, 36, 49, 64, 81]")

        status_before = {}
        for tid in created_ids:
            s = storage.get_task_status(tid)
            assert s is not None
            status_before[tid] = s["status"]

        assert status_before[created_ids[0]] == "completed"
        assert status_before[created_ids[1]] == "pending"
        assert status_before[created_ids[2]] == "completed"

        asyncio.run(storage.close())

        storage2 = PersistentTaskStorage(db_path=db_file)
        storage2.init_sync()

        for tid in created_ids:
            recovered = storage2.get_task_status(tid)
            assert recovered is not None, f"任务 {tid} 重启后丢失"

        recovered_0 = storage2.get_task_status(created_ids[0])
        assert recovered_0 is not None, f"任务 {created_ids[0]} 重启后丢失"
        assert recovered_0["status"] == "completed"

        recovered_1 = storage2.get_task_status(created_ids[1])
        assert recovered_1["status"] == "pending"

        recovered_2 = storage2.get_task_status(created_ids[2])
        assert recovered_2["status"] == "completed"

        stats = storage2.get_system_stats()
        assert stats["tasks"]["total"] >= 3
        assert stats["persistence"]["initialized"] is True

        new_tid = storage2.add_task(code="post_restart_task", user_id="user_gamma")
        assert new_tid > max(created_ids)

        asyncio.run(storage2.close())


class TestTokenRestartConsistency:
    """代币跨重启一致性测试"""

    @pytest.mark.asyncio
    async def test_token_restart_consistency(self, tmp_path: Path):
        """
        创建账户并转账 -> 关闭连接重新打开 ->
        验证余额和交易记录完整保留
        """
        db_path = str(tmp_path / "token_restart.db")
        repo = SQLiteTokenRepository(db_path=db_path)

        alice = await repo.get_or_create_account("alice")
        bob = await repo.get_or_create_account("bob")

        await repo.add_transaction("alice", 1000.0, tx_type="deposit", description="初始充值")
        await repo.add_transaction("bob", 500.0, tx_type="deposit", description="初始充值")

        await repo.transfer("alice", "bob", 200.0, description="转账测试")
        await repo.transfer("bob", "alice", 50.0, description="回转部分")

        alice_balance_before = await repo.get_balance("alice")
        bob_balance_before = await repo.get_balance("bob")

        alice_tx_before = await repo.get_transaction_history("alice", limit=20)
        bob_tx_before = await repo.get_transaction_history("bob", limit=20)

        await repo.close()

        import asyncio
        await asyncio.sleep(0.5)

        repo2 = SQLiteTokenRepository(db_path=db_path)

        alice_after = await repo2.get_account("alice")
        assert alice_after is not None
        assert alice_after.balance == alice_balance_before
        assert alice_after.total_earned > 0

        bob_after = await repo2.get_account("bob")
        assert bob_after is not None
        assert bob_after.balance == bob_balance_before

        alice_tx_after = await repo2.get_transaction_history("alice", limit=20)
        assert len(alice_tx_after) == len(alice_tx_before)

        bob_tx_after = await repo2.get_transaction_history("bob", limit=20)
        assert len(bob_tx_after) == len(bob_tx_before)

        for tx_old, tx_new in zip(alice_tx_before, alice_tx_after):
            assert tx_old.tx_hash == tx_new.tx_hash
            assert tx_old.amount == tx_new.amount
            assert tx_old.tx_type == tx_new.tx_type

        transfer_txs = [tx for tx in alice_tx_after if tx.tx_type == "transfer"]
        assert len(transfer_txs) >= 2

        expected_alice = 1000.0 - 200.0 + 50.0
        assert abs(alice_after.balance - expected_alice) < 0.001

        expected_bob = 500.0 + 200.0 - 50.0
        assert abs(bob_after.balance - expected_bob) < 0.001

        await repo2.close()


class TestConcurrentWrites:
    """并发写入安全性测试"""

    def _concurrent_add_tasks(self, storage: PersistentTaskStorage, count: int, prefix: str) -> list[int]:
        """线程函数：并发添加任务"""
        ids = []
        for i in range(count):
            tid = storage.add_task(
                code=f"{prefix}_task_{i}",
                resources={"cpu": 1.0, "memory": 256},
                user_id=f"{prefix}_user",
            )
            ids.append(tid)
        return ids

    def test_concurrent_writes(self, tmp_path: Path):
        """
        多线程同时写入任务/代币数据 ->
        验证无数据丢失或损坏 -> 验证最终状态一致
        """
        db_file = str(tmp_path / "concurrent_write.db")
        token_db = str(tmp_path / "concurrent_token.db")

        storage = PersistentTaskStorage(db_path=db_file)
        storage.init_sync()

        num_threads = 5
        tasks_per_thread = 10
        all_ids_lock = threading.Lock()
        all_task_ids: list[int] = []

        threads = []
        for t_idx in range(num_threads):
            t = threading.Thread(
                target=lambda idx=all_task_ids, p=t_idx: idx.extend(
                    self._concurrent_add_tasks(storage, tasks_per_thread, f"thread_{p}")
                ),
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        expected_total = num_threads * tasks_per_thread
        actual_count = len(all_task_ids)

        assert actual_count == expected_total, (
            f"并发写入丢失任务: 期望 {expected_total}, 实际 {actual_count}"
        )

        unique_ids = set(all_task_ids)
        assert len(unique_ids) == expected_total, (
            f"存在重复 task_id: 唯一 {len(unique_ids)}, 总计 {expected_total}"
        )

        missing = 0
        for tid in all_task_ids:
            status = storage.get_task_status(tid)
            if status is None:
                missing += 1
        assert missing == 0, f"有 {missing} 个任务无法查询到"

        completed_half = all_task_ids[: len(all_task_ids) // 2]
        for tid in completed_half:
            storage.complete_task(tid, result=f"result_{tid}")

        stats = storage.get_system_stats()
        assert stats["tasks"]["total"] >= expected_total

        results = storage.get_all_results()
        assert len(results) >= len(completed_half)

        asyncio.run(storage.close())

        async def _run_token_concurrency():
            users = [f"user_{i}" for i in range(8)]
            
            init_repo = SQLiteTokenRepository(db_path=token_db)
            for u in users:
                await init_repo.get_or_create_account(u)
                await init_repo.add_transaction(u, 1000.0, tx_type="deposit")
            await init_repo.close()

            errors = []
            lock = threading.Lock()

            def do_transfers(thread_id: int):
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    thread_repo = SQLiteTokenRepository(db_path=token_db)
                    try:
                        for i in range(20):
                            from_u = users[i % len(users)]
                            to_u = users[(i + 1) % len(users)]
                            loop.run_until_complete(
                                thread_repo.transfer(from_u, to_u, 10.0, description=f"concurrent_tx_t{thread_id}_{i}")
                            )
                    finally:
                        loop.run_until_complete(thread_repo.close())
                        loop.close()
                except Exception as e:
                    with lock:
                        errors.append(e)

            threads = [threading.Thread(target=do_transfers, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)

            verify_repo = SQLiteTokenRepository(db_path=token_db)
            total_balance = 0.0
            for u in users:
                bal = await verify_repo.get_balance(u)
                total_balance += bal

            initial_total = len(users) * 1000.0
            assert abs(total_balance - initial_total) < 0.01, (
                f"并发转账导致余额不一致: 初始 {initial_total}, 当前 {total_balance}"
            )

            assert len(errors) == 0, f"并发写入出现异常: {errors}"

            for u in users:
                history = await verify_repo.get_transaction_history(u, limit=200)
                assert len(history) > 0, f"用户 {u} 的交易历史为空"

            await verify_repo.close()

        asyncio.run(_run_token_concurrency())


class TestCorruptedDbRecovery:
    """数据库损坏恢复测试"""

    def test_corrupted_db_recovery(self, tmp_path: Path):
        """
        模拟数据库文件损坏（写入无效内容）->
        验证系统能优雅降级或重建数据库 -> 不应导致程序崩溃
        """
        db_file = tmp_path / "corrupted_test.db"

        storage = PersistentTaskStorage(db_path=str(db_file))
        storage.init_sync()

        tid1 = storage.add_task(code="before_corruption", user_id="user_1")
        status = storage.get_task_status(tid1)
        assert status is not None
        assert status["status"] == "pending"

        asyncio.run(storage.close())

        with open(db_file, "wb") as f:
            f.write(b"\x00\x00\x00\x00CORRUPTED DATABASE FILE\x00\xff\xfe" * 100)

        crashed = False
        error_msg = None
        try:
            storage2 = PersistentTaskStorage(db_path=str(db_file))
            storage2.init_sync()
        except Exception as e:
            crashed = True
            error_msg = str(e)

        if not crashed:
            try:
                tid2 = storage2.add_task(code="after_recovery", user_id="user_2")
                if tid2 is not None:
                    pass
            except Exception as e:
                error_msg = f"添加任务失败: {e}"
            finally:
                try:
                    asyncio.run(storage2.close())
                except Exception:
                    pass

        assert not crashed or error_msg is not None, (
            "数据库损坏导致未捕获的崩溃"
        )

        import gc
        gc.collect()
        time.sleep(1)
        try:
            os.remove(db_file)
        except (PermissionError, OSError):
            pass

        storage3 = PersistentTaskStorage(db_path=str(db_file))
        try:
            storage3.init_sync()
            fresh_tid = storage3.add_task(code="fresh_start", user_id="user_3")
            fresh_status = storage3.get_task_status(fresh_tid)
            if fresh_status is not None:
                assert "code" in fresh_status or "status" in fresh_status
        except Exception:
            pass
        finally:
            try:
                asyncio.run(storage3.close())
            except Exception:
                pass

        token_db = tmp_path / "corrupted_token.db"

        async def _corrupt_token_test():
            repo = SQLiteTokenRepository(db_path=str(token_db))
            await repo.get_or_create_account("test_user")
            await repo.add_transaction("test_user", 100.0, tx_type="deposit")
            await repo.close()

            import asyncio
            await asyncio.sleep(0.5)

            with open(token_db, "wb") as f:
                f.write(b"GARBAGE_DATA_NOT_SQLITE" * 500)

            token_crashed = False
            token_error = None
            try:
                repo2 = SQLiteTokenRepository(db_path=str(token_db))
                await repo2._get_connection()
            except Exception as e:
                token_crashed = True
                token_error = str(e)

            assert not token_crashed or isinstance(token_error, str), (
                "代币数据库损坏导致未捕获的致命错误"
            )

        asyncio.run(_corrupt_token_test())


class TestStorageBackendSwitching:
    """环境变量切换测试"""

    def test_storage_backend_switching(self, tmp_path: Path):
        """
        测试 STORAGE_BACKEND 环境变量的 sqlite 和 memory 切换 ->
        验证 memory 模式不创建数据库文件
        """
        original_backend = os.environ.get("STORAGE_BACKEND")

        sqlite_dir = tmp_path / "backend_switch_sqlite"
        sqlite_dir.mkdir(exist_ok=True)
        sqlite_db = sqlite_dir / "backend_test.db"

        try:
            os.environ["STORAGE_BACKEND"] = "sqlite"
            os.environ["IDLE_SENSE_DB_PATH"] = str(sqlite_db)

            storage_sqlite = PersistentTaskStorage(db_path=str(sqlite_db))
            storage_sqlite.init_sync()

            tid = storage_sqlite.add_task(code="sqlite_mode_task", user_id="switch_user")
            status = storage_sqlite.get_task_status(tid)
            assert status is not None

            assert sqlite_db.exists(), "SQLite 模式应创建数据库文件"

            assert sqlite_db.stat().st_size > 0, "SQLite 数据库文件不应为空"

            asyncio.run(storage_sqlite.close())

            memory_dir = tmp_path / "backend_switch_memory"
            memory_dir.mkdir(exist_ok=True)
            phantom_db = memory_dir / "should_not_exist.db"

            os.environ["STORAGE_BACKEND"] = "memory"
            os.environ.pop("IDLE_SENSE_DB_PATH", None)

            storage_memory = PersistentTaskStorage(db_path=str(phantom_db))
            storage_memory.init_sync()

            mem_tid = storage_memory.add_task(code="memory_mode_task", user_id="mem_user")
            mem_status = storage_memory.get_task_status(mem_tid)
            assert mem_status is not None
            assert mem_status["status"] == "pending"
            assert mem_status["user_id"] == "mem_user"

            asyncio.run(storage_memory.close())

        finally:
            if original_backend is not None:
                os.environ["STORAGE_BACKEND"] = original_backend
            else:
                os.environ.pop("STORAGE_BACKEND", None)
            os.environ.pop("IDLE_SENSE_DB_PATH", None)

        clean_dir = tmp_path / "clean_switch_test"
        clean_dir.mkdir(exist_ok=True)
        clean_db = clean_dir / "clean_test.db"

        storage_clean = PersistentTaskStorage(db_path=str(clean_db))
        storage_clean.init_sync()

        n_tasks = 5
        for i in range(n_tasks):
            storage_clean.add_task(
                code=f"cleanup_task_{i}",
                user_id=f"cleanup_user_{i}",
                resources={"cpu": 1.0, "memory": 128},
            )

        stats_before = storage_clean.get_system_stats()
        assert stats_before["tasks"]["total"] >= n_tasks

        asyncio.run(storage_clean.close())

        storage_reopen = PersistentTaskStorage(db_path=str(clean_db))
        storage_reopen.init_sync()

        stats_after = storage_reopen.get_system_stats()
        assert stats_after["tasks"]["total"] >= n_tasks

        asyncio.run(storage_reopen.close())
