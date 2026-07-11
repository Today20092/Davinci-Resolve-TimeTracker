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
    parser.add_argument("--tracker", action="store_true")
    parser.add_argument("--companion", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--version", action="store_true")
    args, _unknown = parser.parse_known_args(argv)
    return args


def _is_windows() -> bool:
    return os.name == "nt"


def run_electron_companion(
    db_path: Path, *, background: bool = False, dev: bool = False
) -> int:
    frontend_dir = REPO_ROOT / "frontend"
    npm = shutil.which("npm.cmd" if _is_windows() else "npm")
    if npm is None:
        raise RuntimeError("npm is required to launch the Electron companion")
    env = os.environ.copy()
    python = Path(sys.executable)
    python_text = str(python)
    if _is_windows() and python_text.lower().endswith("pythonw.exe"):
        console_python = Path(f"{python_text[:-11]}python.exe")
        if console_python.is_file():
            python = console_python
    command = [npm, "run", "desktop:dev" if dev else "desktop"]
    if dev:
        env["RESOLVE_TIME_TRACKER_DB"] = str(db_path)
    else:
        command.extend(["--", "--db", str(db_path)])
    if background:
        command.append("--background")
    if _python_has_sidecar_deps(python):
        env["RESOLVE_TIME_TRACKER_PYTHON"] = str(python)
        if not dev:
            command.extend(["--python", str(python)])
    return subprocess.run(
        command,
        cwd=frontend_dir,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if _is_windows()
        else 0,
        check=False,
    ).returncode


def _python_has_sidecar_deps(python: Path) -> bool:
    try:
        return (
            subprocess.run(
                [
                    str(python),
                    "-c",
                    "import sys; assert sys.version_info < (3, 14); import fastapi, reportlab, uvicorn",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"Resolve Time Tracker {__version__}")
        return 0
    if args.api or args.tracker:
        from resolve_time_tracker.api import run_api

        run_api(args.db, host=args.host, port=args.port)
        return 0
    return run_electron_companion(args.db, background=args.background, dev=args.dev)


if __name__ == "__main__":
    raise SystemExit(main())
