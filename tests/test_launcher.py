import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ResolveTimeTracker import (
    REPO_ROOT,
    default_db_path,
    main,
    parse_args,
    run_electron_companion,
)


class LauncherTest(unittest.TestCase):
    def test_legacy_login_entry_does_nothing(self):
        with patch("resolve_time_tracker.runtime_host.run_managed") as run:
            self.assertEqual(0, main(["--background"]))
        run.assert_not_called()

    def test_default_db_path_uses_platform_data_directory(self):
        for system, environment, home, expected in (
            (
                "Windows",
                {"LOCALAPPDATA": "C:/Users/Me/AppData/Local"},
                "/unused",
                "C:/Users/Me/AppData/Local",
            ),
            ("Darwin", {}, "/Users/me", "/Users/me/Library/Application Support"),
            ("Linux", {"XDG_DATA_HOME": "/tmp/share"}, "/unused", "/tmp/share"),
        ):
            with (
                self.subTest(system=system),
                patch("platform.system", return_value=system),
                patch.dict(os.environ, environment),
                patch("pathlib.Path.home", return_value=Path(home)),
            ):
                self.assertEqual(
                    Path(expected) / "ResolveTimeTracker/tracker.sqlite3",
                    default_db_path(),
                )

    def test_parses_dashboard_owner_and_ephemeral_port(self):
        args = parse_args(["--api", "--dashboard-pid", "123"])
        self.assertTrue(args.api)
        self.assertEqual(123, args.dashboard_pid)
        self.assertEqual(0, args.port)

    def test_runtime_modes_forward_owner_and_tracking_intent(self):
        for mode, tracked in (
            ("--api", False),
            ("--tracker", True),
            ("--tracked-launch", True),
        ):
            with (
                self.subTest(mode=mode),
                patch("resolve_time_tracker.runtime_host.run_managed") as run,
            ):
                self.assertEqual(
                    0,
                    main(
                        [
                            mode,
                            "--db",
                            "custom.sqlite3",
                            "--dashboard-pid",
                            "123",
                            "--port",
                            "9000",
                        ]
                    ),
                )
                run.assert_called_once_with(
                    Path("custom.sqlite3"),
                    tracked=tracked,
                    dashboard_pid=123,
                    port=9000,
                )

    def test_default_launches_dashboard(self):
        with patch(
            "scripts.ResolveTimeTracker.run_electron_companion", return_value=0
        ) as run:
            self.assertEqual(0, main([]))
        run.assert_called_once_with(default_db_path(), background=False, dev=False)

    def test_ordinary_launch_starts_prebuilt_electron_without_build_tool(self):
        with (
            patch("scripts.ResolveTimeTracker.Path.is_file", return_value=True),
            patch("scripts.ResolveTimeTracker._is_windows", return_value=True),
            patch(
                "scripts.ResolveTimeTracker._python_has_sidecar_deps", return_value=True
            ),
            patch("subprocess.Popen") as spawn,
            patch("subprocess.run") as run,
            patch("shutil.which") as which,
        ):
            self.assertEqual(0, run_electron_companion(Path("tracker.sqlite3")))
        spawn.assert_called_once()
        self.assertEqual(
            [
                str(REPO_ROOT / "frontend/node_modules/electron/dist/electron.exe"),
                str(REPO_ROOT / "frontend"),
                "--db",
                "tracker.sqlite3",
                "--python",
                sys.executable,
            ],
            spawn.call_args.args[0],
        )
        self.assertEqual(subprocess.DEVNULL, spawn.call_args.kwargs["stdin"])
        run.assert_not_called()
        which.assert_not_called()

    def test_missing_build_reports_installer_without_spawning(self):
        with (
            patch("scripts.ResolveTimeTracker.Path.is_file", return_value=False),
            patch("subprocess.Popen") as spawn,
        ):
            with self.assertRaisesRegex(RuntimeError, "installer"):
                run_electron_companion(Path("tracker.sqlite3"))
        spawn.assert_not_called()

    def test_development_launch_uses_pnpm(self):
        with (
            patch("shutil.which", return_value="pnpm") as which,
            patch("subprocess.run") as run,
            patch("scripts.ResolveTimeTracker._is_windows", return_value=False),
            patch(
                "scripts.ResolveTimeTracker._python_has_sidecar_deps", return_value=True
            ),
        ):
            run.return_value.returncode = 7
            self.assertEqual(
                7, run_electron_companion(Path("tracker.sqlite3"), dev=True)
            )
        which.assert_called_once_with("pnpm")
        self.assertEqual(["pnpm", "run", "desktop:dev"], run.call_args.args[0])
        self.assertEqual(
            "tracker.sqlite3", run.call_args.kwargs["env"]["RESOLVE_TIME_TRACKER_DB"]
        )

    def test_unavailable_sidecar_python_is_not_forwarded(self):
        with (
            patch("scripts.ResolveTimeTracker.Path.is_file", return_value=True),
            patch(
                "scripts.ResolveTimeTracker._python_has_sidecar_deps",
                return_value=False,
            ),
            patch.dict(os.environ, {}, clear=True),
            patch("subprocess.Popen") as spawn,
        ):
            run_electron_companion(Path("tracker.sqlite3"))
        self.assertNotIn("--python", spawn.call_args.args[0])
        self.assertNotIn("RESOLVE_TIME_TRACKER_PYTHON", spawn.call_args.kwargs["env"])

    def test_pythonw_uses_console_python_for_sidecar(self):
        with (
            patch("scripts.ResolveTimeTracker.Path.is_file", return_value=True),
            patch("scripts.ResolveTimeTracker._is_windows", return_value=True),
            patch(
                "scripts.ResolveTimeTracker._python_has_sidecar_deps", return_value=True
            ),
            patch(
                "scripts.ResolveTimeTracker.sys.executable",
                r"C:\app\Scripts\pythonw.exe",
            ),
            patch("subprocess.Popen") as spawn,
        ):
            run_electron_companion(Path("tracker.sqlite3"))
        self.assertEqual(
            r"C:\app\Scripts\python.exe",
            spawn.call_args.kwargs["env"]["RESOLVE_TIME_TRACKER_PYTHON"],
        )
