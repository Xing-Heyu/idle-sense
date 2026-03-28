"""Unit tests for idle_sense core module."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from legacy.idle_sense import get_platform, get_system_status, is_idle


class TestGetPlatform(unittest.TestCase):
    """Tests for get_platform function."""

    def test_returns_valid_platform(self):
        result = get_platform()
        self.assertIn(result, ["windows", "macos", "linux", "unknown"])

    @patch("platform.system")
    def test_windows_detection(self, mock_system):
        from legacy.idle_sense import core
        core._PLATFORM_NAME_CACHE = None
        mock_system.return_value = "Windows"
        result = get_platform()
        self.assertEqual(result, "windows")

    @patch("platform.system")
    def test_macos_detection(self, mock_system):
        from legacy.idle_sense import core
        core._PLATFORM_NAME_CACHE = None
        mock_system.return_value = "Darwin"
        result = get_platform()
        self.assertEqual(result, "macos")

    @patch("platform.system")
    def test_linux_detection(self, mock_system):
        from legacy.idle_sense import core
        core._PLATFORM_NAME_CACHE = None
        mock_system.return_value = "Linux"
        result = get_platform()
        self.assertEqual(result, "linux")


class TestGetSystemStatus(unittest.TestCase):
    """Tests for get_system_status function."""

    def test_returns_dict(self):
        result = get_system_status()
        self.assertIsInstance(result, dict)

    def test_contains_required_keys(self):
        result = get_system_status()
        required_keys = [
            "cpu_percent",
            "memory_percent",
        ]
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")


class TestIsIdle(unittest.TestCase):
    """Tests for is_idle function."""

    def test_returns_boolean(self):
        result = is_idle()
        self.assertIsInstance(result, bool)

    def test_with_custom_thresholds(self):
        result = is_idle(
            idle_threshold_sec=600,
            cpu_threshold=20.0,
            memory_threshold=80.0
        )
        self.assertIsInstance(result, bool)


class TestIdleDetectionLogic(unittest.TestCase):
    """Tests for idle detection logic."""

    def test_detection_runs_without_error(self):
        try:
            result = is_idle()
            self.assertIsInstance(result, bool)
        except Exception as e:
            self.fail(f"is_idle() raised an exception: {e}")


class TestPlatformModule(unittest.TestCase):
    """Tests for platform module loading."""

    def test_check_platform_module(self):
        from legacy.idle_sense import check_platform_module
        result = check_platform_module()

        self.assertIn("platform", result)
        self.assertIn("loaded", result)
        self.assertIn("error", result)

    def test_get_version(self):
        from legacy.idle_sense import get_version
        version = get_version()

        self.assertIsInstance(version, str)
        self.assertEqual(version, "1.0.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
