"""Message Queue - Pub/Sub message queue with multiple backends."""

from __future__ import annotations

import json
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class MessageStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"


class DeliveryMode(str, Enum):
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


@dataclass
class Message(Generic[T]):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    payload: T = None
    headers: dict[str, str] = field(default_factory=dict)
    status: MessageStatus = MessageStatus.PENDING
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 0
    correlation_id: str | None = None
    reply_to: str | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "headers": self.headers,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "retry_count": self.retry_count,
            "priority": self.priority,
            "correlation_id": self.correlation_id,
        }


@dataclass
class Subscription:
    id: str
    topic: str
    callback: Callable[[Message], None]
    filter_expr: str | None = None
    created_at: float = field(default_factory=time.time)
    message_count: int = 0
    error_count: int = 0
    last_message_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "filter": self.filter_expr,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "last_message_at": self.last_message_at,
        }


@dataclass
class QueueStats:
    total_published: int = 0
    total_delivered: int = 0
    total_acknowledged: int = 0
    total_failed: int = 0
    pending_messages: int = 0
    active_subscriptions: int = 0
    topics: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_published": self.total_published,
            "total_delivered": self.total_delivered,
            "total_acknowledged": self.total_acknowledged,
            "total_failed": self.total_failed,
            "pending_messages": self.pending_messages,
            "active_subscriptions": self.active_subscriptions,
            "topics": self.topics,
        }


class MessageQueueBackend(ABC):
    @abstractmethod
    def publish(self, message: Message) -> bool:
        pass

    @abstractmethod
    def consume(self, topic: str, timeout: float = 0) -> Message | None:
        pass

    @abstractmethod
    def acknowledge(self, message_id: str) -> bool:
        pass

    @abstractmethod
    def get_pending(self, topic: str) -> list[Message]:
        pass

    @abstractmethod
    def get_stats(self) -> QueueStats:
        pass


class MemoryQueueBackend(MessageQueueBackend):
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queues: dict[str, list[Message]] = defaultdict(list)
        self._messages: dict[str, Message] = {}
        self._lock = threading.RLock()
        self._conditions: dict[str, threading.Condition] = defaultdict(
            lambda: threading.Condition(self._lock)
        )
        self._stats = QueueStats()

    def publish(self, message: Message) -> bool:
        with self._lock:
            if len(self._messages) >= self.max_size:
                return False

            self._queues[message.topic].append(message)
            self._messages[message.id] = message
            self._stats.total_published += 1
            self._stats.pending_messages = len(self._messages)
            self._stats.topics = len(self._queues)

            self._conditions[message.topic].notify_all()

            return True

    def consume(self, topic: str, timeout: float = 0) -> Message | None:
        with self._conditions[topic]:
            if not self._queues[topic]:
                if timeout > 0:
                    self._conditions[topic].wait(timeout)
                if not self._queues[topic]:
                    return None

            if self._queues[topic]:
                message = self._queues[topic].pop(0)
                message.status = MessageStatus.DELIVERED
                self._stats.total_delivered += 1
                return message

            return None

    def acknowledge(self, message_id: str) -> bool:
        with self._lock:
            message = self._messages.get(message_id)
            if message:
                message.status = MessageStatus.ACKNOWLEDGED
                del self._messages[message_id]
                self._stats.total_acknowledged += 1
                self._stats.pending_messages = len(self._messages)
                return True
            return False

    def get_pending(self, topic: str) -> list[Message]:
        with self._lock:
            return list(self._queues.get(topic, []))

    def get_stats(self) -> QueueStats:
        with self._lock:
            return QueueStats(**dict(self._stats.__dict__.items()))


class RedisQueueBackend(MessageQueueBackend):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        prefix: str = "mq:",
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.prefix = prefix
        self._client = None
        self._stats = QueueStats()

    @property
    def client(self):
        if self._client is None:
            try:
                import redis

                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=True,
                )
            except ImportError as e:
                raise ImportError("Redis support requires redis package") from e
        return self._client

    def _topic_key(self, topic: str) -> str:
        return f"{self.prefix}topic:{topic}"

    def _message_key(self, message_id: str) -> str:
        return f"{self.prefix}msg:{message_id}"

    def publish(self, message: Message) -> bool:
        message_data = json.dumps(
            {
                "id": message.id,
                "topic": message.topic,
                "payload": message.payload,
                "headers": message.headers,
                "status": message.status.value,
                "created_at": message.created_at,
                "expires_at": message.expires_at,
                "retry_count": message.retry_count,
                "max_retries": message.max_retries,
                "priority": message.priority,
                "correlation_id": message.correlation_id,
                "reply_to": message.reply_to,
            }
        )

        self.client.hset(self._message_key(message.id), "data", message_data)
        self.client.rpush(self._topic_key(message.topic), message.id)
        self._stats.total_published += 1

        return True

    def consume(self, topic: str, timeout: float = 0) -> Message | None:
        result = self.client.blpop(self._topic_key(topic), timeout=int(timeout) if timeout else 0)

        if not result:
            return None

        _, message_id = result
        message_data = self.client.hget(self._message_key(message_id), "data")

        if not message_data:
            return None

        data = json.loads(message_data)
        message = Message(
            id=data["id"],
            topic=data["topic"],
            payload=data.get("payload"),
            headers=data.get("headers", {}),
            status=MessageStatus.DELIVERED,
            created_at=data["created_at"],
            expires_at=data.get("expires_at"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            priority=data.get("priority", 0),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
        )

        self._stats.total_delivered += 1
        return message

    def acknowledge(self, message_id: str) -> bool:
        key = self._message_key(message_id)
        if self.client.exists(key):
            self.client.delete(key)
            self._stats.total_acknowledged += 1
            return True
        return False

    def get_pending(self, topic: str) -> list[Message]:
        message_ids = self.client.lrange(self._topic_key(topic), 0, -1)
        messages = []

        for msg_id in message_ids:
            message_data = self.client.hget(self._message_key(msg_id), "data")
            if message_data:
                data = json.loads(message_data)
                messages.append(
                    Message(
                        id=data["id"],
                        topic=data["topic"],
                        payload=data.get("payload"),
                        headers=data.get("headers", {}),
                        status=MessageStatus(data["status"]),
                        created_at=data["created_at"],
                    )
                )

        return messages

    def get_stats(self) -> QueueStats:
        return self._stats


class MessageQueue:
    def __init__(
        self,
        backend: MessageQueueBackend | None = None,
        delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE,
    ):
        self.backend = backend or MemoryQueueBackend()
        self.delivery_mode = delivery_mode
        self._subscriptions: dict[str, Subscription] = {}
        self._topic_subscriptions: dict[str, list[str]] = defaultdict(list)
        self._lock = threading.RLock()
        self._running = False
        self._consumer_threads: list[threading.Thread] = []

    def publish(
        self,
        topic: str,
        payload: Any,
        headers: dict[str, str] | None = None,
        priority: int = 0,
        ttl_seconds: float | None = None,
        correlation_id: str | None = None,
        reply_to: str | None = None,
    ) -> Message:
        message = Message(
            topic=topic,
            payload=payload,
            headers=headers or {},
            priority=priority,
            expires_at=time.time() + ttl_seconds if ttl_seconds else None,
            correlation_id=correlation_id,
            reply_to=reply_to,
        )

        self.backend.publish(message)

        return message

    def subscribe(
        self, topic: str, callback: Callable[[Message], None], filter_expr: str | None = None
    ) -> Subscription:
        import uuid

        subscription = Subscription(
            id=str(uuid.uuid4()), topic=topic, callback=callback, filter_expr=filter_expr
        )

        with self._lock:
            self._subscriptions[subscription.id] = subscription
            self._topic_subscriptions[topic].append(subscription.id)

        return subscription

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            subscription = self._subscriptions.pop(subscription_id, None)
            if subscription:
                self._topic_subscriptions[subscription.topic].remove(subscription_id)
                return True
            return False

    def request_reply(self, topic: str, payload: Any, timeout: float = 30.0) -> Message | None:
        correlation_id = str(uuid.uuid4())
        reply_topic = f"reply:{correlation_id}"

        response_event = threading.Event()
        response_message: Message | None = [None]

        def reply_handler(msg: Message):
            if msg.correlation_id == correlation_id:
                response_message[0] = msg
                response_event.set()

        self.subscribe(reply_topic, reply_handler)

        self.publish(
            topic=topic, payload=payload, correlation_id=correlation_id, reply_to=reply_topic
        )

        response_event.wait(timeout)

        return response_message[0]

    def start_consumers(self, topics: list[str] | None = None):
        if self._running:
            return

        self._running = True

        topics = topics or list(self._topic_subscriptions.keys())

        for topic in topics:
            thread = threading.Thread(target=self._consumer_loop, args=(topic,), daemon=True)
            thread.start()
            self._consumer_threads.append(thread)

    def stop_consumers(self):
        self._running = False
        self._consumer_threads.clear()

    def _consumer_loop(self, topic: str):
        while self._running:
            try:
                message = self.backend.consume(topic, timeout=1.0)

                if not message:
                    continue

                if message.is_expired:
                    message.status = MessageStatus.EXPIRED
                    continue

                with self._lock:
                    sub_ids = self._topic_subscriptions.get(topic, [])

                for sub_id in sub_ids:
                    subscription = self._subscriptions.get(sub_id)
                    if not subscription:
                        continue

                    try:
                        subscription.callback(message)
                        subscription.message_count += 1
                        subscription.last_message_at = time.time()
                    except Exception:
                        subscription.error_count += 1

                if self.delivery_mode == DeliveryMode.AT_LEAST_ONCE:
                    self.backend.acknowledge(message.id)

            except Exception:
                time.sleep(0.1)

    def get_stats(self) -> QueueStats:
        stats = self.backend.get_stats()
        with self._lock:
            stats.active_subscriptions = len(self._subscriptions)
        return stats

    def get_subscriptions(self, topic: str | None = None) -> list[Subscription]:
        with self._lock:
            if topic:
                return [
                    self._subscriptions[sid] for sid in self._topic_subscriptions.get(topic, [])
                ]
            return list(self._subscriptions.values())


__all__ = [
    "MessageStatus",
    "DeliveryMode",
    "Message",
    "Subscription",
    "QueueStats",
    "MessageQueueBackend",
    "MemoryQueueBackend",
    "RedisQueueBackend",
    "MessageQueue",
]
