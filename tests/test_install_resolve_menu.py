import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.install_resolve_menu import (
    DEV_MENU_SCRIPT_NAME,
    MENU_SCRIPT_NAME,
    default_utility_dir,
    install_menu_script,
    install_native_probe,
    remove_native_probe,
)


class InstallResolveMenuTest(unittest.TestCase):
    def test_native_probe_menu_records_when_the_full_invocation_returns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scripts" / "native_ui_probe.py"
            source.parent.mkdir()
            report_path = root / "probe.json"
            report_path.write_text("{}", encoding="utf-8")
            source.write_text(
                f"PROBE_RESULT = {{'report_path': {str(report_path)!r}}}",
                encoding="utf-8",
            )
            target = install_native_probe(repo_root=root, utility_dir=root / "Utility")
            exec(target.read_text(), {"resolve": None, "fusion": None, "bmd": None})
            self.assertTrue(
                json.loads(report_path.read_text())["menu_invocation_returned"]
            )

    def test_native_probe_cli_does_not_install_production_launchers(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = [
                sys.executable,
                "scripts/install_resolve_menu.py",
                "--utility-dir",
                tmp,
            ]
            subprocess.run(
                command + ["--native-probe"], check=True, capture_output=True
            )
            self.assertEqual(
                ["ResolveTimeTrackerNativeProbe.py"],
                [p.name for p in Path(tmp).iterdir()],
            )
            subprocess.run(
                command + ["--remove-native-probe"], check=True, capture_output=True
            )
            self.assertEqual([], list(Path(tmp).iterdir()))

    def test_native_probe_cleanup_removes_only_the_matching_generated_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, utility = Path(tmp) / "repo", Path(tmp) / "Utility"
            target = install_native_probe(repo_root=root, utility_dir=utility)
            self.assertEqual(
                target, install_native_probe(repo_root=root, utility_dir=utility)
            )
            self.assertTrue(remove_native_probe(repo_root=root, utility_dir=utility))
            self.assertFalse(remove_native_probe(repo_root=root, utility_dir=utility))
            target.write_text("different user script", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                install_native_probe(repo_root=root, utility_dir=utility)
            with self.assertRaises(ValueError):
                remove_native_probe(repo_root=root, utility_dir=utility)
            self.assertEqual("different user script", target.read_text())

    def test_native_probe_menu_uses_host_context_without_changing_production_entries(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "checkout with 'quotes'"
            source = root / "scripts" / "native_ui_probe.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "fusion.append((resolve, bmd, __name__))", encoding="utf-8"
            )
            utility = Path(tmp) / "Utility"
            utility.mkdir()
            production = utility / MENU_SCRIPT_NAME
            production.write_text("existing production entry", encoding="utf-8")

            target = install_native_probe(repo_root=root, utility_dir=utility)
            fusion, resolve, bmd = [], object(), object()
            exec(target.read_text(), {"fusion": fusion, "resolve": resolve, "bmd": bmd})

            self.assertEqual([(resolve, bmd, "__main__")], fusion)
            self.assertEqual("existing production entry", production.read_text())
            self.assertFalse((utility / DEV_MENU_SCRIPT_NAME).exists())

    def test_installs_generated_launcher_with_repo_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            utility_dir = Path(tmp) / "Utility"
            repo_root = Path(tmp) / "repo"

            target = install_menu_script(repo_root=repo_root, utility_dir=utility_dir)

            self.assertEqual(utility_dir / MENU_SCRIPT_NAME, target)
            text = target.read_text(encoding="utf-8")
            self.assertIn(str(repo_root.resolve()), text)
            self.assertIn("RESOLVE_TIME_TRACKER_REPO", text)
            self.assertIn("ResolveTimeTracker.py", text)
            self.assertIn("--tracked-launch", text)
            self.assertIn("subprocess.Popen", text)
            self.assertIn('os.name == "nt"', text)
            self.assertIn('"bin/python"', text)
            self.assertIn("installer first", text)

    def test_installs_separate_development_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            utility_dir = Path(tmp) / "Utility"

            install_menu_script(repo_root=Path(tmp) / "repo", utility_dir=utility_dir)

            target = utility_dir / DEV_MENU_SCRIPT_NAME
            self.assertTrue(target.is_file())
            self.assertIn('"--dev"', target.read_text(encoding="utf-8"))

    def test_default_utility_dir_uses_linux_resolve_script_folder(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch.dict("os.environ", {"XDG_DATA_HOME": "/tmp/share"}),
        ):
            self.assertEqual(
                Path("/tmp/share/DaVinciResolve/Fusion/Scripts/Utility"),
                default_utility_dir(),
            )

    def test_default_utility_dir_uses_macos_resolve_script_folder(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("pathlib.Path.home", return_value=Path("/Users/me")),
        ):
            self.assertEqual(
                Path(
                    "/Users/me/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
                ),
                default_utility_dir(),
            )
