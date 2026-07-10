import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import install


class BootstrapInstallTest(unittest.TestCase):
    def test_detects_source_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (root / "scripts" / "ResolveTimeTracker.py").write_text(
                "", encoding="utf-8"
            )
            (root / "scripts" / "install_resolve_menu.py").write_text(
                "", encoding="utf-8"
            )

            self.assertTrue(install.is_source_checkout(root))

    def test_uses_current_checkout_when_installer_is_inside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (root / "scripts" / "ResolveTimeTracker.py").write_text(
                "", encoding="utf-8"
            )
            (root / "scripts" / "install_resolve_menu.py").write_text(
                "", encoding="utf-8"
            )

            self.assertEqual(
                root.resolve(), install.source_dir_for(root / "install.py", None)
            )

    def test_default_source_dir_is_platform_aware(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("pathlib.Path.home", return_value=Path("/Users/me")),
        ):
            self.assertEqual(
                "/Users/me/Library/Application Support/ResolveTimeTracker/source",
                str(install.default_source_dir()).replace("\\", "/"),
            )
        with (
            patch("platform.system", return_value="Linux"),
            patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/share"}),
        ):
            self.assertEqual(
                "/tmp/share/ResolveTimeTracker/source",
                str(install.default_source_dir()).replace("\\", "/"),
            )

    def test_verify_menu_script_requires_this_checkout_and_companion_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "ResolveTimeTrackerMenu.py"
            source.mkdir()
            target.write_text(
                f'REPO_ROOT = Path(r"{source.resolve()}")\n"--companion"\n',
                encoding="utf-8",
            )

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

    def test_install_frontend_runs_npm_ci_and_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            frontend = source / "frontend"
            frontend.mkdir()
            (frontend / "package.json").write_text("{}", encoding="utf-8")

            with (
                patch("shutil.which", return_value="npm"),
                patch("install.run") as run,
            ):
                install.install_frontend(source)

        self.assertEqual(
            [
                call(["npm", "ci"], cwd=frontend),
                call(["npm", "run", "build"], cwd=frontend),
            ],
            run.mock_calls,
        )

    def test_install_menu_forces_python_313_uv_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            target = source / "ResolveTimeTrackerMenu.py"
            if os.name == "nt":
                python = source / ".venv" / "Scripts" / "python.exe"
            else:
                python = source / ".venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            with (
                patch(
                    "install.run",
                    side_effect=["", str(target)],
                ) as run,
                patch("install.verify_menu_script"),
            ):
                self.assertEqual(target, install.install_menu(source, ["uv"], None))

        self.assertEqual(
            [
                call(["uv", "sync", "--python", "3.13"], cwd=source),
                call(
                    [
                        "uv",
                        "run",
                        "--python",
                        "3.13",
                        "scripts/install_resolve_menu.py",
                    ],
                    cwd=source,
                ),
            ],
            run.mock_calls,
        )

    def test_startup_choice_defaults_to_manual_without_tty(self):
        with patch("sys.stdin.isatty", return_value=False):
            self.assertEqual("manual", install.choose_startup_mode())

    def test_startup_choice_accepts_yes_for_auto_start(self):
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value="yes"),
        ):
            self.assertEqual("auto", install.choose_startup_mode())

    def test_startup_choice_accepts_no_for_manual_menu_start(self):
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value="no"),
        ):
            self.assertEqual("manual", install.choose_startup_mode())

    def test_confirm_install_requires_yes_when_interactive(self):
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value="no"),
        ):
            self.assertFalse(install.confirm_install())
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value="y"),
        ):
            self.assertTrue(install.confirm_install())

    def test_installs_windows_startup_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            python = source / ".venv" / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")

            with (
                patch("platform.system", return_value="Windows"),
                patch.dict(os.environ, {"APPDATA": str(root / "roaming")}),
            ):
                target = install.install_startup(source, python)

            text = target.read_text(encoding="utf-8")
            self.assertEqual(install.STARTUP_SCRIPT_NAME, target.name)
            self.assertIn("ResolveTimeTracker.py", text)
            self.assertIn("--tracker", text)

    def test_electron_connects_to_existing_sidecar_before_spawning(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "frontend" / "electron" / "main.cjs").read_text()

        self.assertIn("async function apiIsRunning", text)
        self.assertIn("async function apiSupportsPdf", text)
        self.assertIn('"reportlab"', text)
        self.assertIn("if (!(await apiIsRunning()))", text)
        self.assertIn("startSidecar()", text)

    def test_uv_command_honors_bootstrap_env_path(self):
        with patch.dict(os.environ, {"RESOLVE_TIME_TRACKER_UV": "/tmp/uv"}):
            self.assertEqual(["/tmp/uv"], install.uv_command())

    def test_native_installers_use_uv_standalone_installers(self):
        root = Path(__file__).resolve().parents[1]

        self.assertIn(
            "https://astral.sh/uv/install.ps1", (root / "install.ps1").read_text()
        )
        self.assertIn(
            "https://astral.sh/uv/install.sh", (root / "install.sh").read_text()
        )
        self.assertIn("--python 3.13", (root / "install.ps1").read_text())
        self.assertIn("--python 3.13", (root / "install.sh").read_text())
        self.assertIn("--no-project", (root / "install.ps1").read_text())
        self.assertIn("--no-project", (root / "install.sh").read_text())


if __name__ == "__main__":
    unittest.main()
