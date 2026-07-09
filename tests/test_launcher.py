import os
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ResolveTimeTracker import default_db_path


class LauncherTest(unittest.TestCase):
    def test_default_db_path_uses_local_app_data(self):
        with patch("platform.system", return_value="Windows"), patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\Me\AppData\Local"}):
            self.assertEqual(
                r"C:\Users\Me\AppData\Local\ResolveTimeTracker\tracker.sqlite3",
                str(default_db_path()),
            )

    def test_default_db_path_uses_macos_application_support(self):
        with patch("platform.system", return_value="Darwin"), patch("pathlib.Path.home", return_value=Path("/Users/me")):
            self.assertEqual(
                "/Users/me/Library/Application Support/ResolveTimeTracker/tracker.sqlite3",
                str(default_db_path()).replace("\\", "/"),
            )

    def test_default_db_path_uses_linux_xdg_data_home(self):
        with patch("platform.system", return_value="Linux"), patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/share"}):
            self.assertEqual(
                "/tmp/share/ResolveTimeTracker/tracker.sqlite3",
                str(default_db_path()).replace("\\", "/"),
            )
