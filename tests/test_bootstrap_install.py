import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import install


class BootstrapInstallTest(unittest.TestCase):
    def test_detects_source_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (root / "scripts" / "ResolveTimeTracker.py").write_text("", encoding="utf-8")
            (root / "scripts" / "install_resolve_menu.py").write_text("", encoding="utf-8")

            self.assertTrue(install.is_source_checkout(root))

    def test_uses_current_checkout_when_installer_is_inside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (root / "scripts" / "ResolveTimeTracker.py").write_text("", encoding="utf-8")
            (root / "scripts" / "install_resolve_menu.py").write_text("", encoding="utf-8")

            self.assertEqual(root.resolve(), install.source_dir_for(root / "install.py", None))

    def test_default_source_dir_is_platform_aware(self):
        with patch("platform.system", return_value="Darwin"), patch("pathlib.Path.home", return_value=Path("/Users/me")):
            self.assertEqual(
                "/Users/me/Library/Application Support/ResolveTimeTracker/source",
                str(install.default_source_dir()).replace("\\", "/"),
            )
        with patch("platform.system", return_value="Linux"), patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/share"}):
            self.assertEqual(
                "/tmp/share/ResolveTimeTracker/source",
                str(install.default_source_dir()).replace("\\", "/"),
            )

    def test_verify_menu_script_requires_this_checkout_and_companion_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "ResolveTimeTrackerMenu.py"
            source.mkdir()
            target.write_text(f'REPO_ROOT = Path(r"{source.resolve()}")\n"--companion"\n', encoding="utf-8")

            install.verify_menu_script(target, source)

            target.write_text("wrong", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                install.verify_menu_script(target, source)

    def test_venv_python_detects_existing_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            if os.name == "nt":
                python = source / ".venv" / "Scripts" / "python.exe"
            else:
                python = source / ".venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            self.assertEqual(python, install.venv_python(source))

    def test_python_helper_does_not_install_uv(self):
        with patch("install.uv_command", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "install.ps1"):
                install.ensure_uv()

    def test_native_installers_use_uv_standalone_installers(self):
        root = Path(__file__).resolve().parents[1]

        self.assertIn("https://astral.sh/uv/install.ps1", (root / "install.ps1").read_text())
        self.assertIn("https://astral.sh/uv/install.sh", (root / "install.sh").read_text())
        self.assertIn("--no-sync", (root / "install.ps1").read_text())
        self.assertIn("--no-sync", (root / "install.sh").read_text())


if __name__ == "__main__":
    unittest.main()
