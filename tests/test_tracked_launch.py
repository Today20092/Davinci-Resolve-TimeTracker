import os
import tempfile
import unittest
from pathlib import Path

from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.tracked_launch import (
    DEFAULT_RESOLVE_EXECUTABLE,
    LaunchError,
    discover_resolve_executable,
    launch_tracking,
    valid_resolve_executable,
)


class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.terminated = False

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        self.terminated = True

    def poll(self):
        return None


class TrackedLaunchTest(unittest.TestCase):
    def test_only_existing_resolve_executables_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolve = root / "Resolve.exe"
            resolve.touch()
            self.assertTrue(valid_resolve_executable(resolve))
            self.assertFalse(valid_resolve_executable(root / "resolve.exe"))
            self.assertFalse(valid_resolve_executable(root / "other.exe"))

    def test_discovery_reuses_saved_path_before_conventional_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = root / "saved" / "Resolve.exe"
            saved.parent.mkdir()
            saved.touch()
            conventional = root / "standard" / "Resolve.exe"
            conventional.parent.mkdir()
            conventional.touch()
            with SQLiteStore(root / "tracker.sqlite3") as store:
                store.set_resolve_executable(saved)
                self.assertEqual(
                    saved,
                    discover_resolve_executable(store, conventional=conventional),
                )

    def test_launch_attaches_to_running_resolve_and_starts_one_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "tracker.sqlite3"
            calls = []
            tracker = FakeProcess(99)

            result = launch_tracking(
                db,
                find_running=lambda: 42,
                start_process=lambda command: calls.append(command) or tracker,
                wait_for_exit=lambda pid: self.assertEqual(42, pid),
            )

            self.assertTrue(result.attached)
            self.assertFalse(result.reused_runtime)
            self.assertEqual(1, len(calls))
            self.assertIn("--tracker", calls[0])
            self.assertTrue(tracker.terminated)

    def test_second_launch_reuses_active_runtime_without_starting_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "tracker.sqlite3"
            lock = db.with_suffix(".runtime.lock")
            lock.write_text(str(os.getpid()), encoding="utf-8")
            result = launch_tracking(
                db,
                find_running=lambda: None,
                start_process=lambda command: self.fail("must not launch"),
            )
            self.assertTrue(result.reused_runtime)

    def test_launch_starts_selected_resolve_then_tracker_and_remembers_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "tracker.sqlite3"
            resolve = root / "Resolve.exe"
            resolve.touch()
            calls = []

            launch_tracking(
                db,
                conventional=root / "missing" / "Resolve.exe",
                registry_candidates=lambda: [],
                select_executable=lambda: resolve,
                find_running=lambda: None,
                start_process=lambda command: calls.append(command)
                or FakeProcess(10 + len(calls)),
                wait_for_exit=lambda pid: self.assertEqual(11, pid),
            )

            self.assertEqual([str(resolve)], calls[0])
            self.assertIn("--tracker", calls[1])
            with SQLiteStore(db) as store:
                self.assertEqual(resolve, store.resolve_executable())

    def test_invalid_selected_executable_leaves_no_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "tracker.sqlite3"
            with self.assertRaisesRegex(LaunchError, "Resolve.exe"):
                launch_tracking(
                    db,
                    conventional=Path(tmp) / "missing" / "Resolve.exe",
                    registry_candidates=lambda: [],
                    select_executable=lambda: Path(tmp) / "other.exe",
                    find_running=lambda: None,
                )
            self.assertFalse(db.with_suffix(".runtime.lock").exists())

    def test_default_conventional_location_is_windows_resolve_path(self):
        self.assertEqual(
            Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"),
            DEFAULT_RESOLVE_EXECUTABLE,
        )
