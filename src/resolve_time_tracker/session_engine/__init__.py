"""Event-to-Session state machine."""

from __future__ import annotations

from datetime import datetime

from resolve_time_tracker.database import SQLiteStore


class SessionEngine:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.project_id: int | None = None
        self.page = "Unknown"
        self.activity_category = "editing"
        self.is_idle = False
        self.has_focus = True
        self.is_rendering = False

    def project_changed(self, observed_at: datetime, project_name: str) -> None:
        self._close(observed_at)
        self.project_id = self.store.upsert_project(project_name)
        self._open_if_billable(observed_at)

    def project_closed(self, observed_at: datetime) -> None:
        self._close(observed_at)
        self.project_id = None

    def page_changed(self, observed_at: datetime, page: str) -> None:
        was_billable = self._is_billable()
        if was_billable:
            self._close(observed_at)
        self.page = page or "Unknown"
        if was_billable:
            self._open(observed_at)

    def playback_started(self, observed_at: datetime) -> None:
        if self.is_rendering:
            return
        if self._is_billable():
            self._close(observed_at)
        self.activity_category = "playback"
        self._open_if_billable(observed_at)

    def playback_stopped(self, observed_at: datetime) -> None:
        if self.is_rendering:
            return
        if self._is_billable():
            self._close(observed_at)
        self.activity_category = "editing"
        self._open_if_billable(observed_at)

    def rendering_started(self, observed_at: datetime) -> None:
        if self.is_rendering:
            return
        self._close(observed_at)
        self.is_rendering = True
        self._open_if_billable(observed_at)

    def rendering_finished(self, observed_at: datetime) -> None:
        if not self.is_rendering:
            return
        self._close(observed_at)
        self.is_rendering = False
        self._open_if_billable(observed_at)

    def idle_started(self, observed_at: datetime) -> None:
        if self.is_idle:
            return
        if not self.is_rendering:
            self._close(observed_at)
        self.is_idle = True

    def idle_ended(self, observed_at: datetime) -> None:
        if not self.is_idle:
            return
        self.is_idle = False
        self._open_if_billable(observed_at)

    def resolve_focus_lost(self, observed_at: datetime) -> None:
        if not self.has_focus:
            return
        if not self.is_rendering:
            self._close(observed_at)
        self.has_focus = False

    def resolve_focus_gained(self, observed_at: datetime) -> None:
        if self.has_focus:
            return
        self.has_focus = True
        self._open_if_billable(observed_at)

    def heartbeat_tick(self, observed_at: datetime) -> None:
        if self.store.active_session() is not None:
            self.store.update_heartbeat(observed_at)

    def resolve_closed(self, observed_at: datetime) -> None:
        self._close(observed_at)

    def _is_billable(self) -> bool:
        if self.project_id is None:
            return False
        if self.is_rendering:
            return True
        return not self.is_idle and self.has_focus

    def _current_category(self) -> str:
        if self.is_rendering:
            return "rendering"
        return self.activity_category

    def _open_if_billable(self, observed_at: datetime) -> None:
        if self._is_billable():
            self._open(observed_at)

    def _open(self, observed_at: datetime) -> None:
        if self.project_id is None or self.store.active_session() is not None:
            return
        self.store.open_active_session(
            project_id=self.project_id,
            started_at=observed_at,
            page=self.page,
            activity_category=self._current_category(),
        )

    def _close(self, observed_at: datetime) -> None:
        self.store.close_active_session(observed_at)
