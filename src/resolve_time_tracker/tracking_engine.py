"""Deep tracking module from runtime snapshots to persisted Sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from resolve_time_tracker.database import SQLiteStore


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


class TrackingEngine:
    def __init__(self, store: SQLiteStore, *, snapshot_provider: Any):
        store.recover_active_session()
        self._store = store
        self._snapshot_provider = snapshot_provider
        self._session = _SessionState(store)
        self._previous: RuntimeSnapshot | None = None
        self._previous_idle: bool | None = None
        self._tracking_enabled = True

    @property
    def previous_snapshot(self) -> RuntimeSnapshot | None:
        return self._previous

    @property
    def tracking_enabled(self) -> bool:
        return self._tracking_enabled

    def poll(self, observed_at: datetime) -> RuntimeSnapshot:
        if not self._tracking_enabled:
            self._session.resolve_closed(observed_at)
            self._previous_idle = None
            return self._previous or RuntimeSnapshot(None, None, False, None, False)

        snapshot = self._snapshot_provider.snapshot()
        previous = self._previous
        idle_now = (
            snapshot.idle_seconds is not None
            and snapshot.idle_seconds >= self._store.idle_timeout_seconds()
        )

        if previous is None or idle_now != self._previous_idle:
            if idle_now:
                self._session.idle_started(observed_at)
            else:
                self._session.idle_ended(observed_at)

        if (
            previous is None
            or snapshot.resolve_is_foreground != previous.resolve_is_foreground
        ):
            if snapshot.resolve_is_foreground:
                self._session.resolve_focus_gained(observed_at)
            else:
                self._session.resolve_focus_lost(observed_at)

        if previous is None or snapshot.page != previous.page:
            self._session.page_changed(observed_at, snapshot.page or "Unknown")

        if previous is None or snapshot.project_name != previous.project_name:
            if snapshot.project_name:
                self._session.project_changed(observed_at, snapshot.project_name)
            else:
                self._session.project_closed(observed_at)

        if previous is None or snapshot.is_rendering != previous.is_rendering:
            if snapshot.is_rendering:
                self._session.rendering_started(observed_at)
            else:
                self._session.rendering_finished(observed_at)

        self._session.heartbeat_tick(observed_at)
        self._previous = snapshot
        self._previous_idle = idle_now
        return snapshot

    def pause(self, observed_at: datetime) -> None:
        self._tracking_enabled = False
        self._session.resolve_closed(observed_at)

    def resume(self) -> None:
        self._tracking_enabled = True
        self._previous = None
        self._previous_idle = None

    def close(self, observed_at: datetime) -> None:
        self._session.resolve_closed(observed_at)


class _SessionState:
    def __init__(self, store: SQLiteStore):
        self._store = store
        self._project_id: int | None = None
        self._page = "Unknown"
        self._is_idle = False
        self._has_focus = True
        self._is_rendering = False

    def project_changed(self, observed_at: datetime, project_name: str) -> None:
        self._close(observed_at)
        self._project_id = self._store.upsert_project(project_name)
        self._open_if_billable(observed_at)

    def project_closed(self, observed_at: datetime) -> None:
        self._close(observed_at)
        self._project_id = None

    def page_changed(self, observed_at: datetime, page: str) -> None:
        was_billable = self._is_billable()
        if was_billable:
            self._close(observed_at)
        self._page = page or "Unknown"
        if was_billable:
            self._open(observed_at)

    def rendering_started(self, observed_at: datetime) -> None:
        if self._is_rendering:
            return
        self._close(observed_at)
        self._is_rendering = True
        self._open_if_billable(observed_at)

    def rendering_finished(self, observed_at: datetime) -> None:
        if not self._is_rendering:
            return
        self._close(observed_at)
        self._is_rendering = False
        self._open_if_billable(observed_at)

    def idle_started(self, observed_at: datetime) -> None:
        if self._is_idle:
            return
        if not self._is_rendering:
            self._close(observed_at)
        self._is_idle = True

    def idle_ended(self, observed_at: datetime) -> None:
        if not self._is_idle:
            return
        self._is_idle = False
        self._open_if_billable(observed_at)

    def resolve_focus_lost(self, observed_at: datetime) -> None:
        if not self._has_focus:
            return
        if not self._is_rendering:
            self._close(observed_at)
        self._has_focus = False

    def resolve_focus_gained(self, observed_at: datetime) -> None:
        if self._has_focus:
            return
        self._has_focus = True
        self._open_if_billable(observed_at)

    def heartbeat_tick(self, observed_at: datetime) -> None:
        if self._store.active_session() is not None:
            self._store.update_heartbeat(observed_at)

    def resolve_closed(self, observed_at: datetime) -> None:
        self._close(observed_at)

    def _is_billable(self) -> bool:
        if self._project_id is None:
            return False
        if self._is_rendering:
            return True
        return not self._is_idle and self._has_focus

    def _open_if_billable(self, observed_at: datetime) -> None:
        if self._is_billable():
            self._open(observed_at)

    def _open(self, observed_at: datetime) -> None:
        if self._project_id is None or self._store.active_session() is not None:
            return
        self._store.open_active_session(
            project_id=self._project_id,
            started_at=observed_at,
            page=self._page,
            activity_category="rendering" if self._is_rendering else "editing",
        )

    def _close(self, observed_at: datetime) -> None:
        self._store.close_active_session(observed_at)
