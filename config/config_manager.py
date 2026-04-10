"""
Unified Configuration manager for centralized configuration management.

Provides:
- Single source of truth for configuration values
- Environment variable support
- YAML configuration file support
- Default values with fallback
- Type-safe access with proper error handling

Usage:
    from config_manager import get_config, set_config

    # Get nested config value
    config = get_config("scheduler.url")

    # Or set a config value
    config.set_config("scheduler.url", "http://localhost:8000")
"""

import json
import os
from pathlib import Path
from typing import Any, Callable, Optional

import yaml


class ConfigError(Exception):
    """Configuration related errors."""

    pass


class ConfigManager:
    """
    Unified configuration manager for centralized configuration management.

    Provides:
    - Single source of truth for configuration values
    - Environment variable support
    - YAML configuration file support
    - Default values with fallback
    - Type-safe access with proper error handling
    """

    _instance = None
    _config: dict[str, Any] = {}
    _config_file: Optional[Path] = None
    _env_prefix: str = ""
    _defaults: dict[str, Any] = {}

    DEFAULT_CONFIG_FILES = [
        "config/config.yaml",
        "config/.env",
    ]

    ENV_TYPE_PARSERS: dict[str, Callable[[str], Any]] = {
        "s": str,
        "i": int,
        "f": float,
        "b": lambda x: x.lower() in ("true", "1", "yes"),
    }

    def __init__(self, config_file: Optional[str] = None, env_prefix: str = "IDLE_"):
        self._config_file = Path(config_file) if config_file else None
        self._env_prefix = env_prefix
        self._defaults = {}
        self._config = {}
        self._load_config()

    def _load_config(self) -> dict[str, Any]:
        if self._config_file and self._config_file.exists():
            try:
                with open(self._config_file, encoding="utf-8") as f:
                    config_data = yaml.safe_load(f)
                    if config_data:
                        self._config.update(config_data)
            except yaml.YAMLError as e:
                raise ConfigError(f"Invalid YAML in config file: {e}") from e
            except Exception as e:
                raise ConfigError(f"Error loading config file: {e}") from e

        if self._env_prefix:
            for key, value in os.environ.items():
                if key.startswith(self._env_prefix):
                    config_key = key[len(self._env_prefix) :]
                    self._config[config_key] = self._parse_env_value(value)

        return self._config

    def _parse_env_value(self, value: str) -> Any:
        if value.startswith(("s:", "i:", "f:", "b:")):
            type_prefix, actual_value = value[0], value[2:]
            parser = self.ENV_TYPE_PARSERS.get(type_prefix)
            if parser:
                try:
                    return parser(actual_value)
                except (ValueError, TypeError):
                    return actual_value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (dot-separated for nested access)
            default: Default value if key not found

        Returns:
            Configuration value
        """
        if key in self._config:
            return self._config[key]

        env_key = f"{self._env_prefix}{key}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return self._parse_env_value(env_value)

        return self._defaults.get(key, default)

    def set(self, key: str, value: Any, override: bool = True) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
            override: If True, override existing value
        """
        if override or key not in self._config:
            self._config[key] = value

    def get_all(self) -> dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            Dictionary of all configuration values
        """
        result = dict(self._config)
        result.update(self._defaults)
        return result

    def load_defaults(self, defaults: Optional[dict[str, Any]] = None) -> None:
        """Load default configuration values."""
        if defaults:
            self._defaults = defaults
        self._load_config()

        for key, value in self._defaults.items():
            if key not in self._config:
                self._config[key] = value

    def get_config_files(self) -> list[Path]:
        """Get list of configuration files."""
        return [self._config_file] if self._config_file else []

    def get_env_prefix(self) -> str:
        """Get environment variable prefix."""
        return self._env_prefix

    def get_defaults(self) -> dict[str, Any]:
        """Get default configuration values."""
        return dict(self._defaults)

    def get_stats(self) -> dict[str, Any]:
        """
        Get configuration statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "config_file": str(self._config_file) if self._config_file else None,
            "env_prefix": self._env_prefix,
            "defaults": dict(self._defaults),
            "config": dict(self._config),
        }


def get_config(key: str, default: Any = None) -> Any:
    """Get a configuration value from the global config manager."""
    return _config_manager.get(key, default)


def set_config(key: str, value: Any, override: bool = True) -> None:
    """Set a configuration value in the global config manager."""
    _config_manager.set(key, value, override)


_config_manager = ConfigManager()
