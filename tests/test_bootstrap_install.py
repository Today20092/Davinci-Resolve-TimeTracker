import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import install


class BootstrapInstallTest(unittest.TestCase):
    def test_failed_new_install_removes_only_new_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            data = root / "tracker.sqlite3"
            data.write_bytes(b"existing history")

            def clone(target, *_):
                target.mkdir()
                (target / "partial").touch()

            with (
                patch("install.ensure_source", side_effect=clone),
                self.assertRaises(RuntimeError),
            ):
                with install.preserve_source(source, "unused", False):
                    raise RuntimeError("dependency install failed")
            self.assertFalse(source.exists())
            self.assertEqual(b"existing history", data.read_bytes())

    def test_failed_build_restores_prior_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / ".venv" / "old"
            original.parent.mkdir()
            original.write_text("working")
            with self.assertRaises(RuntimeError):
                with install.preserve_build(root):
                    self.assertFalse(original.exists())
                    generated = root / "frontend" / "dist"
                    generated.mkdir(parents=True)
                    (generated / "broken").touch()
                    raise RuntimeError("build failed")
            self.assertEqual("working", original.read_text())
            self.assertFalse((root / "frontend" / "dist").exists())

    def test_partial_backup_failure_never_deletes_untouched_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [root / ".venv", root / "frontend" / "node_modules"]
            for directory in paths:
                directory.mkdir(parents=True)
                (directory / "old").write_text("working")
            rename = Path.rename

            def fail_second(source, target):
                if source == paths[1]:
                    raise PermissionError("directory is in use")
                return rename(source, target)

            with (
                patch.object(Path, "rename", fail_second),
                self.assertRaises(PermissionError),
            ):
                with install.preserve_build(root):
                    self.fail("must not start the build")
            for directory in paths:
                self.assertEqual("working", (directory / "old").read_text())

    def test_preflight_reports_missing_external_tools(self):
        with patch("install.shutil.which", return_value=None):
            self.assertEqual(
                [
                    "Git is required to download the project source.",
                    "Node.js with pnpm is required to build the desktop app.",
                ],
                install.prerequisite_errors(Path("missing-source")),
            )

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
                f'REPO_ROOT = Path(r"{source.resolve()}")\n"--tracked-launch"\n',
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

    def test_install_frontend_uses_frozen_pnpm_lockfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            frontend = source / "frontend"
            frontend.mkdir()
            (frontend / "package.json").write_text("{}", encoding="utf-8")

            with (
                patch("shutil.which", return_value="pnpm"),
                patch("install.run") as run,
            ):
                install.install_frontend(source)

        self.assertEqual(
            [
                call(["pnpm", "install", "--frozen-lockfile"], cwd=frontend),
                call(["pnpm", "exec", "electron", "--version"], cwd=frontend),
                call(["pnpm", "run", "build"], cwd=frontend),
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

    def test_launchers_replace_legacy_startup_without_touching_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = root / ".venv/Scripts/pythonw.exe"
            python.parent.mkdir(parents=True)
            python.touch()
            legacy = root / "Startup" / install.STARTUP_SCRIPT_NAME
            legacy.parent.mkdir()
            legacy.write_text("old startup")
            data = root / "tracker.sqlite3"
            data.write_bytes(b"database and saved settings")
            targets = [
                root / "Programs/Tracked.lnk",
                root / "Desktop/Tracked.lnk",
                root / "Programs/Dashboard.lnk",
            ]
            scripts = []

            def save(command, **kwargs):
                import base64

                scripts.append(base64.b64decode(command[-1]).decode("utf-16-le"))
                targets[len(scripts) - 1].write_bytes(b"shortcut")

            with (
                patch("platform.system", return_value="Windows"),
                patch("install.windows_launcher_paths", return_value=targets),
                patch("install.windows_startup_dir", return_value=legacy.parent),
                patch("install.run", side_effect=save),
            ):
                self.assertEqual(targets, install.install_launchers(root))
            self.assertEqual(3, len(scripts))
            self.assertIn("--tracked-launch", scripts[0])
            self.assertIn("--tracked-launch", scripts[1])
            self.assertIn("--companion", scripts[2])
            self.assertFalse(legacy.exists())
            self.assertEqual(b"database and saved settings", data.read_bytes())

    def test_failed_launcher_attempt_restores_old_and_removes_only_new_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old, new, data = (
                root / "old.lnk",
                root / "new.lnk",
                root / "tracker.sqlite3",
            )
            old.write_bytes(b"previous launcher")
            data.write_bytes(b"saved data")
            with self.assertRaisesRegex(RuntimeError, "failed"):
                with install.preserve_launchers([old, new]):
                    old.write_bytes(b"replacement")
                    new.write_bytes(b"partial")
                    raise RuntimeError("failed")
            self.assertEqual(b"previous launcher", old.read_bytes())
            self.assertFalse(new.exists())
            self.assertEqual(b"saved data", data.read_bytes())

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

    def test_windows_installer_waits_for_permission_to_close(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "install.ps1").read_text()

        self.assertIn("Installation finished successfully.", text)
        self.assertIn("Installation did not finish successfully.", text)
        self.assertIn("Would you like to close this window? [y/N]", text)
        self.assertIn("Wait-ToClose", text)

    def test_windows_installer_supports_piped_execution(self):
        text = (Path(__file__).resolve().parents[1] / "install.ps1").read_text()

        self.assertIn("if ($PSScriptRoot)", text)


if __name__ == "__main__":
    unittest.main()
