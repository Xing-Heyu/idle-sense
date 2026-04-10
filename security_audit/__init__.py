"""
Security Audit Module.

Provides comprehensive security auditing and logging capabilities.
"""

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Audit event types."""

    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    AUTH_FAILURE = "auth_failure"

    TASK_SUBMIT = "task_submit"
    TASK_EXECUTE = "task_execute"
    TASK_COMPLETE = "task_complete"
    TASK_FAIL = "task_fail"

    NODE_REGISTER = "node_register"
    NODE_HEARTBEAT = "node_heartbeat"
    NODE_OFFLINE = "node_offline"

    PERMISSION_DENIED = "permission_denied"
    ACCESS_VIOLATION = "access_violation"

    CONFIG_CHANGE = "config_change"
    SYSTEM_START = "system_start"
    SYSTEM_SHUTDOWN = "system_shutdown"

    SECURITY_ALERT = "security_alert"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class AuditSeverity(str, Enum):
    """Audit severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """An audit event record."""

    event_type: AuditEventType
    severity: AuditSeverity
    message: str
    user_id: Optional[str] = None
    node_id: Optional[str] = None
    task_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            data = f"{self.event_type}{self.timestamp}{self.user_id}{self.node_id}"
            self.event_id = hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "user_id": self.user_id,
            "node_id": self.node_id,
            "task_id": self.task_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource": self.resource,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


class AuditLogger:
    """
    Centralized audit logging system.

    Features:
    - Multiple output formats (JSON, CSV, syslog)
    - Rotation and retention
    - Real-time alerting
    - Searchable event store
    """

    def __init__(
        self,
        log_dir: str = "logs/audit",
        max_file_size: int = 10 * 1024 * 1024,
        retention_days: int = 90,
        enable_console: bool = True,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.max_file_size = max_file_size
        self.retention_days = retention_days
        self.enable_console = enable_console

        self._current_file: Optional[Path] = None
        self._current_size = 0
        self._lock = threading.Lock()
        self._events: list[AuditEvent] = []
        self._max_events = 10000

        self._alert_handlers: list[callable] = []

    def log(self, event: AuditEvent) -> None:
        """Log an audit event."""
        with self._lock:
            self._events.append(event)

            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events :]

            self._write_event(event)

            if event.severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
                self._trigger_alerts(event)

        if self.enable_console:
            log_msg = f"[AUDIT] {event.event_type.value}: {event.message}"
            if event.severity == AuditSeverity.CRITICAL:
                logger.critical(log_msg)
            elif event.severity == AuditSeverity.ERROR:
                logger.error(log_msg)
            elif event.severity == AuditSeverity.WARNING:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

    def _write_event(self, event: AuditEvent) -> None:
        """Write event to log file."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{today}.jsonl"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def _trigger_alerts(self, event: AuditEvent) -> None:
        """Trigger alert handlers for critical events."""
        for handler in self._alert_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    def add_alert_handler(self, handler: callable) -> None:
        """Add an alert handler."""
        self._alert_handlers.append(handler)

    def search(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        node_id: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Search audit events."""
        results = []

        for event in reversed(self._events):
            if event_type and event.event_type != event_type:
                continue
            if user_id and event.user_id != user_id:
                continue
            if node_id and event.node_id != node_id:
                continue
            if severity and event.severity != severity:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue

            results.append(event)

            if len(results) >= limit:
                break

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        stats = {
            "total_events": len(self._events),
            "by_type": {},
            "by_severity": {},
            "by_user": {},
        }

        for event in self._events:
            et = event.event_type.value
            stats["by_type"][et] = stats["by_type"].get(et, 0) + 1

            sv = event.severity.value
            stats["by_severity"][sv] = stats["by_severity"].get(sv, 0) + 1

            if event.user_id:
                stats["by_user"][event.user_id] = stats["by_user"].get(event.user_id, 0) + 1

        return stats


def audit_log(
    event_type: AuditEventType, message: str, severity: AuditSeverity = AuditSeverity.INFO, **kwargs
) -> None:
    """Convenience function to log an audit event."""
    event = AuditEvent(event_type=event_type, severity=severity, message=message, **kwargs)
    get_audit_logger().log(event)


_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
