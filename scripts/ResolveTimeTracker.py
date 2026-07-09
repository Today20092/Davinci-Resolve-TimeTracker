"""Resolve-native entry point launched from Resolve's Scripts menu."""

from __future__ import annotations

import argparse
import os
import platform
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from resolve_time_tracker import __version__
from resolve_time_tracker.resolve_ui import run_resolve_ui


def default_db_path() -> Path:
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "ResolveTimeTracker" / "tracker.sqlite3"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=default_db_path())
    parser.add_argument("--companion", action="store_true")
    parser.add_argument("--version", action="store_true")
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"Resolve Time Tracker {__version__}")
        return 0
    if args.companion:
        from resolve_time_tracker.ui import run_companion

        run_companion(args.db)
        return 0
    run_resolve_ui(
        args.db,
        resolve=globals().get("resolve"),
        fusion=globals().get("fusion"),
        bmd=globals().get("bmd"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
