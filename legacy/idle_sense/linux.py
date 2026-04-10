"""
idle_sense/linux.py
Linux idle detector using X11 idle time and /proc filesystem

借鉴自:
- xprintidle (X11 idle time detection)
- systemd-logind (session idle detection)
- /proc filesystem (CPU/memory stats)
"""

import os
import time
from typing import Optional

# psutil 作为可选依赖，用于获取CPU/内存使用率
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# X11 相关依赖（可选）
try:
    import Xlib.display

    XLIB_AVAILABLE = True
except ImportError:
    XLIB_AVAILABLE = False


class LinuxIdleDetector:
    """
    Linux idle detector supporting multiple backends:

    1. X11 Screensaver extension (most accurate for GUI sessions)
    2. /proc/stat (CPU usage based detection)
    3. systemd-logind (session idle detection)
    """

    def __init__(
        self,
        idle_threshold_sec: int = 300,
        cpu_threshold: float = 15.0,
        memory_threshold: float = 70.0,
        display: Optional[str] = None,
    ):
        self.idle_threshold_sec = idle_threshold_sec
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.display = display or os.environ.get("DISPLAY", ":0")

        self._display = None
        self._x11_available = False
        self._init_x11()

        self._prev_cpu_times = None
        self._prev_time = None

    def _init_x11(self) -> None:
        try:
            if XLIB_AVAILABLE:
                self._display = Xlib.display.Display(self.display)
                self._x11_available = True
        except Exception:
            self._x11_available = False

    def _get_x11_idle_time_ms(self) -> Optional[int]:
        if not self._x11_available or self._display is None:
            return None

        try:
            info = self._display.screen().root.query_screensaver()
            return info.idle if hasattr(info, "idle") else None
        except Exception:
            return None

    def _get_xprintidle(self) -> Optional[int]:
        try:
            import subprocess

            result = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except Exception:
            pass
        return None

    def _get_console_idle_time_ms(self) -> int:
        try:
            import subprocess

            result = subprocess.run(["who", "-u"], capture_output=True, text=True, timeout=2)
            tty_stats = result.stdout
            if not tty_stats:
                return 0

            import re

            idle_pattern = r"(\d+):(\d+)"
            max_idle_seconds = 0

            for match in re.finditer(idle_pattern, tty_stats):
                hours, minutes = int(match.group(1)), int(match.group(2))
                idle_seconds = hours * 3600 + minutes * 60
                max_idle_seconds = max(max_idle_seconds, idle_seconds)

            return max_idle_seconds * 1000
        except Exception:
            return 0

    def get_user_idle_time_ms(self) -> int:
        idle_time = self._get_x11_idle_time_ms()
        if idle_time is not None:
            return idle_time

        idle_time = self._get_xprintidle()
        if idle_time is not None:
            return idle_time

        return self._get_console_idle_time_ms()

    def is_screen_locked(self) -> bool:
        try:
            import subprocess

            result = subprocess.run(
                ["loginctl", "list-sessions", "--no-legend"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.splitlines():
                    session_id = line.strip().split()[0] if line.strip() else None
                    if session_id:
                        try:
                            session_result = subprocess.run(
                                ["loginctl", "show-session", session_id, "--property=LockedHint"],
                                capture_output=True,
                                text=True,
                                timeout=1,
                            )
                            if session_result.returncode == 0 and "yes" in session_result.stdout:
                                return True
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            import subprocess

            result = subprocess.run(
                ["gnome-screensaver-command", "-q"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and "is active" in result.stdout:
                return True
        except Exception:
            pass

        try:
            lock_files = [
                "/tmp/.X0-lock",
                "/var/run/screensaver",
            ]
            for lock_file in lock_files:
                if os.path.exists(lock_file):
                    return True
        except Exception:
            pass

        return False

    def get_cpu_memory_usage(self) -> tuple[float, float]:
        if PSUTIL_AVAILABLE:
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            return cpu_usage, memory.percent

        return self._get_cpu_memory_from_proc()

    def _get_cpu_memory_from_proc(self) -> tuple[float, float]:
        try:
            with open("/proc/stat") as f:
                line = f.readline()
                parts = line.split()[1:8]
                cpu_times = [int(x) for x in parts]

            current_time = time.time()

            if self._prev_cpu_times is not None and self._prev_time is not None:
                time_delta = current_time - self._prev_time
                cpu_delta = sum(cpu_times) - sum(self._prev_cpu_times)

                if time_delta > 0 and cpu_delta > 0:
                    idle_delta = cpu_times[3] - self._prev_cpu_times[3]
                    cpu_usage = 100.0 * (1.0 - idle_delta / cpu_delta)
                else:
                    cpu_usage = 0.0
            else:
                cpu_usage = 0.0

            self._prev_cpu_times = cpu_times
            self._prev_time = current_time

            memory_usage = self._get_memory_usage_from_proc()

            return max(0.0, min(100.0, cpu_usage)), memory_usage
        except Exception:
            return 0.0, 0.0

    def _get_memory_usage_from_proc(self) -> float:
        try:
            with open("/proc/meminfo") as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    key = parts[0].rstrip(":")
                    value = int(parts[1])
                    meminfo[key] = value

            total = meminfo.get("MemTotal", 1)
            available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            used = total - available

            return 100.0 * used / total
        except Exception:
            return 0.0

    def is_idle(self) -> bool:
        idle_time_ms = self.get_user_idle_time_ms()
        idle_time_sec = idle_time_ms / 1000.0

        if idle_time_sec >= self.idle_threshold_sec:
            return True

        if self.is_screen_locked():
            return True

        cpu_usage, memory_usage = self.get_cpu_memory_usage()

        return cpu_usage < self.cpu_threshold and memory_usage < self.memory_threshold

    def get_system_status(self) -> dict:
        idle_time_ms = self.get_user_idle_time_ms()
        cpu_usage, memory_usage = self.get_cpu_memory_usage()
        screen_locked = self.is_screen_locked()

        is_idle = (
            idle_time_ms / 1000.0 >= self.idle_threshold_sec
            or screen_locked
            or (cpu_usage < self.cpu_threshold and memory_usage < self.memory_threshold)
        )

        return {
            "platform": "Linux",
            "idle": is_idle,
            "idle_time": idle_time_ms / 1000.0,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "screen_locked": screen_locked,
            "detection_method": "x11" if self._x11_available else "proc",
            "thresholds": {
                "idle_sec": self.idle_threshold_sec,
                "cpu_percent": self.cpu_threshold,
                "memory_percent": self.memory_threshold,
            },
        }


def is_idle(
    idle_threshold_sec: int = 300, cpu_threshold: float = 15.0, memory_threshold: float = 70.0
) -> bool:
    detector = LinuxIdleDetector(
        idle_threshold_sec=idle_threshold_sec,
        cpu_threshold=cpu_threshold,
        memory_threshold=memory_threshold,
    )
    return detector.is_idle()


def get_system_status(
    idle_threshold_sec: int = 300, cpu_threshold: float = 15.0, memory_threshold: float = 70.0
) -> dict:
    detector = LinuxIdleDetector(
        idle_threshold_sec=idle_threshold_sec,
        cpu_threshold=cpu_threshold,
        memory_threshold=memory_threshold,
    )
    return detector.get_system_status()
