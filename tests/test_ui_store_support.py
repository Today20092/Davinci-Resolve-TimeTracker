import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.session_engine import SessionEngine
from resolve_time_tracker.activity_tracker import RuntimeSnapshot, RuntimeTracker
from resolve_time_tracker.ui import (
    _duration,
    companion_instance_lock,
    close_runtime_once,
    poll_runtime_once,
    prepare_companion_store,
)


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


class SequenceSnapshotProvider:
    def __init__(self, snapshots: list[RuntimeSnapshot]):
        self.snapshots = list(snapshots)

    def snapshot(self) -> RuntimeSnapshot:
        if not self.snapshots:
            raise RuntimeError("No dry-run snapshots remain")
        return self.snapshots.pop(0)


class UiStoreSupportTest(unittest.TestCase):
    def test_ui_module_imports_and_formats_duration(self):
        self.assertEqual("1:01:01", _duration(3661))

    def test_poll_runtime_once_updates_sessions_from_runtime_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = RuntimeTracker(
                    SessionEngine(store),
                    idle_timeout_seconds=300,
                    snapshot_provider=SequenceSnapshotProvider(
                        [RuntimeSnapshot("Project A", "edit", False, 0, True)]
                    ),
                )

                poll_runtime_once(store, tracker, utc(9))

                active = store.active_session_summary()

        self.assertEqual("Project A", active["project_name"])
        self.assertEqual("edit", active["page"])
        self.assertEqual("Project A", tracker.previous_snapshot.project_name)

    def test_companion_startup_recovers_previous_active_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.sqlite3"
            with SQLiteStore(path) as store:
                engine = SessionEngine(store)
                engine.project_changed(utc(9), "Project A")
                engine.heartbeat_tick(utc(9, 5))

            with SQLiteStore(path) as store:
                prepare_companion_store(store)
                rows = store.sessions()

        self.assertEqual(1, len(rows))
        self.assertEqual("2026-01-02T09:05:00Z", rows[0]["ended_at_utc"])

    def test_companion_close_closes_active_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = RuntimeTracker(
                    SessionEngine(store),
                    idle_timeout_seconds=300,
                    snapshot_provider=SequenceSnapshotProvider(
                        [RuntimeSnapshot("Project A", "edit", False, 0, True)]
                    ),
                )
                poll_runtime_once(store, tracker, utc(9))

                close_runtime_once(tracker, utc(10))

                rows = store.sessions()

        self.assertEqual(1, len(rows))
        self.assertEqual("2026-01-02T10:00:00Z", rows[0]["ended_at_utc"])

    def test_companion_instance_lock_blocks_second_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.sqlite3"

            with companion_instance_lock(path):
                with self.assertRaises(RuntimeError):
                    with companion_instance_lock(path):
                        pass

            with companion_instance_lock(path):
                pass

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
