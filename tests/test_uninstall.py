import tempfile
import unittest
from pathlib import Path

import uninstall


class UninstallTest(unittest.TestCase):
    def test_refuses_to_delete_directory_that_is_not_tracker_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unrelated = root / "unrelated"
            unrelated.mkdir()
            (unrelated / "important.txt").write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "not a Resolve Time Tracker"):
                uninstall.remove_installation(
                    source_dir=unrelated,
                    menu_script=root / "missing-menu.py",
                    startup_script=root / "missing-startup.cmd",
                    database=root / "missing.sqlite3",
                    delete_database=False,
                )

            self.assertTrue((unrelated / "important.txt").is_file())

    def test_finds_source_checkout_from_installed_menu_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            menu = root / "ResolveTimeTrackerMenu.py"
            source = root / "custom-source"
            menu.write_text(f'REPO_ROOT = Path(r"{source}")\n', encoding="utf-8")

            self.assertEqual(source, uninstall.installed_source_dir(menu))

    def test_removes_program_files_but_keeps_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            menu = root / "ResolveTimeTrackerMenu.py"
            startup = root / "ResolveTimeTrackerBackground.cmd"
            database = root / "tracker.sqlite3"
            source.mkdir()
            (source / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (source / "scripts").mkdir()
            (source / "scripts" / "ResolveTimeTracker.py").write_text(
                "", encoding="utf-8"
            )
            menu.write_text("launcher", encoding="utf-8")
            startup.write_text("startup", encoding="utf-8")
            database.write_text("time", encoding="utf-8")

            uninstall.remove_installation(
                source_dir=source,
                menu_script=menu,
                startup_script=startup,
                database=database,
                delete_database=False,
            )

            self.assertFalse(source.exists())
            self.assertFalse(menu.exists())
            self.assertFalse(startup.exists())
            self.assertTrue(database.exists())

    def test_deletes_database_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = root / "tracker.sqlite3"
            database.write_text("time", encoding="utf-8")

            uninstall.remove_installation(
                source_dir=root / "missing-source",
                menu_script=root / "missing-menu.py",
                startup_script=root / "missing-startup.cmd",
                database=database,
                delete_database=True,
            )

            self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()
