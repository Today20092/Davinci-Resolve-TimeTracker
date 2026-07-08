import csv
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.session_engine import SessionEngine


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


class CoreTrackingTest(unittest.TestCase):
    def test_events_create_only_billable_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = SessionEngine(store)

                engine.project_changed(utc(9), "Project A")
                engine.page_changed(utc(9, 5), "edit")
                engine.idle_started(utc(9, 30))
                engine.idle_ended(utc(9, 45))
                engine.resolve_focus_lost(utc(10))
                engine.resolve_focus_gained(utc(10, 15))
                engine.rendering_started(utc(10, 30))
                engine.resolve_focus_lost(utc(10, 40))
                engine.rendering_finished(utc(11))
                engine.resolve_focus_gained(utc(11, 15))
                engine.project_changed(utc(11, 30), "Project B")
                engine.resolve_closed(utc(12))

                rows = store.sessions()

        self.assertEqual(
            [
                ("Project A", "Unknown", "editing", 9 * 3600, 9 * 3600 + 5 * 60),
                ("Project A", "edit", "editing", 9 * 3600 + 5 * 60, 9 * 3600 + 30 * 60),
                ("Project A", "edit", "editing", 9 * 3600 + 45 * 60, 10 * 3600),
                ("Project A", "edit", "editing", 10 * 3600 + 15 * 60, 10 * 3600 + 30 * 60),
                ("Project A", "edit", "rendering", 10 * 3600 + 30 * 60, 11 * 3600),
                ("Project A", "edit", "editing", 11 * 3600 + 15 * 60, 11 * 3600 + 30 * 60),
                ("Project B", "edit", "editing", 11 * 3600 + 30 * 60, 12 * 3600),
            ],
            [
                (
                    row["project_name"],
                    row["page"],
                    row["activity_category"],
                    _seconds(row["started_at_utc"]),
                    _seconds(row["ended_at_utc"]),
                )
                for row in rows
            ],
        )

    def test_recovery_closes_active_session_at_last_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.sqlite3"
            with SQLiteStore(path) as store:
                engine = SessionEngine(store)

                engine.project_changed(utc(13), "Project A")
                engine.heartbeat_tick(utc(13, 10))

            with SQLiteStore(path) as recovered:
                recovered.recover_active_session()

                rows = recovered.sessions()

        self.assertEqual(1, len(rows))
        self.assertEqual(13 * 3600, _seconds(rows[0]["started_at_utc"]))
        self.assertEqual(13 * 3600 + 10 * 60, _seconds(rows[0]["ended_at_utc"]))

    def test_csv_export_contains_closed_sessions_with_durations(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = SessionEngine(store)
                engine.project_changed(utc(14), "Project A")
                engine.resolve_closed(utc(15, 30))

                output = io.StringIO()
                store.write_csv(output)

        rows = list(csv.DictReader(io.StringIO(output.getvalue())))
        self.assertEqual(1, len(rows))
        self.assertEqual("Project A", rows[0]["project_name"])
        self.assertEqual("5400", rows[0]["duration_seconds"])
        self.assertEqual("1.5000", rows[0]["duration_hours"])
        self.assertEqual("editing", rows[0]["activity_category"])


def _seconds(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.hour * 3600 + parsed.minute * 60 + parsed.second
