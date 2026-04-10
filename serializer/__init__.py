"""Serializer - High-performance serialization for various data types."""

from __future__ import annotations

import base64
import json
import pickle
import struct
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from datetime import time as time_type
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class SerializationError(Exception):
    pass


class DeserializationError(Exception):
    pass


@dataclass
class SerializationResult:
    data: bytes
    content_type: str
    size_bytes: int
    metadata: dict[str, Any]

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024

    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1024 / 1024


class Serializer(ABC):
    @abstractmethod
    def serialize(self, obj: Any) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        pass

    @property
    @abstractmethod
    def content_type(self) -> str:
        pass

    def serialize_with_metadata(self, obj: Any) -> SerializationResult:
        data = self.serialize(obj)
        return SerializationResult(
            data=data,
            content_type=self.content_type,
            size_bytes=len(data),
            metadata={"serializer": self.__class__.__name__},
        )


class JSONSerializer(Serializer):
    def __init__(self, indent: int | None = None, sort_keys: bool = False):
        self.indent = indent
        self.sort_keys = sort_keys
        self._encoders: dict[type, Callable] = {
            datetime: lambda o: {"__datetime__": o.isoformat()},
            date: lambda o: {"__date__": o.isoformat()},
            time_type: lambda o: {"__time__": o.isoformat()},
            bytes: lambda o: {"__bytes__": base64.b64encode(o).decode("ascii")},
            Path: lambda o: {"__path__": str(o)},
            set: lambda o: {"__set__": list(o)},
            Enum: lambda o: {"__enum__": o.value, "__enum_type__": type(o).__name__},
        }
        self._lock = threading.Lock()

    @property
    def content_type(self) -> str:
        return "application/json"

    def _default(self, obj: Any) -> Any:
        if is_dataclass(obj) and not isinstance(obj, type):
            return {"__dataclass__": obj.__class__.__name__, **asdict(obj)}

        for obj_type, encoder in self._encoders.items():
            if isinstance(obj, obj_type):
                return encoder(obj)

        if hasattr(obj, "__dict__"):
            return {"__object__": obj.__dict__, "__class__": obj.__class__.__name__}

        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _object_hook(self, obj: dict[str, Any]) -> Any:
        if "__datetime__" in obj:
            return datetime.fromisoformat(obj["__datetime__"])
        if "__date__" in obj:
            return date.fromisoformat(obj["__date__"])
        if "__time__" in obj:
            return time_type.fromisoformat(obj["__time__"])
        if "__bytes__" in obj:
            return base64.b64decode(obj["__bytes__"])
        if "__path__" in obj:
            return Path(obj["__path__"])
        if "__set__" in obj:
            return set(obj["__set__"])

        return obj

    def serialize(self, obj: Any) -> bytes:
        try:
            with self._lock:
                json_str = json.dumps(
                    obj,
                    default=self._default,
                    indent=self.indent,
                    sort_keys=self.sort_keys,
                    ensure_ascii=False,
                )
            return json_str.encode("utf-8")
        except Exception as e:
            raise SerializationError(f"JSON serialization failed: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        try:
            with self._lock:
                return json.loads(data.decode("utf-8"), object_hook=self._object_hook)
        except Exception as e:
            raise DeserializationError(f"JSON deserialization failed: {e}") from e


class PickleSerializer(Serializer):
    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL):
        self.protocol = protocol
        self._lock = threading.Lock()

    @property
    def content_type(self) -> str:
        return "application/python-pickle"

    def serialize(self, obj: Any) -> bytes:
        try:
            with self._lock:
                return pickle.dumps(obj, protocol=self.protocol)
        except Exception as e:
            raise SerializationError(f"Pickle serialization failed: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        raise DeserializationError(
            "PickleSerializer.deserialize() is disabled for security. "
            "Use JSONSerializer or MessagePackSerializer instead."
        )


class MessagePackSerializer(Serializer):
    def __init__(self):
        self._msgpack = None
        self._lock = threading.Lock()

    @property
    def content_type(self) -> str:
        return "application/msgpack"

    def _ensure_msgpack(self):
        if self._msgpack is None:
            try:
                import msgpack

                self._msgpack = msgpack
            except ImportError as e:
                raise ImportError("MessagePack support requires msgpack package") from e

    def serialize(self, obj: Any) -> bytes:
        self._ensure_msgpack()
        try:
            with self._lock:
                return self._msgpack.packb(obj, use_bin_type=True)
        except Exception as e:
            raise SerializationError(f"MessagePack serialization failed: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        self._ensure_msgpack()
        try:
            with self._lock:
                return self._msgpack.unpackb(data, raw=False)
        except Exception as e:
            raise DeserializationError(f"MessagePack deserialization failed: {e}") from e


class BinarySerializer(Serializer):
    TYPE_NONE = 0
    TYPE_BOOL = 1
    TYPE_INT = 2
    TYPE_FLOAT = 3
    TYPE_STR = 4
    TYPE_BYTES = 5
    TYPE_LIST = 6
    TYPE_DICT = 7

    def __init__(self):
        self._lock = threading.Lock()

    @property
    def content_type(self) -> str:
        return "application/octet-stream"

    def serialize(self, obj: Any) -> bytes:
        with self._lock:
            return self._encode(obj)

    def _encode(self, obj: Any) -> bytes:
        if obj is None:
            return struct.pack(">BI", self.TYPE_NONE, 0)

        if isinstance(obj, bool):
            return struct.pack(">BB", self.TYPE_BOOL, 1 if obj else 0)

        if isinstance(obj, int):
            return struct.pack(">Bq", self.TYPE_INT, obj)

        if isinstance(obj, float):
            return struct.pack(">Bd", self.TYPE_FLOAT, obj)

        if isinstance(obj, str):
            encoded = obj.encode("utf-8")
            return struct.pack(">BI", self.TYPE_STR, len(encoded)) + encoded

        if isinstance(obj, bytes):
            return struct.pack(">BI", self.TYPE_BYTES, len(obj)) + obj

        if isinstance(obj, (list, tuple)):
            items = b"".join(self._encode(item) for item in obj)
            return struct.pack(">BI", self.TYPE_LIST, len(obj)) + items

        if isinstance(obj, dict):
            items = b""
            for key, value in obj.items():
                items += self._encode(key)
                items += self._encode(value)
            return struct.pack(">BI", self.TYPE_DICT, len(obj)) + items

        raise SerializationError(f"Unsupported type: {type(obj).__name__}")

    def deserialize(self, data: bytes) -> Any:
        with self._lock:
            result, _ = self._decode(data, 0)
            return result

    def _decode(self, data: bytes, offset: int) -> tuple:
        type_byte = struct.unpack_from(">B", data, offset)[0]
        offset += 1

        if type_byte == self.TYPE_NONE:
            return None, offset + 4

        if type_byte == self.TYPE_BOOL:
            value = struct.unpack_from(">B", data, offset)[0]
            return bool(value), offset + 1

        if type_byte == self.TYPE_INT:
            value = struct.unpack_from(">q", data, offset)[0]
            return value, offset + 8

        if type_byte == self.TYPE_FLOAT:
            value = struct.unpack_from(">d", data, offset)[0]
            return value, offset + 8

        if type_byte == self.TYPE_STR:
            length = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            value = data[offset : offset + length].decode("utf-8")
            return value, offset + length

        if type_byte == self.TYPE_BYTES:
            length = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            value = data[offset : offset + length]
            return value, offset + length

        if type_byte == self.TYPE_LIST:
            length = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            items = []
            for _ in range(length):
                item, offset = self._decode(data, offset)
                items.append(item)
            return items, offset

        if type_byte == self.TYPE_DICT:
            length = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            result = {}
            for _ in range(length):
                key, offset = self._decode(data, offset)
                value, offset = self._decode(data, offset)
                result[key] = value
            return result, offset

        raise DeserializationError(f"Unknown type byte: {type_byte}")


class SerializerRegistry:
    _instance: SerializerRegistry | None = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._serializers: dict[str, Serializer] = {
            "json": JSONSerializer(),
        }
        self._default = "json"

    def register(self, name: str, serializer: Serializer):
        self._serializers[name] = serializer

    def get(self, name: str) -> Serializer | None:
        return self._serializers.get(name)

    def set_default(self, name: str):
        if name in self._serializers:
            self._default = name

    def serialize(self, obj: Any, serializer_name: str | None = None) -> SerializationResult:
        name = serializer_name or self._default
        serializer = self._serializers.get(name)

        if not serializer:
            raise SerializationError(f"Unknown serializer: {name}")

        return serializer.serialize_with_metadata(obj)

    def deserialize(self, data: bytes, serializer_name: str | None = None) -> Any:
        name = serializer_name or self._default
        serializer = self._serializers.get(name)

        if not serializer:
            raise DeserializationError(f"Unknown serializer: {name}")

        return serializer.deserialize(data)


def serialize(obj: Any, format: str = "json") -> bytes:
    registry = SerializerRegistry()
    result = registry.serialize(obj, format)
    return result.data


def deserialize(data: bytes, format: str = "json") -> Any:
    registry = SerializerRegistry()
    return registry.deserialize(data, format)


__all__ = [
    "SerializationError",
    "DeserializationError",
    "SerializationResult",
    "Serializer",
    "JSONSerializer",
    "PickleSerializer",
    "MessagePackSerializer",
    "BinarySerializer",
    "SerializerRegistry",
    "serialize",
    "deserialize",
]
