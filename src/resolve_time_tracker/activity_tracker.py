"""Operating-system activity and foreground probes."""

from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
from ctypes import wintypes
from pathlib import Path
from typing import Callable


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class AlwaysActiveProbe:
    def idle_seconds(self) -> float | None:
        return None

    def resolve_is_foreground(self) -> bool:
        return True


class WindowsActivityProbe:
    def idle_seconds(self) -> float | None:
        last_input = LASTINPUTINFO()
        last_input.cbSize = ctypes.sizeof(last_input)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input)):
            return None
        tick_count = ctypes.windll.kernel32.GetTickCount()
        elapsed_ms = (tick_count - last_input.dwTime) & 0xFFFFFFFF
        return elapsed_ms / 1000

    def foreground_window_title(self) -> str:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        title = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, len(title))
        return title.value

    def resolve_is_foreground(self) -> bool:
        return "DaVinci Resolve" in self.foreground_window_title()


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
        output = self.run_text([self.ioreg, "-c", "IOHIDSystem"])
        if output is None:
            return None
        match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', output)
        if match is None:
            return None
        return int(match.group(1)) / 1_000_000_000

    def resolve_is_foreground(self) -> bool:
        output = self.run_text(
            [
                self.osascript,
                "-e",
                'tell application "System Events" to get name of first process whose frontmost is true',
            ]
        )
        return output is not None and "DaVinci Resolve" in output


class LinuxActivityProbe:
    def __init__(self, run_text: Callable[[list[str]], str | None] | None = None):
        self.run_text = run_text or _run_text

    def idle_seconds(self) -> float | None:
        output = self.run_text(["xprintidle"])
        if output is None:
            return None
        try:
            return int(output.strip()) / 1000
        except ValueError:
            return None

    def resolve_is_foreground(self) -> bool:
        output = self.run_text(["xdotool", "getactivewindow", "getwindowname"])
        return output is not None and "DaVinci Resolve" in output


def default_activity_probe() -> (
    WindowsActivityProbe | MacActivityProbe | LinuxActivityProbe | AlwaysActiveProbe
):
    if os.name == "nt":
        return WindowsActivityProbe()
    if platform.system() == "Darwin":
        ioreg = _command_path("ioreg", "/usr/sbin/ioreg")
        osascript = _command_path("osascript", "/usr/bin/osascript")
        if ioreg and osascript:
            return MacActivityProbe(ioreg=ioreg, osascript=osascript)
    if (
        platform.system() == "Linux"
        and shutil.which("xprintidle")
        and shutil.which("xdotool")
    ):
        return LinuxActivityProbe()
    return AlwaysActiveProbe()


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
