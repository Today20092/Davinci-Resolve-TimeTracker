"""Companion process entry point launched from Resolve's Scripts menu."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from resolve_time_tracker import __version__
from resolve_time_tracker.ui import run_companion


def default_db_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return root / "ResolveTimeTracker" / "tracker.sqlite3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=default_db_path())
    parser.add_argument("--version", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.version:
        print(f"Resolve Time Tracker {__version__}")
        return 0
    run_companion(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
