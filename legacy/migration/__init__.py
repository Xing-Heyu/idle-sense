"""Database Migration Tool - Schema versioning and migration management."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class MigrationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Migration:
    version: str
    name: str
    up_sql: str = ""
    down_sql: str = ""
    up_callback: Callable | None = None
    down_callback: Callable | None = None
    description: str = ""
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    checksum: str = ""
    dependencies: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.checksum:
            content = f"{self.version}:{self.name}:{self.up_sql}:{self.down_sql}"
            self.checksum = hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class MigrationRecord:
    version: str
    name: str
    checksum: str
    applied_at: datetime
    execution_time_ms: int
    status: MigrationStatus


class MigrationBackend(ABC):
    @abstractmethod
    def execute(self, sql: str) -> Any:
        pass

    @abstractmethod
    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        pass

    @abstractmethod
    def transaction(self):
        pass

    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        pass


class SQLiteBackend(MigrationBackend):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def execute(self, sql: str) -> Any:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            self.conn.commit()
            return cursor

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

    @contextmanager
    def transaction(self):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            try:
                yield cursor
                cursor.execute("COMMIT")
            except Exception:
                cursor.execute("ROLLBACK")
                raise

    def table_exists(self, table_name: str) -> bool:
        result = self.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        )
        return len(result) > 0

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


class MigrationStore:
    TABLE_NAME = "_migrations"

    def __init__(self, backend: MigrationBackend):
        self.backend = backend
        self._ensure_table()

    def _ensure_table(self):
        if not self.backend.table_exists(self.TABLE_NAME):
            self.backend.execute(f"""
                CREATE TABLE {self.TABLE_NAME} (
                    version TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    execution_time_ms INTEGER,
                    status TEXT DEFAULT 'completed'
                )
            """)

    def record_migration(self, record: MigrationRecord):
        self.backend.execute(
            f"""
            INSERT OR REPLACE INTO {self.TABLE_NAME}
            (version, name, checksum, applied_at, execution_time_ms, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                record.version,
                record.name,
                record.checksum,
                record.applied_at,
                record.execution_time_ms,
                record.status.value,
            ),
        )

    def get_applied_migrations(self) -> list[MigrationRecord]:
        rows = self.backend.query(f"""
            SELECT version, name, checksum, applied_at, execution_time_ms, status
            FROM {self.TABLE_NAME}
            ORDER BY applied_at
        """)
        return [
            MigrationRecord(
                version=row[0],
                name=row[1],
                checksum=row[2],
                applied_at=datetime.fromisoformat(row[3]) if isinstance(row[3], str) else row[3],
                execution_time_ms=row[4],
                status=MigrationStatus(row[5]),
            )
            for row in rows
        ]

    def is_applied(self, version: str) -> bool:
        rows = self.backend.query(
            f"SELECT version FROM {self.TABLE_NAME} WHERE version = ?", (version,)
        )
        return len(rows) > 0

    def get_last_version(self) -> str | None:
        rows = self.backend.query(f"""
            SELECT version FROM {self.TABLE_NAME}
            WHERE status = 'completed'
            ORDER BY applied_at DESC LIMIT 1
        """)
        return rows[0][0] if rows else None

    def remove_migration(self, version: str):
        self.backend.execute(f"DELETE FROM {self.TABLE_NAME} WHERE version = ?", (version,))


class MigrationRunner:
    def __init__(self, backend: MigrationBackend, migrations_dir: str = "migrations"):
        self.backend = backend
        self.store = MigrationStore(backend)
        self.migrations_dir = Path(migrations_dir)
        self.migrations: dict[str, Migration] = {}
        self._load_migrations()

    def _load_migrations(self):
        if not self.migrations_dir.exists():
            self.migrations_dir.mkdir(parents=True, exist_ok=True)
            return

        for file_path in sorted(self.migrations_dir.glob("*.json")):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                migration = Migration(
                    version=data["version"],
                    name=data["name"],
                    up_sql=data.get("up_sql", ""),
                    down_sql=data.get("down_sql", ""),
                    description=data.get("description", ""),
                    author=data.get("author", ""),
                    dependencies=data.get("dependencies", []),
                )
                self.migrations[migration.version] = migration
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load migration {file_path}: {e}")

    def register_migration(self, migration: Migration):
        self.migrations[migration.version] = migration
        file_path = self.migrations_dir / f"{migration.version}_{migration.name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": migration.version,
                    "name": migration.name,
                    "up_sql": migration.up_sql,
                    "down_sql": migration.down_sql,
                    "description": migration.description,
                    "author": migration.author,
                    "dependencies": migration.dependencies,
                },
                f,
                indent=2,
            )

    def create_migration(
        self, name: str, up_sql: str, down_sql: str = "", description: str = "", author: str = ""
    ) -> Migration:
        last_version = self.store.get_last_version()
        if last_version:
            parts = last_version.split(".")
            new_version = ".".join(
                str(int(parts[i]) + 1) if i == len(parts) - 1 else parts[i]
                for i in range(len(parts))
            )
        else:
            new_version = "1.0.0"

        migration = Migration(
            version=new_version,
            name=name,
            up_sql=up_sql,
            down_sql=down_sql,
            description=description,
            author=author,
        )
        self.register_migration(migration)
        return migration

    def get_pending_migrations(self) -> list[Migration]:
        applied = {m.version for m in self.store.get_applied_migrations()}
        pending = []

        for version in sorted(self.migrations.keys()):
            if version not in applied:
                migration = self.migrations[version]
                if all(dep in applied for dep in migration.dependencies):
                    pending.append(migration)

        return pending

    def _run_up(self, migration: Migration) -> MigrationRecord:
        start_time = datetime.now()

        try:
            if migration.up_sql:
                self.backend.execute(migration.up_sql)

            if migration.up_callback:
                migration.up_callback(self.backend)

            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

            record = MigrationRecord(
                version=migration.version,
                name=migration.name,
                checksum=migration.checksum,
                applied_at=datetime.now(),
                execution_time_ms=execution_time,
                status=MigrationStatus.COMPLETED,
            )
            self.store.record_migration(record)
            return record

        except Exception:
            record = MigrationRecord(
                version=migration.version,
                name=migration.name,
                checksum=migration.checksum,
                applied_at=datetime.now(),
                execution_time_ms=0,
                status=MigrationStatus.FAILED,
            )
            self.store.record_migration(record)
            raise

    def _run_down(self, migration: Migration) -> bool:
        try:
            if migration.down_sql:
                self.backend.execute(migration.down_sql)

            if migration.down_callback:
                migration.down_callback(self.backend)

            self.store.remove_migration(migration.version)
            return True

        except Exception as e:
            print(f"Rollback failed for {migration.version}: {e}")
            return False

    def migrate(self, target_version: str | None = None) -> list[MigrationRecord]:
        results = []
        pending = self.get_pending_migrations()

        if target_version:
            pending = [m for m in pending if m.version <= target_version]

        for migration in pending:
            print(f"Applying migration: {migration.version} - {migration.name}")
            record = self._run_up(migration)
            results.append(record)

        return results

    def rollback(self, steps: int = 1) -> list[str]:
        applied = self.store.get_applied_migrations()
        rolled_back = []

        for record in reversed(applied[-steps:]):
            if record.version in self.migrations:
                migration = self.migrations[record.version]
                if self._run_down(migration):
                    rolled_back.append(record.version)

        return rolled_back

    def reset(self):
        applied = self.store.get_applied_migrations()
        for record in reversed(applied):
            if record.version in self.migrations:
                migration = self.migrations[record.version]
                self._run_down(migration)

    def status(self) -> dict[str, Any]:
        applied = self.store.get_applied_migrations()
        pending = self.get_pending_migrations()

        return {
            "applied_count": len(applied),
            "pending_count": len(pending),
            "last_version": self.store.get_last_version(),
            "applied": [
                {"version": m.version, "name": m.name, "applied_at": m.applied_at.isoformat()}
                for m in applied
            ],
            "pending": [{"version": m.version, "name": m.name} for m in pending],
        }


def migration(
    version: str,
    name: str,
    up_sql: str = "",
    down_sql: str = "",
    dependencies: list[str] | None = None,
):
    def decorator(func: Callable) -> Migration:
        return Migration(
            version=version,
            name=name,
            up_sql=up_sql,
            down_sql=down_sql,
            up_callback=func,
            dependencies=dependencies or [],
        )

    return decorator


__all__ = [
    "MigrationStatus",
    "Migration",
    "MigrationRecord",
    "MigrationBackend",
    "SQLiteBackend",
    "MigrationStore",
    "MigrationRunner",
    "migration",
]
