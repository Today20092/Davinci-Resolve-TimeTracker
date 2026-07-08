"""Activity, idle, focus, playback, and render signal tracking."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from ctypes import wintypes
from typing import Protocol

from resolve_time_tracker.session_engine import SessionEngine


@dataclass(frozen=True)
class RuntimeSnapshot:
    project_name: str | None
    page: str | None
    is_rendering: bool
    idle_seconds: float | None
    resolve_is_foreground: bool
    timeline_name: str | None = None
    timeline_id: str | None = None
    timecode: str | None = None


class SnapshotProvider(Protocol):
    def snapshot(self) -> RuntimeSnapshot:
        raise NotImplementedError


class RuntimeTracker:
    def __init__(
        self,
        engine: SessionEngine,
        *,
        idle_timeout_seconds: int,
        snapshot_provider: SnapshotProvider,
    ):
        self.engine = engine
        self.idle_timeout_seconds = idle_timeout_seconds
        self.snapshot_provider = snapshot_provider
        self._previous: RuntimeSnapshot | None = None

    @property
    def previous_snapshot(self) -> RuntimeSnapshot | None:
        return self._previous

    def poll(self, observed_at) -> RuntimeSnapshot:
        snapshot = self.snapshot_provider.snapshot()
        previous = self._previous

        idle_now = (
            snapshot.idle_seconds is not None
            and snapshot.idle_seconds >= self.idle_timeout_seconds
        )
        idle_before = (
            previous is not None
            and previous.idle_seconds is not None
            and previous.idle_seconds >= self.idle_timeout_seconds
        )

        if previous is None or idle_now != idle_before:
            if idle_now:
                self.engine.idle_started(observed_at)
            else:
                self.engine.idle_ended(observed_at)

        if previous is None or snapshot.resolve_is_foreground != previous.resolve_is_foreground:
            if snapshot.resolve_is_foreground:
                self.engine.resolve_focus_gained(observed_at)
            else:
                self.engine.resolve_focus_lost(observed_at)

        if previous is None or snapshot.page != previous.page:
            self.engine.page_changed(observed_at, snapshot.page or "Unknown")

        if previous is None or snapshot.project_name != previous.project_name:
            if snapshot.project_name:
                self.engine.project_changed(observed_at, snapshot.project_name)
            else:
                self.engine.project_closed(observed_at)

        if previous is None or snapshot.is_rendering != previous.is_rendering:
            if snapshot.is_rendering:
                self.engine.rendering_started(observed_at)
            else:
                self.engine.rendering_finished(observed_at)

        self.engine.heartbeat_tick(observed_at)
        self._previous = snapshot
        return snapshot


class SequenceSnapshotProvider:
    def __init__(self, snapshots: list[RuntimeSnapshot]):
        self.snapshots = list(snapshots)

    def snapshot(self) -> RuntimeSnapshot:
        if not self.snapshots:
            raise RuntimeError("No dry-run snapshots remain")
        return self.snapshots.pop(0)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


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
