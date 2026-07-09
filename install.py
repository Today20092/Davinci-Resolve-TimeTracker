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


def ensure_source(source_dir: Path, repo_url: str) -> None:
    if is_source_checkout(source_dir):
        return
    if source_dir.exists():
        raise RuntimeError(
            f"{source_dir} exists but is not a Resolve Time Tracker checkout"
        )
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to clone Resolve Time Tracker source")
    source_dir.parent.mkdir(parents=True, exist_ok=True)
    run([git, "clone", repo_url, str(source_dir)])


def uv_command() -> list[str] | None:
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
    python = venv_python(source_dir)
    if python is None:
        run([*uv, "sync"], cwd=source_dir)
        python = venv_python(source_dir)
    if python is None:
        raise RuntimeError(
            f"uv sync did not create a virtualenv Python under {source_dir / '.venv'}"
        )
    command = [str(python), "scripts/install_resolve_menu.py"]
    if utility_dir is not None:
        command.extend(["--utility-dir", str(utility_dir)])
    output = run(command, cwd=source_dir)
    target = Path(output.strip().splitlines()[-1])
    verify_menu_script(target, source_dir)
    return target


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = source_dir_for(Path(__file__), args.source_dir)
    ensure_source(source_dir, args.repo_url)
    uv = ensure_uv()
    target = install_menu(source_dir, uv, args.utility_dir)
    print(f"Source: {source_dir}")
    print(f"Resolve menu script: {target}")
    print("Open Resolve, then run Workspace > Scripts > ResolveTimeTrackerMenu")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stdout:
            print(exc.stdout, file=sys.stderr)
        raise SystemExit(1)
