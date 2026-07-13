"""Shared Resolve Project reporting projection."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class ProjectReport:
    sessions: list[dict[str, Any]]
    tracked_seconds: int
    today_seconds: int
    session_count: int
    activity_totals: dict[str, int]
    page_totals: list[tuple[str, int]]
    date_range: str

    @property
    def recent_sessions(self) -> list[dict[str, Any]]:
        return sorted(
            self.sessions,
            key=lambda session: session["started_at_utc"],
            reverse=True,
        )


def project_report(
    project_name: str,
    sessions: list[dict[str, Any]],
    *,
    active_session: dict[str, Any] | None = None,
    active_seconds: int = 0,
    now: datetime | None = None,
) -> ProjectReport:
    generated = now or datetime.now(timezone.utc)
    project_sessions = [
        session for session in sessions if session["project_name"] == project_name
    ]
    activity_totals = {"editing": 0, "playback": 0, "rendering": 0}
    page_totals: dict[str, int] = {}
    today = generated.astimezone().date()
    today_seconds = 0

    for session in project_sessions:
        seconds = int(session["duration_seconds"])
        activity_totals[session["activity_category"]] += seconds
        page = display_page(session["page"], session["activity_category"])
        page_totals[page] = page_totals.get(page, 0) + seconds
        today_seconds += seconds_on_local_date(
            parse_utc(session["started_at_utc"]),
            parse_utc(session["ended_at_utc"]),
            today,
        )

    active = (
        active_session
        if active_session is not None and active_session["project_name"] == project_name
        else None
    )
    if active is not None:
        category = active["activity_category"]
        activity_totals[category] += active_seconds
        page = display_page(active["page"], category)
        page_totals[page] = page_totals.get(page, 0) + active_seconds
        today_seconds += seconds_on_local_date(
            parse_utc(active["started_at_utc"]), generated, today
        )

    dates = [
        parse_utc(value).astimezone().date()
        for session in project_sessions
        for value in (session["started_at_utc"], session["ended_at_utc"])
    ]
    if active is not None:
        dates.extend([parse_utc(active["started_at_utc"]).astimezone().date(), today])
    dates.sort()
    return ProjectReport(
        sessions=project_sessions,
        tracked_seconds=sum(activity_totals.values()),
        today_seconds=today_seconds,
        session_count=len(project_sessions) + (1 if active is not None else 0),
        activity_totals=activity_totals,
        page_totals=sorted(page_totals.items(), key=lambda item: item[1], reverse=True),
        date_range=(
            f"{dates[0]:%m/%d/%Y} - {dates[-1]:%m/%d/%Y}"
            if dates
            else "Live project time"
        ),
    )


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def display_page(page: str, category: str) -> str:
    if category == "rendering" and page in {"", "Unknown", "none"}:
        return "Render/Export"
    return page or "Unknown"


def seconds_on_local_date(started: datetime, ended: datetime, day: date) -> int:
    next_day = day + timedelta(days=1)
    start_of_day = datetime.fromtimestamp(time.mktime(day.timetuple()), timezone.utc)
    end_of_day = datetime.fromtimestamp(time.mktime(next_day.timetuple()), timezone.utc)
    overlap_start = max(started.astimezone(timezone.utc), start_of_day)
    overlap_end = min(ended.astimezone(timezone.utc), end_of_day)
    return max(0, int((overlap_end - overlap_start).total_seconds()))
