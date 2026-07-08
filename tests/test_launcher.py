import os
import unittest
from unittest.mock import patch

from scripts.ResolveTimeTracker import default_db_path


class LauncherTest(unittest.TestCase):
    def test_default_db_path_uses_local_app_data(self):
        with patch("platform.system", return_value="Windows"), patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\Me\AppData\Local"}):
            self.assertEqual(
                r"C:\Users\Me\AppData\Local\ResolveTimeTracker\tracker.sqlite3",
                str(default_db_path()),
            )
