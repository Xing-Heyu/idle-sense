"""
审计日志系统

记录所有关键操作，支持审计追溯
"""

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class AuditAction(Enum):
    """审计操作类型"""

    USER_LOGIN = "user:login"
    USER_LOGOUT = "user:logout"
    USER_REGISTER = "user:register"

    TASK_SUBMIT = "task:submit"
    TASK_CANCEL = "task:cancel"
    TASK_DELETE = "task:delete"

    NODE_ACTIVATE = "node:activate"
    NODE_STOP = "node:stop"

    SYSTEM_CONFIG_CHANGE = "system:config_change"


@dataclass
class AuditLog:
    """审计日志记录"""

    timestamp: datetime
    action: AuditAction
    user_id: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditLog":
        """从字典创建"""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=AuditAction(data["action"]),
            user_id=data["user_id"],
            resource_type=data["resource_type"],
            resource_id=data["resource_id"],
            details=data.get("details", {}),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
        )


class AuditLogger:
    """
    审计日志记录器

    记录所有关键操作，支持查询和追溯
    """

    def __init__(self, db_path: str = "audit.db"):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON audit_logs(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_action ON audit_logs(action)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_logs(timestamp)
            """)

    def log(
        self,
        action: AuditAction,
        user_id: str,
        resource_type: str,
        resource_id: str,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """记录审计日志"""
        log_entry = AuditLog(
            timestamp=datetime.now(),
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO audit_logs
                    (timestamp, action, user_id, resource_type, resource_id, details, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        log_entry.timestamp.isoformat(),
                        log_entry.action.value,
                        log_entry.user_id,
                        log_entry.resource_type,
                        log_entry.resource_id,
                        json.dumps(log_entry.details),
                        log_entry.ip_address,
                        log_entry.user_agent,
                    ),
                )

    def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """查询审计日志"""
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if action:
            conditions.append("action = ?")
            params.append(action.value)
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT timestamp, action, user_id, resource_type, resource_id, details, ip_address, user_agent
            FROM audit_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                data = {
                    "timestamp": row[0],
                    "action": row[1],
                    "user_id": row[2],
                    "resource_type": row[3],
                    "resource_id": row[4],
                    "details": json.loads(row[5]) if row[5] else {},
                    "ip_address": row[6],
                    "user_agent": row[7],
                }
                results.append(AuditLog.from_dict(data))
            return results


__all__ = ["AuditAction", "AuditLog", "AuditLogger"]
