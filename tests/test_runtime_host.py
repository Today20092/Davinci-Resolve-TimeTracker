import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import PropertyMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from resolve_time_tracker.api import ApiState
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.runtime_host import RuntimeHost, runtime_request
from resolve_time_tracker.tracked_launch import LaunchError
from resolve_time_tracker.tracking_engine import RuntimeSnapshot, TrackingEngine
from resolve_time_tracker.tracking_runtime import TrackingRuntime


class Provider:
    def __init__(self):
        self.closed = False

    def snapshot(self):
        return RuntimeSnapshot("Project", "edit", False, 0, True)

    def close(self):
        self.closed = True


class RuntimeHostTest(unittest.TestCase):
    def test_new_session_freshness_uses_its_own_start_until_first_heartbeat(self):
        for second, expected_status, elapsed, ended in (
            (26, "active", 11, "2026-01-01T00:00:26Z"),
            (31, "stale", 0, "2026-01-01T00:00:15Z"),
        ):
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            clock = [0.0]

            class PageChange(Provider):
                def snapshot(self):
                    return RuntimeSnapshot(
                        "Project", "edit" if clock[0] < 15 else "color", False, 0, True
                    )

            with (
                self.subTest(second=second),
                tempfile.TemporaryDirectory() as tmp,
                SQLiteStore(Path(tmp) / "db") as store,
                patch("time.monotonic", side_effect=lambda: clock[0]),
            ):
                engine = TrackingEngine(store, snapshot_provider=PageChange())
                runtime = TrackingRuntime(
                    engine, now=lambda: now + timedelta(seconds=clock[0])
                )
                api = ApiState(
                    store,
                    tracking_engine=engine,
                    tracking_runtime=runtime,
                    now=lambda: now + timedelta(seconds=clock[0]),
                )
                for observed in (0, 10, 15):
                    clock[0] = observed
                    runtime.observe()
                clock[0] = second
                self.assertEqual(expected_status, api.status()["tracking_status"])
                self.assertEqual(elapsed, api.status()["active_elapsed_seconds"])
                api.pause()
                color = next(s for s in api.sessions() if s["page"] == "color")
                self.assertEqual(ended, color["ended_at_utc"])

    def test_fresh_observation_after_failure_does_not_backfill_a_stale_gap(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = [0.0]

        class Recovering(Provider):
            def snapshot(self):
                if clock[0] == 15:
                    raise RuntimeError("SDK unavailable")
                if clock[0] == 40:
                    return RuntimeSnapshot("Other project", "color", False, 0, True)
                return super().snapshot()

        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
            patch("time.monotonic", side_effect=lambda: clock[0]),
        ):
            engine = TrackingEngine(store, snapshot_provider=Recovering())
            runtime = TrackingRuntime(
                engine, now=lambda: now + timedelta(seconds=clock[0])
            )
            api = ApiState(store, tracking_engine=engine, tracking_runtime=runtime)
            runtime.observe()
            clock[0] = 10
            runtime.observe()
            clock[0] = 15
            self.assertFalse(runtime.observe())
            clock[0] = 40
            self.assertTrue(runtime.observe())
            self.assertEqual("2026-01-01T00:00:10Z", api.sessions()[0]["ended_at_utc"])

    def test_pause_and_resume_discard_an_already_started_resolve_observation(self):
        reads = [0]

        class PausedDuringRead(Provider):
            def snapshot(self):
                reads[0] += 1
                if reads[0] == 2:
                    api.pause()
                    api.resume()
                    return RuntimeSnapshot("Old read", "color", False, 0, True)
                return super().snapshot()

        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
        ):
            engine = TrackingEngine(store, snapshot_provider=PausedDuringRead())
            runtime = TrackingRuntime(engine)
            api = ApiState(store, tracking_engine=engine, tracking_runtime=runtime)
            runtime.observe()
            self.assertTrue(runtime.observe())
            self.assertEqual("idle", api.status()["tracking_status"])
            self.assertEqual("Project", api.status()["project"])
            self.assertEqual(1, runtime.observation_count)
            self.assertTrue(runtime.observe())
            self.assertEqual("active", api.status()["tracking_status"])

    def test_pause_after_observations_go_stale_recovers_at_the_last_heartbeat(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = [0.0]
        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
            patch("time.monotonic", side_effect=lambda: clock[0]),
        ):
            engine = TrackingEngine(store, snapshot_provider=Provider())
            runtime = TrackingRuntime(
                engine, now=lambda: now + timedelta(seconds=clock[0])
            )
            api = ApiState(
                store,
                tracking_engine=engine,
                tracking_runtime=runtime,
                now=lambda: now + timedelta(seconds=clock[0]),
            )
            runtime.observe()
            clock[0] = 5
            runtime.observe()
            clock[0] = 20
            self.assertEqual("paused", api.pause()["tracking_status"])
            self.assertEqual("2026-01-01T00:00:00Z", api.sessions()[0]["ended_at_utc"])

    def test_late_resolve_observation_does_not_bill_the_unobserved_interval(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = [0.0]

        class Slow(Provider):
            def snapshot(self):
                if clock[0] == 15:
                    clock[0] = 60
                    return RuntimeSnapshot("Other project", "color", False, 0, True)
                return super().snapshot()

        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
            patch("time.monotonic", side_effect=lambda: clock[0]),
        ):
            engine = TrackingEngine(store, snapshot_provider=Slow())
            runtime = TrackingRuntime(
                engine, now=lambda: now + timedelta(seconds=clock[0])
            )
            api = ApiState(store, tracking_engine=engine, tracking_runtime=runtime)
            self.assertTrue(runtime.observe())
            clock[0] = 10
            self.assertTrue(runtime.observe())
            clock[0] = 15
            self.assertFalse(runtime.observe())
            self.assertEqual("error", api.status()["tracking_status"])
            session = api.sessions()[0]
            self.assertEqual("Project", session["project_name"])
            self.assertEqual("2026-01-01T00:00:10Z", session["ended_at_utc"])

    def test_slow_failed_resolve_observation_recovers_at_the_last_heartbeat(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = [0.0]

        class SlowFailure(Provider):
            def snapshot(self):
                if clock[0] == 15:
                    clock[0] = 60
                    raise RuntimeError("SDK read failed after waiting")
                return super().snapshot()

        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
            patch("time.monotonic", side_effect=lambda: clock[0]),
        ):
            engine = TrackingEngine(store, snapshot_provider=SlowFailure())
            runtime = TrackingRuntime(
                engine, now=lambda: now + timedelta(seconds=clock[0])
            )
            api = ApiState(store, tracking_engine=engine, tracking_runtime=runtime)
            runtime.observe()
            clock[0] = 10
            runtime.observe()
            clock[0] = 15
            self.assertFalse(runtime.observe())
            self.assertEqual("2026-01-01T00:00:10Z", api.sessions()[0]["ended_at_utc"])

    def test_resume_race_never_reads_resolve_inside_the_database_lock(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
        ):
            engine = TrackingEngine(store, snapshot_provider=Provider())
            runtime = TrackingRuntime(engine)
            with (
                patch.object(
                    TrackingEngine,
                    "tracking_enabled",
                    new_callable=PropertyMock,
                    side_effect=[False, True],
                ),
                patch.object(engine, "read_snapshot") as read,
            ):
                self.assertTrue(runtime.observe())
            read.assert_not_called()
            self.assertEqual(0, runtime.observation_count)

    def test_heartbeat_limit_survives_page_changes_and_many_readers(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
        ):
            engine = TrackingEngine(store, snapshot_provider=Provider())
            runtime = TrackingRuntime(engine)
            api = ApiState(store, tracking_engine=engine, tracking_runtime=runtime)
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            with patch.object(
                store, "update_heartbeat", wraps=store.update_heartbeat
            ) as heartbeat:
                for second in range(0, 60, 5):
                    with patch.object(
                        engine,
                        "read_snapshot",
                        return_value=RuntimeSnapshot("A", str(second), False, 0, True),
                    ):
                        runtime.observe(now + timedelta(seconds=second))
                    for _ in range(4):
                        api.status()
                        list(api.events(once=True, poll_interval_seconds=5))
                self.assertEqual(12, runtime.observation_count)
                self.assertEqual(6, heartbeat.call_count)

    def test_single_owner_dashboard_survives_resolve_then_everything_stops(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db", check_same_thread=False) as store,
        ):
            api = ApiState(store)
            alive = {10, 20}
            launches = []
            bridge = Provider()
            host = RuntimeHost(
                api,
                alive=lambda pid: pid in alive,
                launch=lambda _: launches.append(10) or 10,
                bridge_factory=lambda: bridge,
            )
            host.attach(20)
            with patch.object(TrackingRuntime, "start"):
                host.track()
                host.track()
            self.assertEqual([10], launches)
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            api.tracking_runtime.observe(now)
            api.tracking_runtime.observe(now + timedelta(seconds=10))
            host.detach(20)
            self.assertFalse(host.tick())
            host.attach(20)
            alive.remove(10)
            self.assertFalse(host.tick())
            self.assertTrue(bridge.closed)
            self.assertIsNone(api.tracking_runtime)
            self.assertTrue(api.read_only)
            self.assertEqual(
                "2026-01-01T00:00:10Z", store.sessions()[0]["ended_at_utc"]
            )
            host.detach(20)
            self.assertTrue(host.tick())
            self.assertEqual([10], launches)

    def test_failed_launch_leaves_no_tracking_or_owner(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
        ):

            def fail(_):
                raise LaunchError("cancelled")

            host = RuntimeHost(ApiState(store), launch=fail)
            with self.assertRaises(LaunchError):
                host.track()
            self.assertTrue(host.tick())
            self.assertIsNone(store.active_session())

    def test_startup_failure_cleans_up_and_allows_another_launch(self):
        for failure in ("bridge", "thread"):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as tmp,
                SQLiteStore(Path(tmp) / "db", check_same_thread=False) as store,
            ):
                api = ApiState(store)
                bridge = Provider()

                def create_bridge():
                    if failure == "bridge":
                        raise RuntimeError("bridge unavailable")
                    return bridge

                host = RuntimeHost(
                    api,
                    alive=lambda _: True,
                    launch=lambda _: 10,
                    bridge_factory=create_bridge,
                )
                host.attach(20)
                with patch.object(
                    threading.Thread,
                    "start",
                    side_effect=RuntimeError("thread unavailable"),
                ):
                    with self.assertRaisesRegex(
                        LaunchError, "Could not start tracking"
                    ):
                        host.track()
                self.assertTrue(api.read_only)
                self.assertIsNone(api.tracking_runtime)
                self.assertIsNone(api.tracking_engine)
                self.assertIsNone(host.resolve_pid)
                self.assertIsNone(store.active_session())
                if failure == "thread":
                    self.assertTrue(bridge.closed)
                self.assertFalse(host.tick())
                host.bridge_factory = Provider
                try:
                    host.track()
                    self.assertFalse(api.read_only)
                    self.assertIsNotNone(api.tracking_runtime)
                finally:
                    host.stop_tracking()
                    host.detach(20)
                self.assertTrue(host.tick())

    def test_blocked_observation_cannot_prevent_exit_or_write_after_stop(self):
        entered, release = threading.Event(), threading.Event()

        class Blocked(Provider):
            def snapshot(self):
                entered.set()
                release.wait(5)
                return super().snapshot()

        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db", check_same_thread=False) as store,
        ):
            alive = {10}
            api = ApiState(store)
            host = RuntimeHost(
                api,
                alive=lambda pid: pid in alive,
                launch=lambda _: 10,
                bridge_factory=Blocked,
            )
            try:
                host.track()
                self.assertTrue(entered.wait(2))
                runtime = api.tracking_runtime
                alive.clear()
                started = time.monotonic()
                self.assertTrue(host.tick())
                self.assertLess(time.monotonic() - started, 2)
                release.set()
                runtime.stop()
                self.assertIsNone(store.active_session())
            finally:
                release.set()

    def test_unavailable_activity_recovery_does_not_bill_previous_project(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "db") as store,
        ):
            engine = TrackingEngine(store, snapshot_provider=Provider())
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            engine.poll(now, RuntimeSnapshot("A", "edit", False, 0, True))
            engine.poll(
                now + timedelta(seconds=5),
                RuntimeSnapshot(
                    "B",
                    "edit",
                    False,
                    None,
                    None,
                    activity_unavailable_reason="permission denied",
                ),
            )
            self.assertIsNone(store.active_session())
            engine.poll(
                now + timedelta(seconds=10),
                RuntimeSnapshot("B", "edit", False, 0, True),
            )
            self.assertEqual("B", store.active_session_summary()["project_name"])


class RuntimeProcessTest(unittest.TestCase):
    def start_runtime(self, db, pid):
        root = Path(__file__).resolve().parents[1]
        return subprocess.Popen(
            [
                sys.executable,
                str(root / "scripts" / "ResolveTimeTracker.py"),
                "--api",
                "--db",
                str(db),
                "--dashboard-pid",
                str(pid),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def wait_ready(self, db, child):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            self.assertIsNone(child.poll(), "runtime exited before becoming ready")
            try:
                info = json.loads(db.with_suffix(".runtime.json").read_text())
                base = f"http://127.0.0.1:{info['port']}"
                with urlopen(base + "/health", timeout=0.2):
                    return base
            except (OSError, ValueError):
                time.sleep(0.05)
        self.fail("runtime did not become ready")

    def stop_child(self, child):
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)

    def test_real_reporting_runtime_duplicate_and_detach_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "tracker.sqlite3"
            child = self.start_runtime(db, os.getpid())
            try:
                base = self.wait_ready(db, child)
                duplicate = self.start_runtime(db, os.getpid())
                try:
                    self.assertEqual(0, duplicate.wait(timeout=10))
                finally:
                    self.stop_child(duplicate)
                with urlopen(base + "/status") as response:
                    self.assertEqual("reporting", json.load(response)["connection"])
                with self.assertRaises(HTTPError) as error:
                    urlopen(
                        Request(base + "/tracking/resume", data=b"{}", method="POST")
                    )
                self.assertEqual(409, error.exception.code)
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + "/runtime/track", data=b"{}", method="POST"))
                self.assertEqual(403, error.exception.code)
                runtime_request(db, "/runtime/detach", {"pid": os.getpid()})
                self.assertEqual(0, child.wait(timeout=8))
                self.assertFalse(db.with_suffix(".runtime.json").exists())
            finally:
                self.stop_child(child)

    def test_dashboard_crash_also_terminates_reporting_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            dashboard = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            child = self.start_runtime(Path(tmp) / "tracker.sqlite3", dashboard.pid)
            try:
                self.wait_ready(Path(tmp) / "tracker.sqlite3", child)
                self.stop_child(dashboard)
                self.assertEqual(0, child.wait(timeout=8))
            finally:
                self.stop_child(child)
                self.stop_child(dashboard)
