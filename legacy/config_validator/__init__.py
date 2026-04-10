"""Configuration Validator - Validates configuration with schema and rules."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class ValidationLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    path: str
    message: str
    level: ValidationLevel = ValidationLevel.ERROR
    value: Any = None
    expected: str | None = None
    suggestion: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def add_error(self, error: ValidationError):
        if error.level == ValidationLevel.ERROR:
            self.errors.append(error)
            self.valid = False
        elif error.level == ValidationLevel.WARNING:
            self.warnings.append(error)

    def merge(self, other: ValidationResult):
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [
                {
                    "path": e.path,
                    "message": e.message,
                    "level": e.level.value,
                    "value": str(e.value) if e.value is not None else None,
                    "expected": e.expected,
                    "suggestion": e.suggestion,
                }
                for e in self.errors
            ],
            "warnings": [{"path": w.path, "message": w.message} for w in self.warnings],
        }


class Validator(ABC):
    @abstractmethod
    def validate(self, value: Any, path: str = "") -> ValidationResult:
        pass


class TypeValidator(Validator):
    def __init__(self, expected_type: type | tuple[type, ...]):
        self.expected_type = expected_type

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)
        if not isinstance(value, self.expected_type):
            result.add_error(
                ValidationError(
                    path=path,
                    message=f"Expected type {self.expected_type}, got {type(value).__name__}",
                    value=value,
                    expected=str(self.expected_type),
                )
            )
        return result


class RangeValidator(Validator):
    def __init__(
        self,
        min_val: int | float | None = None,
        max_val: int | float | None = None,
        inclusive: bool = True,
    ):
        self.min_val = min_val
        self.max_val = max_val
        self.inclusive = inclusive

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)

        if not isinstance(value, (int, float)):
            result.add_error(
                ValidationError(path=path, message="Value must be numeric", value=value)
            )
            return result

        if self.min_val is not None:
            if self.inclusive and value < self.min_val:
                result.add_error(
                    ValidationError(
                        path=path,
                        message=f"Value {value} is below minimum {self.min_val}",
                        value=value,
                        expected=f">= {self.min_val}",
                    )
                )
            elif not self.inclusive and value <= self.min_val:
                result.add_error(
                    ValidationError(
                        path=path,
                        message=f"Value {value} must be greater than {self.min_val}",
                        value=value,
                        expected=f"> {self.min_val}",
                    )
                )

        if self.max_val is not None:
            if self.inclusive and value > self.max_val:
                result.add_error(
                    ValidationError(
                        path=path,
                        message=f"Value {value} exceeds maximum {self.max_val}",
                        value=value,
                        expected=f"<= {self.max_val}",
                    )
                )
            elif not self.inclusive and value >= self.max_val:
                result.add_error(
                    ValidationError(
                        path=path,
                        message=f"Value {value} must be less than {self.max_val}",
                        value=value,
                        expected=f"< {self.max_val}",
                    )
                )

        return result


class LengthValidator(Validator):
    def __init__(self, min_length: int | None = None, max_length: int | None = None):
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)

        try:
            length = len(value)
        except TypeError:
            result.add_error(ValidationError(path=path, message="Value has no length", value=value))
            return result

        if self.min_length is not None and length < self.min_length:
            result.add_error(
                ValidationError(
                    path=path,
                    message=f"Length {length} is below minimum {self.min_length}",
                    value=value,
                    expected=f">= {self.min_length}",
                )
            )

        if self.max_length is not None and length > self.max_length:
            result.add_error(
                ValidationError(
                    path=path,
                    message=f"Length {length} exceeds maximum {self.max_length}",
                    value=value,
                    expected=f"<= {self.max_length}",
                )
            )

        return result


class PatternValidator(Validator):
    def __init__(self, pattern: str, flags: int = 0):
        self.pattern = re.compile(pattern, flags)
        self.pattern_str = pattern

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)

        if not isinstance(value, str):
            result.add_error(
                ValidationError(path=path, message="Value must be a string", value=value)
            )
            return result

        if not self.pattern.match(value):
            result.add_error(
                ValidationError(
                    path=path,
                    message=f"Value does not match pattern {self.pattern_str}",
                    value=value,
                    expected=self.pattern_str,
                )
            )

        return result


class EnumValidator(Validator):
    def __init__(self, allowed_values: list[Any]):
        self.allowed_values = allowed_values

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)

        if value not in self.allowed_values:
            result.add_error(
                ValidationError(
                    path=path,
                    message=f"Value must be one of {self.allowed_values}",
                    value=value,
                    expected=str(self.allowed_values),
                )
            )

        return result


class URLValidator(Validator):
    URL_PATTERN = re.compile(
        r"^(https?|wss?)://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)

        if not isinstance(value, str):
            result.add_error(
                ValidationError(path=path, message="URL must be a string", value=value)
            )
            return result

        if not self.URL_PATTERN.match(value):
            result.add_error(
                ValidationError(
                    path=path,
                    message="Invalid URL format",
                    value=value,
                    suggestion="Use format: http(s)://host[:port]/path",
                )
            )

        return result


class EmailValidator(Validator):
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)

        if not isinstance(value, str):
            result.add_error(
                ValidationError(path=path, message="Email must be a string", value=value)
            )
            return result

        if not self.EMAIL_PATTERN.match(value):
            result.add_error(
                ValidationError(path=path, message="Invalid email format", value=value)
            )

        return result


class PathValidator(Validator):
    def __init__(
        self,
        must_exist: bool = False,
        must_be_file: bool = False,
        must_be_dir: bool = False,
        allow_relative: bool = True,
    ):
        self.must_exist = must_exist
        self.must_be_file = must_be_file
        self.must_be_dir = must_be_dir
        self.allow_relative = allow_relative

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)

        if not isinstance(value, str):
            result.add_error(
                ValidationError(path=path, message="Path must be a string", value=value)
            )
            return result

        p = Path(value)

        if not self.allow_relative and not p.is_absolute():
            result.add_error(
                ValidationError(path=path, message="Path must be absolute", value=value)
            )

        if self.must_exist and not p.exists():
            result.add_error(ValidationError(path=path, message="Path does not exist", value=value))

        if self.must_be_file and p.exists() and not p.is_file():
            result.add_error(ValidationError(path=path, message="Path must be a file", value=value))

        if self.must_be_dir and p.exists() and not p.is_dir():
            result.add_error(
                ValidationError(path=path, message="Path must be a directory", value=value)
            )

        return result


class SchemaValidator(Validator):
    def __init__(self, schema: dict[str, Any]):
        self.schema = schema
        self._field_validators: dict[str, list[Validator]] = {}
        self._parse_schema()

    def _parse_schema(self):
        for field_name, field_def in self.schema.items():
            validators = []

            if isinstance(field_def, dict):
                field_type = field_def.get("type")
                if field_type:
                    validators.append(TypeValidator(field_type))

                if "min" in field_def or "max" in field_def:
                    validators.append(
                        RangeValidator(min_val=field_def.get("min"), max_val=field_def.get("max"))
                    )

                if "min_length" in field_def or "max_length" in field_def:
                    validators.append(
                        LengthValidator(
                            min_length=field_def.get("min_length"),
                            max_length=field_def.get("max_length"),
                        )
                    )

                if "pattern" in field_def:
                    validators.append(PatternValidator(field_def["pattern"]))

                if "enum" in field_def:
                    validators.append(EnumValidator(field_def["enum"]))

                if field_def.get("format") == "url":
                    validators.append(URLValidator())
                elif field_def.get("format") == "email":
                    validators.append(EmailValidator())
                elif field_def.get("format") == "path":
                    validators.append(PathValidator(must_exist=field_def.get("must_exist", False)))

            elif isinstance(field_def, type):
                validators.append(TypeValidator(field_def))

            self._field_validators[field_name] = validators

    def validate(self, value: Any, path: str = "") -> ValidationResult:
        result = ValidationResult(valid=True)

        if not isinstance(value, dict):
            result.add_error(
                ValidationError(path=path, message="Value must be a dictionary", value=value)
            )
            return result

        for field_name, field_def in self.schema.items():
            field_path = f"{path}.{field_name}" if path else field_name

            required = True
            if isinstance(field_def, dict):
                required = field_def.get("required", True)

            if field_name not in value:
                if required:
                    result.add_error(
                        ValidationError(
                            path=field_path, message=f"Required field '{field_name}' is missing"
                        )
                    )
                continue

            field_value = value[field_name]

            for validator in self._field_validators.get(field_name, []):
                field_result = validator.validate(field_value, field_path)
                result.merge(field_result)

        return result


class ConfigValidator:
    def __init__(self):
        self.schema_validators: dict[str, SchemaValidator] = {}
        self.custom_validators: dict[str, Callable] = {}
        self.env_prefix = ""

    def set_env_prefix(self, prefix: str):
        self.env_prefix = prefix

    def register_schema(self, name: str, schema: dict[str, Any]):
        self.schema_validators[name] = SchemaValidator(schema)

    def register_custom_validator(self, name: str, validator: Callable):
        self.custom_validators[name] = validator

    def validate_config(
        self, config: dict[str, Any], schema_name: str | None = None
    ) -> ValidationResult:
        result = ValidationResult(valid=True)

        if schema_name and schema_name in self.schema_validators:
            schema_result = self.schema_validators[schema_name].validate(config)
            result.merge(schema_result)

        for name, validator in self.custom_validators.items():
            try:
                validator_result = validator(config)
                if isinstance(validator_result, ValidationResult):
                    result.merge(validator_result)
                elif validator_result is False:
                    result.add_error(
                        ValidationError(path="", message=f"Custom validator '{name}' failed")
                    )
            except Exception as e:
                result.add_error(
                    ValidationError(path="", message=f"Validator '{name}' raised exception: {e}")
                )

        return result

    def validate_env(self, env_vars: dict[str, str]) -> ValidationResult:
        result = ValidationResult(valid=True)

        for key, value in env_vars.items():
            if self.env_prefix and not key.startswith(self.env_prefix):
                continue

            path = f"env.{key}"

            if not value:
                result.add_error(
                    ValidationError(
                        path=path,
                        message=f"Environment variable {key} is empty",
                        level=ValidationLevel.WARNING,
                    )
                )

        return result

    def validate_file(self, file_path: str) -> ValidationResult:
        result = ValidationResult(valid=True)

        path = Path(file_path)
        if not path.exists():
            result.add_error(
                ValidationError(
                    path=file_path, message=f"Configuration file does not exist: {file_path}"
                )
            )
            return result

        try:
            if path.suffix == ".json":
                with open(path, encoding="utf-8") as f:
                    config = json.load(f)
            elif path.suffix in (".yaml", ".yml"):
                try:
                    import yaml

                    with open(path, encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                except ImportError:
                    result.add_error(
                        ValidationError(
                            path=file_path, message="YAML support requires PyYAML package"
                        )
                    )
                    return result
            else:
                result.add_error(
                    ValidationError(
                        path=file_path, message=f"Unsupported config file format: {path.suffix}"
                    )
                )
                return result

            result.data = config

        except json.JSONDecodeError as e:
            result.add_error(ValidationError(path=file_path, message=f"Invalid JSON: {e}"))
        except Exception as e:
            result.add_error(
                ValidationError(path=file_path, message=f"Failed to read config file: {e}")
            )

        return result


IDLE_SENSE_SCHEMA = {
    "scheduler": {"type": dict, "required": True},
    "scheduler.host": {"type": str, "required": True, "format": "url"},
    "scheduler.port": {"type": int, "required": True, "min": 1, "max": 65535},
    "node": {"type": dict, "required": True},
    "node.id": {"type": str, "required": True, "min_length": 1},
    "node.max_cpu_percent": {"type": (int, float), "min": 0, "max": 100},
    "node.max_memory_percent": {"type": (int, float), "min": 0, "max": 100},
    "sandbox": {"type": dict},
    "sandbox.enabled": {"type": bool},
    "sandbox.timeout_seconds": {"type": int, "min": 1, "max": 3600},
    "logging": {"type": dict},
    "logging.level": {"type": str, "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
}


__all__ = [
    "ValidationLevel",
    "ValidationError",
    "ValidationResult",
    "Validator",
    "TypeValidator",
    "RangeValidator",
    "LengthValidator",
    "PatternValidator",
    "EnumValidator",
    "URLValidator",
    "EmailValidator",
    "PathValidator",
    "SchemaValidator",
    "ConfigValidator",
    "IDLE_SENSE_SCHEMA",
]
