"""Opt-in real installer check, with only OS profile-path discovery redirected."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import install
from resolve_time_tracker.database import SQLiteStore


@unittest.skipUnless(
    os.name == "nt" and os.environ.get("RESOLVE_RUN_INSTALL_INTEGRATION") == "1",
    "requires Windows and RESOLVE_RUN_INSTALL_INTEGRATION=1; installs real dependencies",
)
class WindowsInstallIntegrationTest(unittest.TestCase):
    def test_fresh_upgrade_and_failed_shortcut_attempt_preserve_the_installation(self):
        with tempfile.TemporaryDirectory(prefix="resolve-install-check-") as tmp:
            root = Path(tmp).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            source, utility = root / "source", root / "Utility"
            programs, desktop = root / "Programs", root / "Desktop"
            startup = programs / "Startup"
            targets = [
                programs / "DaVinci Resolve + Time Tracker.lnk",
                desktop / "DaVinci Resolve + Time Tracker.lnk",
                programs / "Resolve Time Tracker Dashboard.lnk",
            ]
            for target in [source, utility, startup, *targets]:
                self.assertTrue(target.resolve().is_relative_to(root))
            shutil.copytree(
                Path(__file__).resolve().parents[1],
                source,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".venv",
                    "node_modules",
                    "dist",
                    "__pycache__",
                    ".pytest_cache",
                    ".ruff_cache",
                ),
            )
            environment = {
                "APPDATA": str(root / "Roaming"),
                "LOCALAPPDATA": str(root / "Local"),
                "UV_CACHE_DIR": str(root / "uv-cache"),
                "PNPM_HOME": str(root / "pnpm-home"),
                "RESOLVE_TIME_TRACKER_UV": shutil.which("uv") or "uv",
            }
            database = root / "Local/ResolveTimeTracker/tracker.sqlite3"
            store = SQLiteStore(database)
            store.upsert_project("Disposable installer history")
            saved_resolve = root / "Resolve.exe"
            saved_resolve.touch()
            store.set_resolve_executable(saved_resolve)
            store.close()
            database_hash = hashlib.sha256(database.read_bytes()).hexdigest()

            # Profile discovery is substituted; all installer stages and COM writes are real.
            with (
                patch.dict(os.environ, environment),
                patch("install.windows_launcher_paths", return_value=targets),
                patch("install.windows_startup_dir", return_value=startup),
                patch.object(sys, "stdin", io.StringIO()),
                patch.object(
                    sys,
                    "argv",
                    [
                        "install.py",
                        "--source-dir",
                        str(source),
                        "--utility-dir",
                        str(utility),
                    ],
                ),
            ):
                os.environ.pop("UV_PROJECT_ENVIRONMENT", None)
                os.environ.pop("VIRTUAL_ENV", None)
                store_path = subprocess.run(
                    [shutil.which("pnpm.cmd") or "pnpm.cmd", "store", "path"],
                    cwd=source / "frontend",
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                ).stdout.strip()
                self.assertTrue(Path(store_path).resolve().is_relative_to(root))
                self.assertEqual(0, install.main())
                self.assertTrue((source / "frontend/dist/index.html").is_file())
                self.assertTrue((source / ".venv/Scripts/pythonw.exe").is_file())
                self.assertTrue(all(path.is_file() for path in targets))
                shortcut_paths = ",".join(
                    "'" + str(path).replace("'", "''") + "'" for path in targets
                )
                shortcut_details = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "$shell=New-Object -ComObject WScript.Shell; "
                        f"@({shortcut_paths}) | ForEach-Object {{$shell.CreateShortcut($_)}} | "
                        "Select-Object TargetPath,Arguments,WorkingDirectory | ConvertTo-Json -Compress",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                details = json.loads(shortcut_details.stdout)
                self.assertEqual(3, len(details))
                for index, shortcut in enumerate(details):
                    self.assertEqual(
                        source / ".venv/Scripts/pythonw.exe",
                        Path(shortcut["TargetPath"]),
                    )
                    self.assertEqual(source, Path(shortcut["WorkingDirectory"]))
                    self.assertIn(
                        str(source / "scripts/ResolveTimeTracker.py"),
                        shortcut["Arguments"],
                    )
                    self.assertIn(
                        "--companion" if index == 2 else "--tracked-launch",
                        shortcut["Arguments"],
                    )
                menu = utility / "ResolveTimeTrackerMenu.py"
                self.assertIn(str(source), menu.read_text(encoding="utf-8"))
                self.assertIn("--tracked-launch", menu.read_text(encoding="utf-8"))

                startup.mkdir(parents=True, exist_ok=True)
                legacy = startup / install.STARTUP_SCRIPT_NAME
                legacy.write_text("legacy startup", encoding="utf-8")
                self.assertEqual(0, install.main())
                self.assertFalse(legacy.exists())
                self.assertEqual(
                    database_hash, hashlib.sha256(database.read_bytes()).hexdigest()
                )

                legacy.write_text("keep this if upgrade fails", encoding="utf-8")
                artifacts = [
                    menu,
                    utility / "ResolveTimeTrackerDevMenu.py",
                    *targets,
                    legacy,
                ]
                before = {path: path.read_bytes() for path in artifacts}
                environment_marker = source / ".venv/previous-installation"
                build_marker = source / "frontend/dist/previous-build"
                environment_marker.write_text(
                    "working Python environment", encoding="utf-8"
                )
                build_marker.write_text("working dashboard", encoding="utf-8")
                run = subprocess.run
                shortcut_attempts = 0

                def fail_third_shortcut(command, *args, **kwargs):
                    nonlocal shortcut_attempts
                    if Path(command[0]).name.lower() == "powershell.exe":
                        shortcut_attempts += 1
                        if shortcut_attempts == 3:
                            raise subprocess.CalledProcessError(
                                23, command, "injected OS write failure"
                            )
                    return run(command, *args, **kwargs)

                # Only the final OS write fails; two replacement shortcuts are actually saved.
                with patch("subprocess.run", side_effect=fail_third_shortcut):
                    with self.assertRaises(subprocess.CalledProcessError):
                        install.main()
                self.assertEqual(3, shortcut_attempts)
                for path, content in before.items():
                    self.assertEqual(
                        content, path.read_bytes(), str(path.relative_to(root))
                    )
                self.assertEqual(
                    "working Python environment", environment_marker.read_text()
                )
                self.assertEqual("working dashboard", build_marker.read_text())
                self.assertEqual(
                    database_hash, hashlib.sha256(database.read_bytes()).hexdigest()
                )


if __name__ == "__main__":
    unittest.main()
