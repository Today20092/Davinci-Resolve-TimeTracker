"""SQLite persistence for Resolve Time Tracker."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def upsert_project(self, resolve_name: str) -> int:
        with self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO projects(resolve_name) VALUES (?)",
                (resolve_name,),
            )
            row = self._connection.execute(
                "SELECT id FROM projects WHERE resolve_name = ?",
                (resolve_name,),
            ).fetchone()
        return int(row["id"])

    def open_active_session(
        self,
        *,
        project_id: int,
        started_at: datetime,
        page: str,
        activity_category: str,
    ) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM active_session WHERE id = 1")
            self._connection.execute(
                """
                INSERT INTO active_session(
                  id, project_id, started_at_utc, last_heartbeat_at_utc, page, activity_category
                )
                VALUES (1, ?, ?, NULL, ?, ?)
                """,
                (project_id, _format_utc(started_at), page, activity_category),
            )

    def close_active_session(self, ended_at: datetime) -> None:
        active = self.active_session()
        if active is None:
            return

        ended = _format_utc(ended_at)
        started = active["started_at_utc"]
        if ended < started:
            ended = started

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO sessions(project_id, started_at_utc, ended_at_utc, page, activity_category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    active["project_id"],
                    started,
                    ended,
                    active["page"],
                    active["activity_category"],
                ),
            )
            self._connection.execute("DELETE FROM active_session WHERE id = 1")

    def update_heartbeat(self, observed_at: datetime) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE active_session SET last_heartbeat_at_utc = ? WHERE id = 1",
                (_format_utc(observed_at),),
            )

    def recover_active_session(self) -> None:
        active = self.active_session()
        if active is None:
            return
        ended = active["last_heartbeat_at_utc"] or active["started_at_utc"]
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO sessions(project_id, started_at_utc, ended_at_utc, page, activity_category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    active["project_id"],
                    active["started_at_utc"],
                    ended,
                    active["page"],
                    active["activity_category"],
                ),
            )
            self._connection.execute("DELETE FROM active_session WHERE id = 1")

    def active_session(self) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM active_session WHERE id = 1",
        ).fetchone()

    def sessions(self) -> list[sqlite3.Row]:
        return list(
            self._connection.execute(
                """
                SELECT
                  sessions.id,
                  projects.resolve_name AS project_name,
                  sessions.started_at_utc,
                  sessions.ended_at_utc,
                  sessions.page,
                  sessions.activity_category
                FROM sessions
                JOIN projects ON projects.id = sessions.project_id
                ORDER BY sessions.started_at_utc, sessions.id
                """
            )
        )

    def project_summaries(self) -> list[sqlite3.Row]:
        return list(
            self._connection.execute(
                """
                SELECT
                  projects.resolve_name AS project_name,
                  COUNT(sessions.id) AS session_count,
                  COALESCE(SUM(
                    strftime('%s', sessions.ended_at_utc) -
                    strftime('%s', sessions.started_at_utc)
                  ), 0) AS duration_seconds,
                  MAX(substr(sessions.started_at_utc, 1, 10)) AS last_session_date
                FROM projects
                LEFT JOIN sessions ON sessions.project_id = projects.id
                GROUP BY projects.id, projects.resolve_name
                ORDER BY projects.resolve_name
                """
            )
        )

    def active_session_summary(self) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT
              active_session.id,
              projects.resolve_name AS project_name,
              active_session.started_at_utc,
              active_session.last_heartbeat_at_utc,
              active_session.page,
              active_session.activity_category
            FROM active_session
            JOIN projects ON projects.id = active_session.project_id
            WHERE active_session.id = 1
            """
        ).fetchone()

    def update_session(
        self,
        session_id: int,
        *,
        started_at: datetime,
        ended_at: datetime,
        page: str,
        activity_category: str,
    ) -> None:
        if activity_category not in {"editing", "playback", "rendering"}:
            raise ValueError("activity_category must be editing, playback, or rendering")
        started = _format_utc(started_at)
        ended = _format_utc(ended_at)
        if ended < started:
            raise ValueError("ended_at must be greater than or equal to started_at")
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE sessions
                SET started_at_utc = ?, ended_at_utc = ?, page = ?, activity_category = ?
                WHERE id = ?
                """,
                (started, ended, page or "Unknown", activity_category, session_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Session {session_id} does not exist")

    def idle_timeout_seconds(self) -> int:
        row = self._connection.execute(
            "SELECT idle_timeout_seconds FROM settings WHERE id = 1",
        ).fetchone()
        return int(row["idle_timeout_seconds"])

    def set_idle_timeout_seconds(self, seconds: int) -> None:
        if seconds <= 0:
            raise ValueError("idle timeout must be positive")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO settings(id, idle_timeout_seconds)
                VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET idle_timeout_seconds = excluded.idle_timeout_seconds
                """,
                (seconds,),
            )

    def write_csv(self, output: TextIO) -> None:
        import csv

        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            [
                "session_id",
                "project_name",
                "date",
                "started_at_utc",
                "ended_at_utc",
                "duration_seconds",
                "duration_hours",
                "page",
                "activity_category",
            ]
        )
        for row in self.sessions():
            started = _parse_utc(row["started_at_utc"])
            ended = _parse_utc(row["ended_at_utc"])
            duration = max(0, int((ended - started).total_seconds()))
            writer.writerow(
                [
                    row["id"],
                    row["project_name"],
                    started.date().isoformat(),
                    row["started_at_utc"],
                    row["ended_at_utc"],
                    str(duration),
                    f"{duration / 3600:.4f}",
                    row["page"],
                    row["activity_category"],
                ]
            )

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                  id INTEGER PRIMARY KEY,
                  resolve_name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS sessions (
                  id INTEGER PRIMARY KEY,
                  project_id INTEGER NOT NULL REFERENCES projects(id),
                  started_at_utc TEXT NOT NULL,
                  ended_at_utc TEXT NOT NULL,
                  page TEXT NOT NULL,
                  activity_category TEXT NOT NULL CHECK (
                    activity_category IN ('editing', 'playback', 'rendering')
                  )
                );

                CREATE TABLE IF NOT EXISTS active_session (
                  id INTEGER PRIMARY KEY CHECK (id = 1),
                  project_id INTEGER NOT NULL REFERENCES projects(id),
                  started_at_utc TEXT NOT NULL,
                  last_heartbeat_at_utc TEXT,
                  page TEXT NOT NULL,
                  activity_category TEXT NOT NULL CHECK (
                    activity_category IN ('editing', 'playback', 'rendering')
                  )
                );

                CREATE TABLE IF NOT EXISTS settings (
                  id INTEGER PRIMARY KEY CHECK (id = 1),
                  idle_timeout_seconds INTEGER NOT NULL CHECK (idle_timeout_seconds > 0)
                );

                INSERT OR IGNORE INTO settings(id, idle_timeout_seconds) VALUES (1, 300);
                """
            )


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
