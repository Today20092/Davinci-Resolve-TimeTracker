"""Cross-platform installer for Resolve Time Tracker."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


REPO_URL = "https://github.com/Today20092/Davinci-Resolve-TimeTracker.git"
PYTHON_VERSION = "3.13"
STARTUP_SCRIPT_NAME = "ResolveTimeTrackerBackground.cmd"


def is_source_checkout(path: Path) -> bool:
    return (
        (path / "pyproject.toml").is_file()
        and (path / "scripts" / "ResolveTimeTracker.py").is_file()
        and (path / "scripts" / "install_resolve_menu.py").is_file()
    )


def default_source_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "ResolveTimeTracker" / "source"


def source_dir_for(installer_path: Path, requested: Path | None) -> Path:
    if requested is not None:
        return requested.expanduser().resolve()
    here = installer_path.resolve().parent
    if is_source_checkout(here):
        return here
    return default_source_dir()


def ensure_source(source_dir: Path, repo_url: str, update: bool) -> None:
    if is_source_checkout(source_dir):
        print(f"[3/7] Using existing source checkout: {source_dir}", flush=True)
        git = shutil.which("git")
        if update and git is not None and (source_dir / ".git").is_dir():
            print("[3/7] Updating source checkout...", flush=True)
            run([git, "pull", "--ff-only"], cwd=source_dir)
        return
    if source_dir.exists():
        raise RuntimeError(
            f"{source_dir} exists but is not a Resolve Time Tracker checkout"
        )
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to clone Resolve Time Tracker source")
    source_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"[3/7] Cloning source to {source_dir}", flush=True)
    run([git, "clone", repo_url, str(source_dir)])


def uv_command() -> list[str] | None:
    configured = os.environ.get("RESOLVE_TIME_TRACKER_UV")
    if configured:
        return [configured]
    uv = shutil.which("uv")
    if uv is not None:
        return [uv]
    try:
        run([sys.executable, "-m", "uv", "--version"])
    except (subprocess.CalledProcessError, OSError):
        return None
    return [sys.executable, "-m", "uv"]


def ensure_uv() -> list[str]:
    command = uv_command()
    if command is not None:
        print(f"[4/7] Using uv: {' '.join(command)}", flush=True)
        return command
    raise RuntimeError(
        "uv is required. Run install.ps1 on Windows or install.sh on macOS/Linux."
    )


def venv_python(source_dir: Path) -> Path | None:
    if os.name == "nt":
        candidates = [
            source_dir / ".venv" / "Scripts" / "python.exe",
            source_dir / ".venv" / "Scripts" / "pythonw.exe",
        ]
    else:
        candidates = [
            source_dir / ".venv" / "bin" / "python",
            source_dir / ".venv" / "bin" / "pythonw",
        ]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def install_menu(source_dir: Path, uv: list[str], utility_dir: Path | None) -> Path:
    print("[6/7] Installing Python dependencies...", flush=True)
    run([*uv, "sync", "--python", PYTHON_VERSION], cwd=source_dir)
    python = venv_python(source_dir)
    if python is None:
        raise RuntimeError(
            f"uv sync did not create a virtualenv Python under {source_dir / '.venv'}"
        )
    command = [
        *uv,
        "run",
        "--python",
        PYTHON_VERSION,
        "scripts/install_resolve_menu.py",
    ]
    if utility_dir is not None:
        command.extend(["--utility-dir", str(utility_dir)])
    print("[7/7] Installing DaVinci Resolve menu script...", flush=True)
    output = run(command, cwd=source_dir)
    target = Path(output.strip().splitlines()[-1])
    verify_menu_script(target, source_dir)
    return target


def windows_startup_dir() -> Path:
    return (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def install_startup(source_dir: Path, python: Path | None = None) -> Path:
    if platform.system() != "Windows":
        raise RuntimeError(
            "Background auto-start is currently only installed on Windows"
        )
    if python is None and os.name == "nt":
        pythonw = source_dir / ".venv" / "Scripts" / "pythonw.exe"
        python = pythonw if pythonw.exists() else None
    python = python or venv_python(source_dir)
    if python is None:
        raise RuntimeError(
            f"uv sync did not create a virtualenv Python under {source_dir / '.venv'}"
        )
    startup_dir = windows_startup_dir()
    startup_dir.mkdir(parents=True, exist_ok=True)
    target = startup_dir / STARTUP_SCRIPT_NAME
    target.write_text(
        "\n".join(
            [
                "@echo off",
                f'cd /d "{source_dir.resolve()}"',
                (
                    f'start "" /min "{python}" '
                    f'"{source_dir.resolve() / "scripts" / "ResolveTimeTracker.py"}" '
                    "--tracker"
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return target


def choose_startup_mode(*, default: str = "manual") -> str:
    if not sys.stdin.isatty():
        return default
    print("How should Resolve Time Tracker start?", flush=True)
    print("  [1] Manual only (default)", flush=True)
    print("  [2] Start with my computer", flush=True)
    answer = input("Choose 1 or 2: ").strip()
    return "auto" if answer == "2" else "manual"


def install_frontend(source_dir: Path) -> None:
    frontend_dir = source_dir / "frontend"
    if not (frontend_dir / "package.json").is_file():
        print("[5/7] No frontend package found; skipping Electron companion.", flush=True)
        return
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise RuntimeError("npm is required to install the Electron companion")
    print("[5/7] Installing and building Electron companion...", flush=True)
    run([npm, "ci"], cwd=frontend_dir)
    run([npm, "run", "build"], cwd=frontend_dir)


def verify_menu_script(target: Path, source_dir: Path) -> None:
    if not target.is_file():
        raise RuntimeError(f"Resolve menu script was not created: {target}")
    text = target.read_text(encoding="utf-8")
    if str(source_dir.resolve()) not in text or "--companion" not in text:
        raise RuntimeError(
            f"Resolve menu script does not point at this checkout: {target}"
        )


def run(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Resolve Time Tracker for DaVinci Resolve"
    )
    parser.add_argument(
        "--source-dir", type=Path, help="Existing or new Resolve Time Tracker checkout"
    )
    parser.add_argument("--repo-url", default=REPO_URL)
    parser.add_argument(
        "--utility-dir", type=Path, help="Override Resolve Scripts/Utility folder"
    )
    parser.add_argument(
        "--startup",
        choices=["ask", "manual", "auto"],
        default="ask",
        help="Startup behavior; ask defaults to manual in non-interactive installs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    installer_path = Path(__file__)
    source_dir = source_dir_for(installer_path, args.source_dir)
    update_source = args.source_dir is None and not is_source_checkout(
        installer_path.resolve().parent
    )
    print("Plan:", flush=True)
    print(f"  - Source checkout: {source_dir}", flush=True)
    print("  - Install/update frontend dependencies if the companion app is present.", flush=True)
    print("  - Install the DaVinci Resolve Scripts menu entry.", flush=True)
    print("  - Ask before enabling background auto-start.", flush=True)
    print("", flush=True)
    ensure_source(source_dir, args.repo_url, update_source)
    uv = ensure_uv()
    install_frontend(source_dir)
    target = install_menu(source_dir, uv, args.utility_dir)
    startup_mode = choose_startup_mode() if args.startup == "ask" else args.startup
    startup_target = None
    if startup_mode == "auto":
        startup_target = install_startup(source_dir)
    print(f"Source: {source_dir}")
    print(f"Resolve menu script: {target}")
    if startup_target is None:
        print("Startup: manual only")
        print("Open Resolve, then run Workspace > Scripts > ResolveTimeTrackerMenu")
    else:
        print(f"Startup: {startup_target}")
        print("Resolve Time Tracker will start with your computer.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stdout:
            print(exc.stdout, file=sys.stderr)
        raise SystemExit(1)
