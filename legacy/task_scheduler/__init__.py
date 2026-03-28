"""Task Scheduler - Advanced task scheduling with cron and interval support."""

from __future__ import annotations

import calendar
import contextlib
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable


class ScheduleType(str, Enum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class ScheduledTask:
    id: str
    name: str
    handler: Callable
    schedule_type: ScheduleType
    schedule_expr: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    max_runs: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "schedule_expr": self.schedule_expr,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "tags": self.tags
        }


class CronParser:
    FIELD_NAMES = ["minute", "hour", "day", "month", "weekday"]
    FIELD_RANGES = {
        "minute": (0, 59),
        "hour": (0, 23),
        "day": (1, 31),
        "month": (1, 12),
        "weekday": (0, 6)
    }

    @classmethod
    def parse(cls, expression: str) -> dict[str, set[int]]:
        fields = expression.split()

        if len(fields) != 5:
            raise ValueError(f"Invalid cron expression: {expression}")

        result = {}

        for _i, (field_name, field_value) in enumerate(zip(cls.FIELD_NAMES, fields)):
            min_val, max_val = cls.FIELD_RANGES[field_name]
            result[field_name] = cls._parse_field(field_value, min_val, max_val)

        return result

    @classmethod
    def _parse_field(cls, field: str, min_val: int, max_val: int) -> set[int]:
        values = set()

        for part in field.split(","):
            if "/" in part:
                range_part, step_part = part.split("/", 1)
                step = int(step_part)

                if range_part == "*":
                    start, end = min_val, max_val
                elif "-" in range_part:
                    start, end = map(int, range_part.split("-"))
                else:
                    start = end = int(range_part)

                for v in range(start, max_val + 1, step):
                    if min_val <= v <= max_val:
                        values.add(v)

            elif "-" in part:
                start, end = map(int, part.split("-"))
                for v in range(start, end + 1):
                    if min_val <= v <= max_val:
                        values.add(v)

            elif part == "*":
                values.update(range(min_val, max_val + 1))

            else:
                v = int(part)
                if min_val <= v <= max_val:
                    values.add(v)

        return values

    @classmethod
    def get_next_run(cls, expression: str, after: datetime | None = None) -> datetime:
        parsed = cls.parse(expression)
        after = after or datetime.now()

        current = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

        for _ in range(366 * 24 * 60):
            if cls._matches(current, parsed):
                return current
            current += timedelta(minutes=1)

        raise ValueError("Could not find next run time within 1 year")

    @classmethod
    def _matches(cls, dt: datetime, parsed: dict[str, set[int]]) -> bool:
        return (
            dt.minute in parsed["minute"] and
            dt.hour in parsed["hour"] and
            dt.day in parsed["day"] and
            dt.month in parsed["month"] and
            dt.weekday() in parsed["weekday"]
        )


class ScheduleCalculator:
    @staticmethod
    def calculate_next_run(
        schedule_type: ScheduleType,
        expression: str,
        after: datetime | None = None
    ) -> datetime:
        after = after or datetime.now()

        if schedule_type == ScheduleType.ONCE:
            return datetime.fromisoformat(expression)

        if schedule_type == ScheduleType.INTERVAL:
            parts = expression.split()
            value = int(parts[0])
            unit = parts[1].lower()

            if unit in ("second", "seconds"):
                delta = timedelta(seconds=value)
            elif unit in ("minute", "minutes"):
                delta = timedelta(minutes=value)
            elif unit in ("hour", "hours"):
                delta = timedelta(hours=value)
            elif unit in ("day", "days"):
                delta = timedelta(days=value)
            else:
                raise ValueError(f"Unknown interval unit: {unit}")

            return after + delta

        if schedule_type == ScheduleType.CRON:
            return CronParser.get_next_run(expression, after)

        if schedule_type == ScheduleType.DAILY:
            hour, minute = map(int, expression.split(":"))
            next_run = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= after:
                next_run += timedelta(days=1)
            return next_run

        if schedule_type == ScheduleType.WEEKLY:
            parts = expression.split()
            weekday = int(parts[0])
            hour, minute = map(int, parts[1].split(":"))

            days_ahead = weekday - after.weekday()
            if days_ahead <= 0:
                days_ahead += 7

            next_run = after + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if next_run <= after:
                next_run += timedelta(weeks=1)

            return next_run

        if schedule_type == ScheduleType.MONTHLY:
            parts = expression.split()
            day = int(parts[0])
            hour, minute = map(int, parts[1].split(":"))

            next_run = after.replace(day=min(day, calendar.monthrange(after.year, after.month)[1]),
                                     hour=hour, minute=minute, second=0, microsecond=0)

            if next_run <= after:
                month = after.month + 1
                year = after.year
                if month > 12:
                    month = 1
                    year += 1
                next_run = next_run.replace(year=year, month=month,
                                           day=min(day, calendar.monthrange(year, month)[1]))

            return next_run

        raise ValueError(f"Unknown schedule type: {schedule_type}")


class TaskScheduler:
    def __init__(self, check_interval: float = 1.0):
        self.check_interval = check_interval
        self._tasks: dict[str, ScheduledTask] = {}
        self._lock = threading.RLock()
        self._running = False
        self._scheduler_thread: threading.Thread | None = None
        self._on_task_run: Callable[[ScheduledTask], None] | None = None
        self._on_task_error: Callable[[ScheduledTask, Exception], None] | None = None

    def schedule(
        self,
        name: str,
        handler: Callable,
        schedule_type: ScheduleType,
        expression: str,
        args: tuple | None = None,
        kwargs: dict | None = None,
        enabled: bool = True,
        max_runs: int | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None
    ) -> ScheduledTask:
        import uuid

        task = ScheduledTask(
            id=str(uuid.uuid4()),
            name=name,
            handler=handler,
            schedule_type=schedule_type,
            schedule_expr=expression,
            args=args or (),
            kwargs=kwargs or {},
            enabled=enabled,
            max_runs=max_runs,
            tags=tags or [],
            metadata=metadata or {}
        )

        task.next_run = ScheduleCalculator.calculate_next_run(
            schedule_type, expression
        )

        with self._lock:
            self._tasks[task.id] = task

        return task

    def schedule_once(
        self,
        name: str,
        handler: Callable,
        run_at: datetime,
        **kwargs
    ) -> ScheduledTask:
        return self.schedule(
            name=name,
            handler=handler,
            schedule_type=ScheduleType.ONCE,
            expression=run_at.isoformat(),
            **kwargs
        )

    def schedule_interval(
        self,
        name: str,
        handler: Callable,
        interval_seconds: int,
        **kwargs
    ) -> ScheduledTask:
        return self.schedule(
            name=name,
            handler=handler,
            schedule_type=ScheduleType.INTERVAL,
            expression=f"{interval_seconds} seconds",
            **kwargs
        )

    def schedule_cron(
        self,
        name: str,
        handler: Callable,
        cron_expression: str,
        **kwargs
    ) -> ScheduledTask:
        return self.schedule(
            name=name,
            handler=handler,
            schedule_type=ScheduleType.CRON,
            expression=cron_expression,
            **kwargs
        )

    def schedule_daily(
        self,
        name: str,
        handler: Callable,
        time_str: str,
        **kwargs
    ) -> ScheduledTask:
        return self.schedule(
            name=name,
            handler=handler,
            schedule_type=ScheduleType.DAILY,
            expression=time_str,
            **kwargs
        )

    def unschedule(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def get_task(self, task_id: str) -> ScheduledTask | None:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[ScheduledTask]:
        return list(self._tasks.values())

    def get_tasks_by_tag(self, tag: str) -> list[ScheduledTask]:
        return [t for t in self._tasks.values() if tag in t.tags]

    def enable_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task:
            task.enabled = True
            if not task.next_run:
                task.next_run = ScheduleCalculator.calculate_next_run(
                    task.schedule_type, task.schedule_expr
                )
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task:
            task.enabled = False
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        return self.disable_task(task_id)

    def resume_task(self, task_id: str) -> bool:
        return self.enable_task(task_id)

    def run_task_now(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False

        try:
            task.handler(*task.args, **task.kwargs)
            task.last_run = datetime.now()
            task.run_count += 1

            if self._on_task_run:
                self._on_task_run(task)

            return True
        except Exception as e:
            if self._on_task_error:
                self._on_task_error(task, e)
            return False

    def set_callbacks(
        self,
        on_task_run: Callable[[ScheduledTask], None] | None = None,
        on_task_error: Callable[[ScheduledTask, Exception], None] | None = None
    ):
        self._on_task_run = on_task_run
        self._on_task_error = on_task_error

    def start(self):
        if self._running:
            return

        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    def stop(self):
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
            self._scheduler_thread = None

    def _scheduler_loop(self):
        while self._running:
            with contextlib.suppress(Exception):
                self._check_and_run_tasks()

            time.sleep(self.check_interval)

    def _check_and_run_tasks(self):
        now = datetime.now()

        with self._lock:
            tasks_to_run = []

            for task in self._tasks.values():
                if not task.enabled:
                    continue

                if task.max_runs is not None and task.run_count >= task.max_runs:
                    continue

                if task.next_run and task.next_run <= now:
                    tasks_to_run.append(task)

        for task in tasks_to_run:
            try:
                task.handler(*task.args, **task.kwargs)
                task.last_run = now
                task.run_count += 1

                if task.schedule_type == ScheduleType.ONCE:
                    task.enabled = False
                else:
                    task.next_run = ScheduleCalculator.calculate_next_run(
                        task.schedule_type, task.schedule_expr, now
                    )

                if self._on_task_run:
                    self._on_task_run(task)

            except Exception as e:
                if self._on_task_error:
                    self._on_task_error(task, e)

    def get_upcoming_runs(self, count: int = 10) -> list[tuple[ScheduledTask, datetime]]:
        with self._lock:
            tasks_with_next_run = [
                (task, task.next_run)
                for task in self._tasks.values()
                if task.enabled and task.next_run
            ]

        tasks_with_next_run.sort(key=lambda x: x[1])
        return tasks_with_next_run[:count]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._tasks)
            enabled = sum(1 for t in self._tasks.values() if t.enabled)
            total_runs = sum(t.run_count for t in self._tasks.values())

            return {
                "total_tasks": total,
                "enabled_tasks": enabled,
                "disabled_tasks": total - enabled,
                "total_runs": total_runs,
                "running": self._running
            }


__all__ = [
    "ScheduleType",
    "ScheduledTask",
    "CronParser",
    "ScheduleCalculator",
    "TaskScheduler",
]
