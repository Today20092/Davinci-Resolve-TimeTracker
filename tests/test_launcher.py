import os
import unittest
from unittest.mock import patch

from scripts.ResolveTimeTracker import default_db_path
from scripts.ResolveTimeTrackerMenu import launch_command, python_command


class LauncherTest(unittest.TestCase):
    def test_menu_launcher_prefers_configured_python(self):
        with patch.dict(os.environ, {"RESOLVE_TIME_TRACKER_PYTHON": r"C:\Python313\python.exe"}):
            self.assertEqual([r"C:\Python313\python.exe"], python_command())

    def test_launch_command_runs_companion_entrypoint(self):
        command = launch_command()

        self.assertTrue(command[-1].endswith("scripts\\ResolveTimeTracker.py") or command[-1].endswith("scripts/ResolveTimeTracker.py"))

    def test_default_db_path_uses_local_app_data(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\Me\AppData\Local"}):
            self.assertEqual(
                r"C:\Users\Me\AppData\Local\ResolveTimeTracker\tracker.sqlite3",
                str(default_db_path()),
            )
