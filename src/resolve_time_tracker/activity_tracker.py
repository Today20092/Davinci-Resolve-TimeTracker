"""Operating-system activity and foreground probes."""

from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class AlwaysActiveProbe:
    def idle_seconds(self) -> float | None:
        return None

    def resolve_is_foreground(self) -> bool:
        return True

    @property
    def unavailable_reason(self) -> None:
        return None


@dataclass(frozen=True)
class ActivityState:
    idle_seconds: float | None
    resolve_is_foreground: bool | None
    unavailable_reason: str | None = None


class UnavailableActivityProbe:
    def __init__(self, reason: str):
        self.unavailable_reason = reason

    def idle_seconds(self) -> None:
        return None

    def resolve_is_foreground(self) -> None:
        return None


class CachedActivityProbe:
    """Publish activity off the tracking thread, only during a Resolve session."""

    def __init__(
        self,
        probe: MacActivityProbe | LinuxActivityProbe,
        *,
        interval_seconds: float = 15,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._probe = probe
        self._interval_seconds = max(15, interval_seconds)
        self._clock = clock
        self._sampled_at: float | None = None
        self._state = ActivityState(None, None, "activity has not been sampled")
        self._condition = threading.Condition()
        self._present = False
        self._closed = False
        self._generation = 0
        self._thread: threading.Thread | None = None

    def set_resolve_present(self, present: bool) -> None:
        with self._condition:
            if self._closed or present == self._present:
                return
            self._present = present
            self._generation += 1
            self._state = ActivityState(None, None, "activity has not been sampled")
            if present and self._thread is None:
                self._thread = threading.Thread(
                    target=self._run, name="activity-probe", daemon=True
                )
                self._thread.start()
            self._condition.notify_all()

    def snapshot(self) -> ActivityState:
        with self._condition:
            return self._state

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._present = False
            self._state = ActivityState(None, None, "activity probe stopped")
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join()

    @property
    def unavailable_reason(self) -> str | None:
        return self.snapshot().unavailable_reason

    def idle_seconds(self) -> float | None:
        return self.snapshot().idle_seconds

    def resolve_is_foreground(self) -> bool | None:
        return self.snapshot().resolve_is_foreground

    def _run(self) -> None:
        while True:
            with self._condition:
                if self._closed:
                    return
                if not self._present:
                    self._condition.wait()
                    continue
                now = self._clock()
                remaining = (
                    0
                    if self._sampled_at is None
                    else self._interval_seconds - (now - self._sampled_at)
                )
                if remaining > 0:
                    self._condition.wait(remaining)
                    continue
                self._sampled_at = now
                generation = self._generation
            try:
                state = self._probe.sample()
            except Exception:
                state = ActivityState(None, None, "activity probe failed")
            with self._condition:
                if (
                    self._present
                    and not self._closed
                    and generation == self._generation
                ):
                    self._state = state
                self._condition.notify_all()


class WindowsActivityProbe:
    def snapshot(self) -> ActivityState:
        try:
            idle = self.idle_seconds()
            if idle is None:
                return ActivityState(
                    None, None, "Windows activity detection is unavailable"
                )
            return ActivityState(idle, self.resolve_is_foreground())
        except OSError:
            return ActivityState(
                None, None, "Windows activity detection is unavailable"
            )

    def idle_seconds(self) -> float | None:
        last_input = LASTINPUTINFO()
        last_input.cbSize = ctypes.sizeof(last_input)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input)):
            return None
        tick_count = ctypes.windll.kernel32.GetTickCount()
        elapsed_ms = (tick_count - last_input.dwTime) & 0xFFFFFFFF
        return elapsed_ms / 1000

    def foreground_window_title(self) -> str:
        ctypes.windll.user32.GetForegroundWindow.restype = wintypes.HWND
        ctypes.windll.user32.GetWindowTextW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        title = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, len(title))
        return title.value

    def resolve_is_foreground(self) -> bool:
        return "DaVinci Resolve" in self.foreground_window_title()

    @property
    def unavailable_reason(self) -> None:
        return None


class MacActivityProbe:
    def __init__(
        self,
        run_text: Callable[[list[str]], str | None] | None = None,
        ioreg: str = "ioreg",
        osascript: str = "osascript",
    ):
        self.run_text = run_text or _run_text
        self.ioreg = ioreg
        self.osascript = osascript

    def idle_seconds(self) -> float | None:
        return self.sample().idle_seconds

    def resolve_is_foreground(self) -> bool:
        return self.sample().resolve_is_foreground is True

    def sample(self) -> ActivityState:
        idle_output = self.run_text([self.ioreg, "-c", "IOHIDSystem"])
        foreground_output = self.run_text(
            [
                self.osascript,
                "-e",
                'tell application "System Events" to get name of first process whose frontmost is true',
            ]
        )
        if (
            idle_output is None
            or not foreground_output
            or not foreground_output.strip()
        ):
            return ActivityState(None, None, "activity probe failed")
        match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', idle_output)
        if match is None:
            return ActivityState(
                None, None, "activity probe returned malformed idle data"
            )
        return ActivityState(
            int(match.group(1)) / 1_000_000_000,
            "DaVinci Resolve" in foreground_output,
        )

    @property
    def unavailable_reason(self) -> None:
        return None


class LinuxActivityProbe:
    def __init__(self, run_text: Callable[[list[str]], str | None] | None = None):
        self.run_text = run_text or _run_text

    def idle_seconds(self) -> float | None:
        return self.sample().idle_seconds

    def resolve_is_foreground(self) -> bool:
        return self.sample().resolve_is_foreground is True

    def sample(self) -> ActivityState:
        idle_output = self.run_text(["xprintidle"])
        foreground_output = self.run_text(
            ["xdotool", "getactivewindow", "getwindowname"]
        )
        if (
            idle_output is None
            or not foreground_output
            or not foreground_output.strip()
        ):
            return ActivityState(None, None, "activity probe failed")
        try:
            idle_seconds = int(idle_output.strip()) / 1000
            if idle_seconds < 0:
                raise ValueError("negative idle time")
        except ValueError:
            return ActivityState(
                None, None, "activity probe returned malformed idle data"
            )
        return ActivityState(idle_seconds, "DaVinci Resolve" in foreground_output)

    @property
    def unavailable_reason(self) -> None:
        return None


def default_activity_probe() -> (
    WindowsActivityProbe
    | CachedActivityProbe
    | UnavailableActivityProbe
    | AlwaysActiveProbe
):
    if os.name == "nt":
        return WindowsActivityProbe()
    if platform.system() == "Darwin":
        ioreg = _command_path("ioreg", "/usr/sbin/ioreg")
        osascript = _command_path("osascript", "/usr/bin/osascript")
        if ioreg and osascript:
            return CachedActivityProbe(
                MacActivityProbe(ioreg=ioreg, osascript=osascript)
            )
        return UnavailableActivityProbe("macOS activity utilities are unavailable")
    if (
        platform.system() == "Linux"
        and os.environ.get("XDG_SESSION_TYPE", "").lower() != "wayland"
        and os.environ.get("DISPLAY")
        and shutil.which("xprintidle")
        and shutil.which("xdotool")
    ):
        return CachedActivityProbe(LinuxActivityProbe())
    if platform.system() == "Linux":
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            return UnavailableActivityProbe("Wayland activity detection is unsupported")
        return UnavailableActivityProbe("X11 activity detection is unavailable")
    return UnavailableActivityProbe(
        "activity detection is unsupported on this platform"
    )


def _run_text(command: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            command, text=True, stderr=subprocess.DEVNULL, timeout=2
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _command_path(name: str, fallback: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    return fallback if Path(fallback).exists() else None
