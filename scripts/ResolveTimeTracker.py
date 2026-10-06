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
    parser.add_argument("--tracked-launch", action="store_true")
    parser.add_argument("--dashboard-pid", type=int)
    parser.add_argument("--companion", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--version", action="store_true")
    args, _unknown = parser.parse_known_args(argv)
    return args


def _is_windows() -> bool:
    return os.name == "nt"


def run_electron_companion(
    db_path: Path, *, background: bool = False, dev: bool = False
) -> int:
    frontend_dir = REPO_ROOT / "frontend"
    env = os.environ.copy()
    python = Path(sys.executable)
    python_text = str(python)
    if _is_windows() and python_text.lower().endswith("pythonw.exe"):
        console_python = Path(f"{python_text[:-11]}python.exe")
        if console_python.is_file():
            python = console_python
    if dev:
        pnpm = shutil.which("pnpm.cmd" if _is_windows() else "pnpm")
        if pnpm is None:
            raise RuntimeError("pnpm is required for development mode")
        command = [pnpm, "run", "desktop:dev"]
        env["RESOLVE_TIME_TRACKER_DB"] = str(db_path)
    else:
        binary = (
            "electron.exe"
            if _is_windows()
            else "Electron.app/Contents/MacOS/Electron"
            if platform.system() == "Darwin"
            else "electron"
        )
        electron = frontend_dir / "node_modules" / "electron" / "dist" / binary
        if (
            not electron.is_file()
            or not (frontend_dir / "dist" / "index.html").is_file()
        ):
            raise RuntimeError("Dashboard is not built. Run the installer first.")
        command = [str(electron), str(frontend_dir), "--db", str(db_path)]
    if _python_has_sidecar_deps(python):
        env["RESOLVE_TIME_TRACKER_PYTHON"] = str(python)
        if not dev:
            command.extend(["--python", str(python)])
    if not dev:
        subprocess.Popen(
            command,
            cwd=frontend_dir,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if _is_windows()
            else 0,
            start_new_session=not _is_windows(),
        )
        return 0
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
    if args.background:
        # Old login shortcuts must not launch Resolve or leave a watcher behind.
        return 0
    if args.api or args.tracker or args.tracked_launch:
        from resolve_time_tracker.runtime_host import run_managed

        run_managed(
            args.db,
            tracked=args.tracked_launch or args.tracker,
            dashboard_pid=args.dashboard_pid,
            port=args.port,
        )
        return 0
    return run_electron_companion(args.db, background=args.background, dev=args.dev)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        if os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, str(exc), "Resolve Time Tracker", 0x10
            )
        else:
            print(str(exc), file=sys.stderr)
        raise SystemExit(1)
