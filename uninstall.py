"""Remove Resolve Time Tracker files while optionally preserving tracked time."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import sys
from pathlib import Path


MENU_SCRIPT_NAME = "ResolveTimeTrackerMenu.py"
DEV_MENU_SCRIPT_NAME = "ResolveTimeTrackerDevMenu.py"
STARTUP_SCRIPT_NAME = "ResolveTimeTrackerBackground.cmd"


def data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "ResolveTimeTracker"


def utility_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        return (
            Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            / "Blackmagic Design"
            / "DaVinci Resolve"
            / "Support"
            / "Fusion"
            / "Scripts"
            / "Utility"
        )
    if system == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Blackmagic Design"
            / "DaVinci Resolve"
            / "Fusion"
            / "Scripts"
            / "Utility"
        )
    return (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        / "DaVinciResolve"
        / "Fusion"
        / "Scripts"
        / "Utility"
    )


def startup_script() -> Path:
    return (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / STARTUP_SCRIPT_NAME
    )


def installed_source_dir(menu_script: Path) -> Path | None:
    if not menu_script.is_file():
        return None
    match = re.search(
        r'^REPO_ROOT = Path\(r["\'](.+)["\']\)$',
        menu_script.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return Path(match.group(1)) if match else None


def is_source_checkout(path: Path) -> bool:
    return (path / "pyproject.toml").is_file() and (
        path / "scripts" / "ResolveTimeTracker.py"
    ).is_file()


def remove_installation(
    *,
    source_dir: Path,
    menu_script: Path,
    startup_script: Path,
    database: Path,
    delete_database: bool,
) -> None:
    if source_dir.is_dir() and not is_source_checkout(source_dir):
        raise ValueError(
            f"Refusing to remove {source_dir}: not a Resolve Time Tracker checkout"
        )
    menu_script.unlink(missing_ok=True)
    menu_script.with_name(DEV_MENU_SCRIPT_NAME).unlink(missing_ok=True)
    startup_script.unlink(missing_ok=True)
    if source_dir.is_dir():
        shutil.rmtree(source_dir)
    if delete_database:
        database.unlink(missing_ok=True)
        parent = database.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


def confirm(prompt: str, *, default: bool = False) -> bool:
    if not sys.stdin.isatty():
        return default
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Uninstall Resolve Time Tracker")
    parser.add_argument(
        "--yes", action="store_true", help="Skip uninstall confirmation"
    )
    parser.add_argument(
        "--delete-data",
        action="store_true",
        help="Permanently delete tracker.sqlite3 without asking",
    )
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--utility-dir", type=Path, default=utility_dir())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database = data_dir() / "tracker.sqlite3"
    menu_script = args.utility_dir / MENU_SCRIPT_NAME
    source_dir = (
        args.source_dir or installed_source_dir(menu_script) or data_dir() / "source"
    )
    print("Quit Resolve Time Tracker from its tray menu before continuing.")
    print("Uninstall plan:")
    print(f"  - Remove source and app files: {source_dir}")
    print(f"  - Remove Resolve menu entry: {menu_script}")
    if platform.system() == "Windows":
        print(f"  - Remove automatic startup entry: {startup_script()}")
    print(f"  - Tracked-time database: {database}")
    if not args.yes and not confirm("Continue with uninstall?"):
        print("Uninstall cancelled.")
        return 0
    delete_database = args.delete_data or (
        not args.yes
        and confirm("Also permanently delete all tracked projects and time?")
    )
    remove_installation(
        source_dir=source_dir,
        menu_script=menu_script,
        startup_script=startup_script(),
        database=database,
        delete_database=delete_database,
    )
    print("Resolve Time Tracker uninstalled.")
    print(
        "Tracked-time database deleted."
        if delete_database
        else f"Data kept: {database}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"Uninstall failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
