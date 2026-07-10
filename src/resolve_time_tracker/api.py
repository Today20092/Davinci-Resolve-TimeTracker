"""FastAPI sidecar for the Electron companion UI."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.tracking_engine import TrackingEngine


Now = Callable[[], datetime]


class SettingsUpdate(BaseModel):
    idle_timeout_seconds: int


class SessionUpdate(BaseModel):
    started_at_utc: str
    ended_at_utc: str
    page: str
    activity_category: str


class ApiState:
    def __init__(
        self,
        store: SQLiteStore,
        *,
        tracking_engine: TrackingEngine | None = None,
        now: Now | None = None,
    ):
        self.store = store
        self.tracking_engine = tracking_engine
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.last_runtime_error: str | None = None
        self.lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        with self.lock:
            return self._status_unlocked()

    def refresh(self) -> dict[str, Any]:
        with self.lock:
            if self.tracking_engine is not None:
                try:
                    self._poll_unlocked()
                    self.last_runtime_error = None
                except Exception as exc:
                    self.last_runtime_error = f"{type(exc).__name__}: {exc}"
            return self._status_unlocked()

    def pause(self) -> dict[str, Any]:
        with self.lock:
            if self.tracking_engine is not None:
                self.tracking_engine.pause(self.now())
            return self._status_unlocked()

    def resume(self) -> dict[str, Any]:
        with self.lock:
            if self.tracking_engine is not None:
                self.tracking_engine.resume()
                try:
                    self._poll_unlocked()
                    self.last_runtime_error = None
                except Exception as exc:
                    self.last_runtime_error = f"{type(exc).__name__}: {exc}"
            return self._status_unlocked()

    def projects(self) -> list[dict[str, Any]]:
        with self.lock:
            return [
                {
                    "project_name": row["project_name"],
                    "session_count": row["session_count"],
                    "duration_seconds": row["duration_seconds"],
                    "duration": _duration(row["duration_seconds"]),
                    "last_session_date": row["last_session_date"],
                }
                for row in self.store.project_summaries()
            ]

    def sessions(self) -> list[dict[str, Any]]:
        with self.lock:
            return [self._session(row) for row in self.store.sessions()]

    def settings(self) -> dict[str, Any]:
        with self.lock:
            return self._settings_unlocked()

    def update_settings(self, update: SettingsUpdate) -> dict[str, Any]:
        with self.lock:
            try:
                self.store.set_idle_timeout_seconds(update.idle_timeout_seconds)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return self._settings_unlocked()

    def update_session(self, session_id: int, update: SessionUpdate) -> dict[str, Any]:
        with self.lock:
            try:
                self.store.update_session(
                    session_id,
                    started_at=_parse_utc(update.started_at_utc),
                    ended_at=_parse_utc(update.ended_at_utc),
                    page=update.page,
                    activity_category=update.activity_category,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return self._session_by_id_unlocked(session_id)

    def csv(self) -> str:
        with self.lock:
            output = StringIO()
            self.store.write_csv(output)
            return output.getvalue()

    def events(self, *, once: bool, poll_interval_seconds: float) -> Iterator[str]:
        while True:
            yield _sse("status", self.refresh())
            if once:
                return
            time.sleep(poll_interval_seconds)

    def _poll_unlocked(self) -> None:
        if self.tracking_engine is None:
            return
        self.tracking_engine.poll(self.now())

    def _status_unlocked(self) -> dict[str, Any]:
        active = self.store.active_session_summary()
        snapshot = (
            self.tracking_engine.previous_snapshot
            if self.tracking_engine is not None
            else None
        )
        status = {
            "connection": "connected",
            "project": "none",
            "page": "none",
            "state": "paused",
            "active_elapsed_seconds": 0,
            "active_elapsed": "0:00:00",
            "heartbeat": "none",
            "tracking_enabled": True,
            "db_path": str(self.store.path),
        }
        if active is not None:
            started = _parse_utc(active["started_at_utc"])
            elapsed = max(0, int((self.now() - started).total_seconds()))
            status.update(
                {
                    "project": active["project_name"],
                    "page": active["page"],
                    "state": active["activity_category"],
                    "active_elapsed_seconds": elapsed,
                    "active_elapsed": _duration(elapsed),
                    "heartbeat": active["last_heartbeat_at_utc"] or "none",
                }
            )
        elif snapshot is not None:
            status["project"] = snapshot.project_name or "none"
            status["page"] = snapshot.page or "none"
        if self.tracking_engine is not None:
            status["tracking_enabled"] = self.tracking_engine.tracking_enabled
            if not self.tracking_engine.tracking_enabled:
                status["state"] = "manual pause"
        if self.last_runtime_error:
            status["connection"] = "error"
            status["heartbeat"] = self.last_runtime_error
        return status

    def _settings_unlocked(self) -> dict[str, Any]:
        seconds = self.store.idle_timeout_seconds()
        return {
            "idle_timeout_seconds": seconds,
            "idle_timeout_minutes": max(1, round(seconds / 60)),
        }

    def _session_by_id_unlocked(self, session_id: int) -> dict[str, Any]:
        for row in self.store.sessions():
            if row["id"] == session_id:
                return self._session(row)
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    def _session(self, row: Any) -> dict[str, Any]:
        duration = _session_duration(row)
        return {
            "id": row["id"],
            "project_name": row["project_name"],
            "started_at_utc": row["started_at_utc"],
            "ended_at_utc": row["ended_at_utc"],
            "duration_seconds": duration,
            "duration": _duration(duration),
            "page": row["page"],
            "activity_category": row["activity_category"],
        }


def create_app(
    store: SQLiteStore,
    *,
    tracking_engine: TrackingEngine | None = None,
    now: Now | None = None,
    poll_interval_seconds: float = 5,
) -> FastAPI:
    api = ApiState(store, tracking_engine=tracking_engine, now=now)
    app = FastAPI(title="Resolve Time Tracker")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.api = api

    @app.get("/status")
    def status() -> dict[str, Any]:
        return api.status()

    @app.post("/refresh")
    def refresh() -> dict[str, Any]:
        return api.refresh()

    @app.get("/projects")
    def projects() -> list[dict[str, Any]]:
        return api.projects()

    @app.get("/sessions")
    def sessions() -> list[dict[str, Any]]:
        return api.sessions()

    @app.get("/settings")
    def settings() -> dict[str, Any]:
        return api.settings()

    @app.post("/tracking/pause")
    def pause_tracking() -> dict[str, Any]:
        return api.pause()

    @app.post("/tracking/resume")
    def resume_tracking() -> dict[str, Any]:
        return api.resume()

    @app.post("/settings")
    def update_settings(update: SettingsUpdate) -> dict[str, Any]:
        return api.update_settings(update)

    @app.post("/sessions/{session_id}")
    def update_session(session_id: int, update: SessionUpdate) -> dict[str, Any]:
        return api.update_session(session_id, update)

    @app.get("/export.csv")
    def export_csv() -> Response:
        return Response(api.csv(), media_type="text/csv")

    @app.get("/events")
    def events(once: bool = False) -> StreamingResponse:
        return StreamingResponse(
            api.events(once=once, poll_interval_seconds=poll_interval_seconds),
            media_type="text/event-stream",
        )

    return app


def run_api(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    enable_tracking: bool = True,
) -> None:
    import uvicorn

    store = SQLiteStore(db_path, check_same_thread=False)
    try:
        tracking_engine = None
        if enable_tracking:
            from resolve_time_tracker.resolve_bridge import ResolveBridge

            tracking_engine = TrackingEngine(store, snapshot_provider=ResolveBridge())
        uvicorn.run(
            create_app(store, tracking_engine=tracking_engine), host=host, port=port
        )
    finally:
        store.close()


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _session_duration(row: Any) -> int:
    started = _parse_utc(row["started_at_utc"])
    ended = _parse_utc(row["ended_at_utc"])
    return max(0, int((ended - started).total_seconds()))


def _duration(seconds: int) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"
