import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.install_resolve_menu import MENU_SCRIPT_NAME, default_utility_dir, install_menu_script


class InstallResolveMenuTest(unittest.TestCase):
    def test_installs_generated_launcher_with_repo_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            utility_dir = Path(tmp) / "Utility"
            repo_root = Path(tmp) / "repo"

            target = install_menu_script(repo_root=repo_root, utility_dir=utility_dir)

            self.assertEqual(utility_dir / MENU_SCRIPT_NAME, target)
            text = target.read_text(encoding="utf-8")
            self.assertIn(str(repo_root), text)
            self.assertIn("RESOLVE_TIME_TRACKER_REPO", text)
            self.assertIn("ResolveTimeTracker.py", text)
            self.assertIn("--companion", text)
            self.assertIn("subprocess.Popen", text)
            self.assertIn('os.name == "nt"', text)
            self.assertIn('".venv" / "bin" / "python"', text)
            self.assertIn("Run uv sync", text)

    def test_default_utility_dir_uses_linux_resolve_script_folder(self):
        with patch("platform.system", return_value="Linux"), patch.dict("os.environ", {"XDG_DATA_HOME": "/tmp/share"}):
            self.assertEqual(
                Path("/tmp/share/DaVinciResolve/Fusion/Scripts/Utility"),
                default_utility_dir(),
            )

    def test_default_utility_dir_uses_macos_resolve_script_folder(self):
        with patch("platform.system", return_value="Darwin"), patch("pathlib.Path.home", return_value=Path("/Users/me")):
            self.assertEqual(
                Path("/Users/me/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"),
                default_utility_dir(),
            )
