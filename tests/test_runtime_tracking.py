import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from resolve_time_tracker.activity_tracker import (
    LinuxActivityProbe,
    MacActivityProbe,
    RuntimeSnapshot,
    RuntimeTracker,
)
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.resolve_bridge import ResolveBridge, default_scripting_root
from resolve_time_tracker.session_engine import SessionEngine


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


class SequenceSnapshotProvider:
    def __init__(self, snapshots: list[RuntimeSnapshot]):
        self.snapshots = list(snapshots)

    def snapshot(self) -> RuntimeSnapshot:
        if not self.snapshots:
            raise RuntimeError("No dry-run snapshots remain")
        return self.snapshots.pop(0)


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

    def test_lowered_idle_timeout_closes_active_session_on_next_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = RuntimeTracker(
                    SessionEngine(store),
                    idle_timeout_seconds=300,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 100, True),
                            RuntimeSnapshot("Project A", "edit", False, 110, True),
                        ]
                    ),
                )

                tracker.poll(utc(11))
                tracker.idle_timeout_seconds = 60
                tracker.poll(utc(11, 1))

                rows = store.sessions()
                active = store.active_session()

        self.assertEqual("2026-01-02T11:01:00Z", rows[0]["ended_at_utc"])
        self.assertIsNone(active)

    def test_raised_idle_timeout_resumes_tracking_on_next_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = RuntimeTracker(
                    SessionEngine(store),
                    idle_timeout_seconds=60,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 100, True),
                            RuntimeSnapshot("Project A", "edit", False, 110, True),
                        ]
                    ),
                )

                tracker.poll(utc(12))
                tracker.idle_timeout_seconds = 300
                tracker.poll(utc(12, 1))

                active = store.active_session()

        self.assertEqual("2026-01-02T12:01:00Z", active["started_at_utc"])

    def test_manual_pause_closes_and_resume_reopens_on_next_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = RuntimeTracker(
                    SessionEngine(store),
                    idle_timeout_seconds=300,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                        ]
                    ),
                )

                tracker.poll(utc(13))
                tracker.pause(utc(13, 10))
                paused_snapshot = tracker.poll(utc(13, 20))
                tracker.resume()
                tracker.poll(utc(13, 30))

                rows = store.sessions()
                active = store.active_session()

        self.assertEqual("Project A", paused_snapshot.project_name)
        self.assertEqual("2026-01-02T13:10:00Z", rows[0]["ended_at_utc"])
        self.assertEqual("2026-01-02T13:30:00Z", active["started_at_utc"])

    def test_mac_activity_probe_parses_idle_and_foreground(self):
        def run_text(command: list[str]) -> str:
            if command[0] == "ioreg":
                return '    "HIDIdleTime" = 2500000000\n'
            return "DaVinci Resolve\n"

        probe = MacActivityProbe(run_text=run_text)

        self.assertEqual(2.5, probe.idle_seconds())
        self.assertTrue(probe.resolve_is_foreground())

    def test_linux_activity_probe_parses_idle_and_foreground(self):
        def run_text(command: list[str]) -> str:
            if command[0] == "xprintidle":
                return "2500\n"
            return "DaVinci Resolve Studio\n"

        probe = LinuxActivityProbe(run_text=run_text)

        self.assertEqual(2.5, probe.idle_seconds())
        self.assertTrue(probe.resolve_is_foreground())

    def test_resolve_bridge_scripting_root_is_platform_aware(self):
        with patch("platform.system", return_value="Darwin"), patch.dict(
            "os.environ", {}, clear=True
        ):
            self.assertEqual(
                "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
                str(default_scripting_root()).replace("\\", "/"),
            )
        with patch("platform.system", return_value="Linux"), patch.dict(
            "os.environ", {}, clear=True
        ):
            self.assertEqual(
                "/opt/resolve/Developer/Scripting",
                str(default_scripting_root()).replace("\\", "/"),
            )

    def test_resolve_bridge_scripting_root_honors_env_override(self):
        with patch.dict("os.environ", {"RESOLVE_SCRIPT_API": "/tmp/resolve-api"}):
            self.assertEqual("/tmp/resolve-api", str(default_scripting_root()).replace("\\", "/"))

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
