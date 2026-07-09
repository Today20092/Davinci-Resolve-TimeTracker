"""Resolve-native entry point launched from Resolve's Scripts menu."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
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
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--companion", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--version", action="store_true")
    args, _unknown = parser.parse_known_args(argv)
    return args


def run_electron_companion(db_path: Path) -> int:
    frontend_dir = REPO_ROOT / "frontend"
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise RuntimeError("npm is required to launch the Electron companion")
    env = os.environ.copy()
    env["RESOLVE_TIME_TRACKER_PYTHON"] = sys.executable
    return subprocess.run(
        [npm, "run", "desktop", "--", "--db", str(db_path)],
        cwd=frontend_dir,
        env=env,
        check=False,
    ).returncode


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"Resolve Time Tracker {__version__}")
        return 0
    if args.api:
        from resolve_time_tracker.api import run_api

        run_api(args.db, host=args.host, port=args.port)
        return 0
    if args.companion:
        return run_electron_companion(args.db)
    run_resolve_ui(
        args.db,
        resolve=globals().get("resolve"),
        fusion=globals().get("fusion"),
        bmd=globals().get("bmd"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
