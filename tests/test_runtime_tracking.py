import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from resolve_time_tracker.activity_tracker import (
    RuntimeSnapshot,
    RuntimeTracker,
    SequenceSnapshotProvider,
)
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.resolve_bridge import ResolveBridge
from resolve_time_tracker.session_engine import SessionEngine


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


class RuntimeTrackingTest(unittest.TestCase):
    def test_fake_snapshots_drive_engine_events_and_heartbeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = SessionEngine(store)
                tracker = RuntimeTracker(
                    engine,
                    idle_timeout_seconds=300,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", False, 301, True),
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", True, 600, False),
                            RuntimeSnapshot("Project A", "edit", False, 600, False),
                        ]
                    ),
                )

                for observed_at in [utc(9), utc(9, 10), utc(9, 20), utc(9, 30), utc(9, 40)]:
                    tracker.poll(observed_at)

                rows = store.sessions()
                active = store.active_session()

        self.assertEqual(
            [
                ("editing", "2026-01-02T09:00:00Z", "2026-01-02T09:10:00Z"),
                ("editing", "2026-01-02T09:20:00Z", "2026-01-02T09:30:00Z"),
                ("rendering", "2026-01-02T09:30:00Z", "2026-01-02T09:40:00Z"),
            ],
            [
                (row["activity_category"], row["started_at_utc"], row["ended_at_utc"])
                for row in rows
            ],
        )
        self.assertIsNone(active)

    def test_active_poll_updates_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = RuntimeTracker(
                    SessionEngine(store),
                    idle_timeout_seconds=300,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "cut", False, 0, True),
                            RuntimeSnapshot("Project A", "cut", False, 5, True),
                        ]
                    ),
                )

                tracker.poll(utc(10))
                tracker.poll(utc(10, 1))

                active = store.active_session()

        self.assertEqual("2026-01-02T10:01:00Z", active["last_heartbeat_at_utc"])

    def test_resolve_bridge_snapshot_reads_safe_runtime_fields(self):
        bridge = ResolveBridge(activity_probe=FakeActivity())
        bridge._module = FakeResolveModule()

        snapshot = bridge.snapshot()

        self.assertEqual("Project A", snapshot.project_name)
        self.assertEqual("edit", snapshot.page)
        self.assertTrue(snapshot.is_rendering)
        self.assertEqual(12.5, snapshot.idle_seconds)
        self.assertTrue(snapshot.resolve_is_foreground)
        self.assertEqual("Timeline 1", snapshot.timeline_name)
        self.assertEqual("timeline-id", snapshot.timeline_id)
        self.assertEqual("01:00:00:00", snapshot.timecode)


class FakeActivity:
    def idle_seconds(self) -> float:
        return 12.5

    def resolve_is_foreground(self) -> bool:
        return True


class FakeResolveModule:
    def scriptapp(self, name: str):
        return FakeResolve() if name == "Resolve" else None


class FakeResolve:
    def GetCurrentPage(self) -> str:
        return "edit"

    def GetProjectManager(self):
        return FakeProjectManager()


class FakeProjectManager:
    def GetCurrentProject(self):
        return FakeProject()


class FakeProject:
    def GetName(self) -> str:
        return "Project A"

    def IsRenderingInProgress(self) -> bool:
        return True

    def GetCurrentTimeline(self):
        return FakeTimeline()


class FakeTimeline:
    def GetName(self) -> str:
        return "Timeline 1"

    def GetUniqueId(self) -> str:
        return "timeline-id"

    def GetCurrentTimecode(self) -> str:
        return "01:00:00:00"
