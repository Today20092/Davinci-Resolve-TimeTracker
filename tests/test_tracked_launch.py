import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.tracked_launch import (
    LaunchError,
    _runtime_lock,
    discover_resolve_executable,
    launch_tracking,
    process_alive,
    start_resolve,
    valid_resolve_executable,
)


class TrackedLaunchTest(unittest.TestCase):
    def test_only_existing_resolve_executables_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolve = root / "Resolve.exe"
            resolve.touch()
            other = root / "other.exe"
            other.touch()
            self.assertTrue(valid_resolve_executable(resolve))
            for invalid in (None, root, other, root / "missing/Resolve.exe"):
                self.assertFalse(valid_resolve_executable(invalid))

    def test_discovery_prefers_saved_then_conventional_then_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [
                root / location / "Resolve.exe"
                for location in ("saved", "standard", "registry")
            ]
            for path in paths:
                path.parent.mkdir()
                path.touch()
            with SQLiteStore(root / "tracker.sqlite3") as store:
                store.set_resolve_executable(paths[0])
                for expected in paths:
                    self.assertEqual(
                        expected,
                        discover_resolve_executable(
                            store,
                            conventional=paths[1],
                            registry_candidates=lambda: [paths[2]],
                        ),
                    )
                    expected.unlink()
                self.assertIsNone(
                    discover_resolve_executable(
                        store,
                        conventional=paths[1],
                        registry_candidates=lambda: [paths[2]],
                    )
                )

    def test_running_resolve_is_attached_without_spawn_or_picker(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "tracker.sqlite3") as store,
        ):
            spawn = Mock()
            picker = Mock()
            self.assertEqual(
                42,
                start_resolve(
                    store,
                    find_running=lambda: 42,
                    start_process=spawn,
                    select_executable=picker,
                ),
            )
            spawn.assert_not_called()
            picker.assert_not_called()

    def test_selected_executable_is_launched_once_and_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = root / "Resolve.exe"
            executable.touch()
            with SQLiteStore(root / "tracker.sqlite3") as store:
                spawn = Mock(return_value=Mock(pid=42))
                self.assertEqual(
                    42,
                    start_resolve(
                        store,
                        conventional=root / "missing/Resolve.exe",
                        registry_candidates=lambda: [],
                        select_executable=lambda: executable,
                        find_running=lambda: None,
                        start_process=spawn,
                    ),
                )
                spawn.assert_called_once_with([str(executable)])
                self.assertEqual(executable, store.resolve_executable())

    def test_invalid_or_cancelled_picker_never_spawns(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            SQLiteStore(Path(tmp) / "tracker.sqlite3") as store,
        ):
            for selected in (None, Path(tmp) / "other.exe"):
                with self.subTest(selected=selected):
                    spawn = Mock()
                    with self.assertRaisesRegex(LaunchError, "Resolve.exe"):
                        start_resolve(
                            store,
                            conventional=Path(tmp) / "missing/Resolve.exe",
                            registry_candidates=lambda: [],
                            select_executable=lambda: selected,
                            find_running=lambda: None,
                            start_process=spawn,
                        )
                    spawn.assert_not_called()

    def test_launch_failure_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "Resolve.exe"
            executable.touch()
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                with self.assertRaisesRegex(
                    LaunchError, "Could not launch DaVinci Resolve"
                ):
                    start_resolve(
                        store,
                        conventional=executable,
                        registry_candidates=lambda: [],
                        find_running=lambda: None,
                        start_process=Mock(side_effect=OSError("denied")),
                    )

    def test_tracking_delegates_to_managed_runtime(self):
        with patch("resolve_time_tracker.runtime_host.run_managed") as run:
            launch_tracking(Path("tracker.sqlite3"))
        run.assert_called_once_with(Path("tracker.sqlite3"), tracked=True)

    def test_process_alive_checks_current_and_invalid_pids(self):
        self.assertTrue(process_alive(os.getpid()))
        self.assertFalse(process_alive(0))
        self.assertFalse(process_alive(-1))
        self.assertFalse(process_alive(2147483647))

    def test_os_lock_excludes_duplicate_and_releases_after_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "tracker.sqlite3"
            script = "from pathlib import Path; import sys, time; from resolve_time_tracker.tracked_launch import _runtime_lock\nwith _runtime_lock(Path(sys.argv[1])) as acquired:\n print(acquired, flush=True)\n time.sleep(30)"
            child = subprocess.Popen(
                [sys.executable, "-c", script, str(db)],
                stdout=subprocess.PIPE,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                self.assertEqual("True", child.stdout.readline().strip())
                with _runtime_lock(db) as acquired:
                    self.assertFalse(acquired)
            finally:
                child.kill()
                child.communicate(timeout=5)
            with _runtime_lock(db) as acquired:
                self.assertTrue(acquired)
