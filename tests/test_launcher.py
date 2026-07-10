import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ResolveTimeTracker import (
    default_db_path,
    parse_args,
    run_electron_companion,
)


class LauncherTest(unittest.TestCase):
    def test_default_db_path_uses_local_app_data(self):
        with (
            patch("platform.system", return_value="Windows"),
            patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\Me\AppData\Local"}),
        ):
            self.assertEqual(
                r"C:\Users\Me\AppData\Local\ResolveTimeTracker\tracker.sqlite3",
                str(default_db_path()),
            )

    def test_default_db_path_uses_macos_application_support(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("pathlib.Path.home", return_value=Path("/Users/me")),
        ):
            self.assertEqual(
                "/Users/me/Library/Application Support/ResolveTimeTracker/tracker.sqlite3",
                str(default_db_path()).replace("\\", "/"),
            )

    def test_default_db_path_uses_linux_xdg_data_home(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/share"}),
        ):
            self.assertEqual(
                "/tmp/share/ResolveTimeTracker/tracker.sqlite3",
                str(default_db_path()).replace("\\", "/"),
            )

    def test_parses_api_sidecar_arguments(self):
        args = parse_args(["--api", "--host", "127.0.0.1", "--port", "9000"])

        self.assertTrue(args.api)
        self.assertEqual("127.0.0.1", args.host)
        self.assertEqual(9000, args.port)

    def test_companion_launches_electron_with_current_python(self):
        with (
            patch("shutil.which", return_value="npm"),
            patch("subprocess.run") as run,
            patch("scripts.ResolveTimeTracker.os.name", "nt"),
            patch.dict(os.environ, {}, clear=True),
        ):
            run.return_value.returncode = 0

            self.assertEqual(0, run_electron_companion(Path("tracker.sqlite3")))

        command = run.call_args.args[0]
        env = run.call_args.kwargs["env"]
        self.assertEqual(["npm", "run", "desktop", "--"], command[:4])
        self.assertIn("--db", command)
        self.assertIn("--python", command)
        self.assertIn("RESOLVE_TIME_TRACKER_PYTHON", env)
        self.assertEqual(subprocess.CREATE_NO_WINDOW, run.call_args.kwargs["creationflags"])

    def test_companion_uses_uv_when_current_python_lacks_sidecar_deps(self):
        with (
            patch("shutil.which", return_value="npm"),
            patch("subprocess.run") as run,
            patch("scripts.ResolveTimeTracker.os.name", "nt"),
            patch.dict(os.environ, {}, clear=True),
        ):
            run.side_effect = [
                subprocess.CompletedProcess([], 1),
                subprocess.CompletedProcess([], 0),
            ]

            self.assertEqual(0, run_electron_companion(Path("tracker.sqlite3")))

        command = run.call_args.args[0]
        env = run.call_args.kwargs["env"]
        self.assertNotIn("--python", command)
        self.assertNotIn("RESOLVE_TIME_TRACKER_PYTHON", env)

    def test_companion_uses_console_python_when_launched_with_pythonw(self):
        with (
            patch("shutil.which", return_value="npm"),
            patch("subprocess.run") as run,
            patch("scripts.ResolveTimeTracker.os.name", "nt"),
            patch("scripts.ResolveTimeTracker.sys.executable", r"C:\app\.venv\Scripts\pythonw.exe"),
            patch("scripts.ResolveTimeTracker.Path.is_file", return_value=True),
            patch.dict(os.environ, {}, clear=True),
        ):
            run.return_value.returncode = 0

            self.assertEqual(0, run_electron_companion(Path("tracker.sqlite3")))

        env = run.call_args.kwargs["env"]
        self.assertEqual(
            r"C:\app\.venv\Scripts\python.exe",
            env["RESOLVE_TIME_TRACKER_PYTHON"],
        )
