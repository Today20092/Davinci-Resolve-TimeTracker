import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from resolve_time_tracker.activity_tracker import (
    LinuxActivityProbe,
    MacActivityProbe,
)
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.resolve_bridge import ResolveBridge, default_scripting_root
from resolve_time_tracker.tracking_engine import RuntimeSnapshot, TrackingEngine
from resolve_time_tracker.tracking_runtime import TrackingRuntime


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
    def test_runtime_waits_after_each_observation_before_the_next_one(self):
        class SlowProvider:
            def __init__(self):
                self.starts: list[float] = []
                self.observed_twice = threading.Event()

            def snapshot(self) -> RuntimeSnapshot:
                self.starts.append(time.monotonic())
                time.sleep(0.03)
                if len(self.starts) == 2:
                    self.observed_twice.set()
                return RuntimeSnapshot("Project A", "cut", False, 0, True)

        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                provider = SlowProvider()
                runtime = TrackingRuntime(
                    TrackingEngine(store, snapshot_provider=provider),
                    observation_interval_seconds=0.01,
                )
                runtime.start()
                self.assertTrue(provider.observed_twice.wait(1))
                runtime.stop()

        self.assertGreaterEqual(provider.starts[1] - provider.starts[0], 0.04)

    def test_runtime_publishes_one_observation_and_rate_limits_heartbeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                provider = SequenceSnapshotProvider(
                    [
                        RuntimeSnapshot("Project A", "cut", False, 0, True)
                        for _ in range(12)
                    ]
                )
                runtime = TrackingRuntime(
                    TrackingEngine(store, snapshot_provider=provider)
                )

                with patch.object(
                    store, "update_heartbeat", wraps=store.update_heartbeat
                ) as heartbeat:
                    for seconds in range(0, 60, 5):
                        runtime.observe(utc(10) + timedelta(seconds=seconds))
                    self.assertEqual(6, heartbeat.call_count)

                active = store.active_session()

        self.assertEqual(12, runtime.observation_count)
        assert runtime.snapshot is not None
        assert active is not None
        self.assertEqual("Project A", runtime.snapshot.project_name)
        self.assertIsNone(runtime.last_error)
        self.assertEqual("2026-01-02T10:00:50Z", active["last_heartbeat_at_utc"])

    def test_failed_observation_keeps_published_state_and_session_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                runtime = TrackingRuntime(
                    TrackingEngine(
                        store,
                        snapshot_provider=SequenceSnapshotProvider(
                            [RuntimeSnapshot("Project A", "cut", False, 0, True)]
                        ),
                    )
                )

                runtime.observe(utc(10))
                succeeded = runtime.observe(utc(10, 5))
                active = store.active_session()

        self.assertFalse(succeeded)
        self.assertEqual("Project A", runtime.snapshot.project_name)
        self.assertIn("No dry-run snapshots remain", runtime.last_error)
        self.assertIsNotNone(active)

    def test_fake_snapshots_drive_engine_events_and_heartbeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = TrackingEngine(
                    store,
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

                for observed_at in [
                    utc(9),
                    utc(9, 10),
                    utc(9, 20),
                    utc(9, 30),
                    utc(9, 40),
                ]:
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
                tracker = TrackingEngine(
                    store,
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
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 100, True),
                            RuntimeSnapshot("Project A", "edit", False, 110, True),
                        ]
                    ),
                )

                tracker.poll(utc(11))
                store.set_idle_timeout_seconds(60)
                tracker.poll(utc(11, 1))

                rows = store.sessions()
                active = store.active_session()

        self.assertEqual("2026-01-02T11:01:00Z", rows[0]["ended_at_utc"])
        self.assertIsNone(active)

    def test_raised_idle_timeout_resumes_tracking_on_next_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                store.set_idle_timeout_seconds(60)
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 100, True),
                            RuntimeSnapshot("Project A", "edit", False, 110, True),
                        ]
                    ),
                )

                tracker.poll(utc(12))
                store.set_idle_timeout_seconds(300)
                tracker.poll(utc(12, 1))

                active = store.active_session()

        self.assertEqual("2026-01-02T12:01:00Z", active["started_at_utc"])

    def test_manual_pause_closes_and_resume_reopens_on_next_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = TrackingEngine(
                    store,
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

    def test_close_ends_the_active_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [RuntimeSnapshot("Project A", "edit", False, 0, True)]
                    ),
                )

                tracker.poll(utc(14))
                tracker.close(utc(14, 30))

                rows = store.sessions()

        self.assertEqual("2026-01-02T14:30:00Z", rows[0]["ended_at_utc"])

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
        with (
            patch("platform.system", return_value="Darwin"),
            patch.dict("os.environ", {}, clear=True),
        ):
            self.assertEqual(
                "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
                str(default_scripting_root()).replace("\\", "/"),
            )
        with (
            patch("platform.system", return_value="Linux"),
            patch.dict("os.environ", {}, clear=True),
        ):
            self.assertEqual(
                "/opt/resolve/Developer/Scripting",
                str(default_scripting_root()).replace("\\", "/"),
            )

    def test_resolve_bridge_scripting_root_honors_env_override(self):
        with patch.dict("os.environ", {"RESOLVE_SCRIPT_API": "/tmp/resolve-api"}):
            self.assertEqual(
                "/tmp/resolve-api", str(default_scripting_root()).replace("\\", "/")
            )

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

    def test_resolve_observations_reuse_the_session_connection(self):
        bridge = ResolveBridge(activity_probe=FakeActivity())
        sdk = Mock(
            scriptapp=Mock(side_effect=[FakeResolve(), RuntimeError("reconnected")])
        )
        bridge._module = sdk

        first = bridge.snapshot()
        second = bridge.snapshot()

        self.assertEqual("Project A", first.project_name)
        self.assertEqual("Project A", second.project_name)
        sdk.scriptapp.assert_called_once_with("Resolve")

    def test_failed_required_sdk_read_reconnects_on_next_observation(self):
        for failure in ("manager", "project", "name", "rendering"):
            with self.subTest(failure=failure):
                project = Mock(
                    GetName=Mock(return_value="Project A"),
                    IsRenderingInProgress=Mock(return_value=False),
                    GetCurrentTimeline=Mock(return_value=None),
                )
                manager = Mock(GetCurrentProject=Mock(return_value=project))
                disconnected = Mock(
                    GetProjectManager=Mock(return_value=manager),
                    GetCurrentPage=Mock(return_value="edit"),
                )
                required_read = {
                    "manager": disconnected.GetProjectManager,
                    "project": manager.GetCurrentProject,
                    "name": project.GetName,
                    "rendering": project.IsRenderingInProgress,
                }[failure]
                required_read.side_effect = RuntimeError("SDK connection lost")
                sdk = Mock(scriptapp=Mock(side_effect=[disconnected, FakeResolve()]))
                bridge = ResolveBridge(activity_probe=FakeActivity())
                bridge._module = sdk

                with self.assertRaisesRegex(RuntimeError, "SDK connection lost"):
                    bridge.snapshot()
                recovered = bridge.snapshot()

                self.assertEqual("Project A", recovered.project_name)
                self.assertEqual(2, sdk.scriptapp.call_count)

    def test_injected_host_resolve_object_survives_temporary_sdk_failure(self):
        resolve = Mock(
            GetProjectManager=Mock(
                side_effect=[
                    RuntimeError("Host temporarily unavailable"),
                    FakeProjectManager(),
                ]
            ),
            GetCurrentPage=Mock(return_value="edit"),
        )
        bridge = ResolveBridge(activity_probe=FakeActivity(), resolve_object=resolve)
        sdk = Mock(scriptapp=Mock(side_effect=AssertionError("Must use host object")))
        bridge._module = sdk

        with self.assertRaisesRegex(RuntimeError, "Host temporarily unavailable"):
            bridge.snapshot()
        recovered = bridge.snapshot()

        self.assertEqual("Project A", recovered.project_name)
        sdk.scriptapp.assert_not_called()


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
