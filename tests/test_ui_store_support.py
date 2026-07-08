import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.session_engine import SessionEngine
from resolve_time_tracker.ui import _duration


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


class UiStoreSupportTest(unittest.TestCase):
    def test_ui_module_imports_and_formats_duration(self):
        self.assertEqual("1:01:01", _duration(3661))

    def test_project_summaries_and_idle_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = SessionEngine(store)
                engine.project_changed(utc(9), "Project A")
                engine.resolve_closed(utc(10, 30))
                store.set_idle_timeout_seconds(600)

                summaries = store.project_summaries()

                self.assertEqual(600, store.idle_timeout_seconds())

        self.assertEqual("Project A", summaries[0]["project_name"])
        self.assertEqual(1, summaries[0]["session_count"])
        self.assertEqual(5400, summaries[0]["duration_seconds"])
        self.assertEqual("2026-01-02", summaries[0]["last_session_date"])

    def test_closed_session_can_be_edited_with_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = SessionEngine(store)
                engine.project_changed(utc(9), "Project A")
                engine.resolve_closed(utc(10))
                session_id = store.sessions()[0]["id"]

                store.update_session(
                    session_id,
                    started_at=utc(9, 15),
                    ended_at=utc(10, 15),
                    page="color",
                    activity_category="rendering",
                )

                row = store.sessions()[0]
                self.assertEqual("2026-01-02T09:15:00Z", row["started_at_utc"])
                self.assertEqual("2026-01-02T10:15:00Z", row["ended_at_utc"])
                self.assertEqual("color", row["page"])
                self.assertEqual("rendering", row["activity_category"])

                with self.assertRaises(ValueError):
                    store.update_session(
                        session_id,
                        started_at=utc(11),
                        ended_at=utc(10),
                        page="edit",
                        activity_category="editing",
                    )
