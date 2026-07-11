"""FastAPI sidecar for the Electron companion UI."""

from __future__ import annotations

import json
import threading
import time
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.pdf_export import PdfExportOptions, build_project_pdf
from resolve_time_tracker.tracking_engine import TrackingEngine


Now = Callable[[], datetime]
STALE_HEARTBEAT_SECONDS = 15


class SettingsUpdate(BaseModel):
    idle_timeout_seconds: int


class SessionUpdate(BaseModel):
    started_at_utc: str
    ended_at_utc: str
    page: str
    activity_category: str


class PdfExportRequest(BaseModel):
    project_name: str
    show_totals: bool = True
    show_page_chart: bool = True
    show_activity_chart: bool = True
    show_recent_activity: bool = True


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
            return self._projects_unlocked()

    def sessions(self) -> list[dict[str, Any]]:
        with self.lock:
            return self._sessions_unlocked()

    def dashboard(self) -> dict[str, Any]:
        with self.lock:
            if self.tracking_engine is not None:
                try:
                    self._poll_unlocked()
                    self.last_runtime_error = None
                except Exception as exc:
                    self.last_runtime_error = f"{type(exc).__name__}: {exc}"
            status = self._status_unlocked()
            sessions = self._sessions_unlocked()
            current_project, export_preview = self._current_project_unlocked(
                status, sessions
            )
            return {
                "status": status,
                "settings": self._settings_unlocked(),
                "projects": self._projects_unlocked(),
                "sessions": sessions,
                "current_project": current_project,
                "export_preview": export_preview,
            }

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

    def pdf(self, request: PdfExportRequest) -> bytes:
        with self.lock:
            sessions = [self._session(row) for row in self.store.sessions()]
        if not any(
            session["project_name"] == request.project_name for session in sessions
        ):
            raise HTTPException(
                status_code=404, detail=f"Project {request.project_name} not found"
            )
        return build_project_pdf(
            project_name=request.project_name,
            sessions=sessions,
            options=PdfExportOptions(
                show_totals=request.show_totals,
                show_page_chart=request.show_page_chart,
                show_activity_chart=request.show_activity_chart,
                show_recent_activity=request.show_recent_activity,
            ),
            generated_at=self.now(),
        )

    def events(self, *, once: bool, poll_interval_seconds: float) -> Iterator[str]:
        while True:
            self.refresh()
            yield _sse("dashboard", {})
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
            "tracking_status": "resolve_closed",
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
            heartbeat = active["last_heartbeat_at_utc"]
            elapsed = max(0, int((self.now() - started).total_seconds()))
            status.update(
                {
                    "project": active["project_name"],
                    "page": active["page"],
                    "state": active["activity_category"],
                    "active_elapsed_seconds": elapsed,
                    "active_elapsed": _duration(elapsed),
                    "heartbeat": heartbeat or "none",
                    "tracking_status": "active",
                }
            )
            if (
                heartbeat
                and (self.now() - _parse_utc(heartbeat)).total_seconds()
                > STALE_HEARTBEAT_SECONDS
            ):
                status["tracking_status"] = "stale"
        elif snapshot is not None:
            status["project"] = snapshot.project_name or "none"
            status["page"] = snapshot.page or "none"
            if snapshot.project_name:
                status["tracking_status"] = "idle"
        if self.tracking_engine is not None:
            status["tracking_enabled"] = self.tracking_engine.tracking_enabled
            if not self.tracking_engine.tracking_enabled:
                status["state"] = "manual pause"
                status["tracking_status"] = "paused"
        if self.last_runtime_error:
            status["connection"] = "error"
            status["heartbeat"] = self.last_runtime_error
            status["tracking_status"] = "error"
        return status

    def _settings_unlocked(self) -> dict[str, Any]:
        seconds = self.store.idle_timeout_seconds()
        return {
            "idle_timeout_seconds": seconds,
            "idle_timeout_minutes": max(1, round(seconds / 60)),
        }

    def _projects_unlocked(self) -> list[dict[str, Any]]:
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

    def _sessions_unlocked(self) -> list[dict[str, Any]]:
        return [self._session(row) for row in self.store.sessions()]

    def _current_project_unlocked(
        self, status: dict[str, Any], sessions: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
        project = status["project"]
        if project == "none":
            return None, None

        project_sessions = [
            session for session in sessions if session["project_name"] == project
        ]
        activity_totals = {"editing": 0, "playback": 0, "rendering": 0}
        page_totals: dict[str, int] = {}
        today = self.now().astimezone().date()
        today_seconds = 0
        for session in project_sessions:
            seconds = session["duration_seconds"]
            activity_totals[session["activity_category"]] += seconds
            page = _display_page(session["page"], session["activity_category"])
            page_totals[page] = page_totals.get(page, 0) + seconds
            today_seconds += _seconds_on_local_date(
                _parse_utc(session["started_at_utc"]),
                _parse_utc(session["ended_at_utc"]),
                today,
            )

        active = self.store.active_session_summary()
        active_seconds = status["active_elapsed_seconds"]
        if active is not None:
            category = active["activity_category"]
            activity_totals[category] += active_seconds
            page = _display_page(active["page"], category)
            page_totals[page] = page_totals.get(page, 0) + active_seconds
            today_seconds += _seconds_on_local_date(
                _parse_utc(active["started_at_utc"]), self.now(), today
            )

        recent = sorted(
            project_sessions,
            key=lambda session: session["started_at_utc"],
            reverse=True,
        )[:5]
        last_activity = (
            status["heartbeat"]
            if status["tracking_status"] == "active"
            else recent[0]["ended_at_utc"]
            if recent
            else "none"
        )
        tracked_seconds = sum(activity_totals.values())
        current_project = {
            "project": project,
            "totals": {
                "tracked_seconds": tracked_seconds,
                "today_seconds": today_seconds,
                "session_count": len(project_sessions)
                + (1 if active is not None else 0),
            },
            "activity_totals": activity_totals,
            "page_totals": [
                {"page": page, "seconds": seconds}
                for page, seconds in sorted(
                    page_totals.items(), key=lambda item: item[1], reverse=True
                )
            ],
            "recent_sessions": recent,
            "last_activity": last_activity,
        }
        dates = sorted(
            _parse_utc(value).astimezone().date()
            for session in project_sessions
            for value in (session["started_at_utc"], session["ended_at_utc"])
        )
        export_preview = {
            "project": project,
            "generated_at": today.strftime("%m/%d/%Y"),
            "date_range": (
                f"{dates[0]:%m/%d/%Y} - {dates[-1]:%m/%d/%Y}"
                if dates
                else "Live project time"
            ),
        }
        return current_project, export_preview

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

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/status")
    def status() -> dict[str, Any]:
        return api.refresh()

    @app.get("/dashboard")
    def dashboard() -> dict[str, Any]:
        return api.dashboard()

    @app.post("/refresh")
    def refresh() -> dict[str, Any]:
        return api.refresh()

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

    @app.post("/export.pdf")
    def export_pdf(request: PdfExportRequest) -> Response:
        filename = f"{_safe_filename(request.project_name)}-time-report.pdf"
        return Response(
            api.pdf(request),
            media_type="application/pdf",
            headers={"content-disposition": f'attachment; filename="{filename}"'},
        )

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


def _safe_filename(value: str) -> str:
    filename = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value
    ).strip("-")
    return filename or "resolve-project"


def _display_page(page: str, category: str) -> str:
    if category == "rendering" and page in {"", "Unknown", "none"}:
        return "Render/Export"
    return page or "Unknown"


def _seconds_on_local_date(started: datetime, ended: datetime, day: date) -> int:
    next_day = day + timedelta(days=1)
    start_of_day = datetime.fromtimestamp(time.mktime(day.timetuple()), timezone.utc)
    end_of_day = datetime.fromtimestamp(time.mktime(next_day.timetuple()), timezone.utc)
    overlap_start = max(started.astimezone(timezone.utc), start_of_day)
    overlap_end = min(ended.astimezone(timezone.utc), end_of_day)
    return max(0, int((overlap_end - overlap_start).total_seconds()))
