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
        self._previous: RuntimeSnapshot | None = None
        self._previous_idle: bool | None = None
        self._tracking_enabled = True
        self._project_id: int | None = None
        self._page = "Unknown"
        self._is_idle = False
        self._has_focus = True
        self._is_rendering = False

    @property
    def previous_snapshot(self) -> RuntimeSnapshot | None:
        return self._previous

    @property
    def tracking_enabled(self) -> bool:
        return self._tracking_enabled

    def poll(self, observed_at: datetime) -> RuntimeSnapshot:
        if not self._tracking_enabled:
            self._close(observed_at)
            self._previous_idle = None
            return self._previous or RuntimeSnapshot(None, None, False, None, False)

        snapshot = self._snapshot_provider.snapshot()
        previous = self._previous
        idle_now = (
            snapshot.idle_seconds is not None
            and snapshot.idle_seconds >= self._store.idle_timeout_seconds()
        )

        if previous is None or idle_now != self._previous_idle:
            if idle_now and not self._is_idle:
                if not self._is_rendering:
                    self._close(observed_at)
                self._is_idle = True
            elif not idle_now and self._is_idle:
                self._is_idle = False
                self._open_if_billable(observed_at)

        if (
            previous is None
            or snapshot.resolve_is_foreground != previous.resolve_is_foreground
        ):
            if snapshot.resolve_is_foreground and not self._has_focus:
                self._has_focus = True
                self._open_if_billable(observed_at)
            elif not snapshot.resolve_is_foreground and self._has_focus:
                if not self._is_rendering:
                    self._close(observed_at)
                self._has_focus = False

        same_project = (
            previous is not None and snapshot.project_name == previous.project_name
        )
        if snapshot.page:
            page = snapshot.page
        elif snapshot.is_rendering or not same_project:
            page = "Unknown"
        else:
            page = self._page
        project_changed = previous is None or not same_project
        page_changed = page != self._page
        rendering_changed = snapshot.is_rendering != self._is_rendering
        backfill_unknown = (
            page_changed
            and not project_changed
            and not rendering_changed
            and self._page == "Unknown"
            and page != "Unknown"
            and self._store.active_session() is not None
        )

        if backfill_unknown:
            self._store.update_active_session_page(page)
            self._page = page
        elif project_changed or page_changed or rendering_changed:
            self._close(observed_at)
            self._page = page
            if project_changed:
                if snapshot.project_name:
                    self._project_id = self._store.upsert_project(snapshot.project_name)
                else:
                    self._project_id = None
            self._is_rendering = snapshot.is_rendering
            self._open_if_billable(observed_at)

        if self._store.active_session() is not None:
            self._store.update_heartbeat(observed_at)
        self._previous = snapshot
        self._previous_idle = idle_now
        return snapshot

    def pause(self, observed_at: datetime) -> None:
        self._tracking_enabled = False
        self._close(observed_at)

    def resume(self) -> None:
        self._tracking_enabled = True
        self._previous = None
        self._previous_idle = None

    def close(self, observed_at: datetime) -> None:
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
