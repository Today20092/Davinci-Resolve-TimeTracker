"""Install the Resolve Utility menu launcher for this checkout."""

from __future__ import annotations

import argparse
import os
import platform
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MENU_SCRIPT_NAME = "ResolveTimeTrackerMenu.py"


def default_utility_dir() -> Path:
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


def launcher_text(repo_root: Path) -> str:
    return f'''"""Generated Resolve Utility launcher for Resolve Time Tracker."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(r"{repo_root}")
env = os.environ.copy()
env["RESOLVE_TIME_TRACKER_REPO"] = str(REPO_ROOT)

def valid_python(candidate):
    try:
        return subprocess.run(
            [str(candidate), "-c", "import sys; raise SystemExit(sys.version_info >= (3, 14))"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
    except OSError:
        return False

def find_uv():
    candidates = [
        "uv.exe" if os.name == "nt" else "uv",
        Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv"),
        Path(os.environ.get("APPDATA", "")) / "uv" / "uv.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "uv" / "uv.exe",
        Path.home() / ".cargo" / "bin" / ("uv.exe" if os.name == "nt" else "uv"),
    ]
    for candidate in candidates:
        try:
            if subprocess.run(
                [str(candidate), "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode == 0:
                return str(candidate)
        except OSError:
            pass
    return None

if os.name == "nt":
    candidates = [
        REPO_ROOT / ".venv" / "Scripts" / "pythonw.exe",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
    ]
else:
    candidates = [
        REPO_ROOT / ".venv" / "bin" / "pythonw",
        REPO_ROOT / ".venv" / "bin" / "python",
    ]
python = next((candidate for candidate in candidates if candidate.exists() and valid_python(candidate)), None)
command = None
if python is not None:
    command = [str(python), str(REPO_ROOT / "scripts" / "ResolveTimeTracker.py"), "--companion"]
else:
    uv = find_uv()
    if uv is None:
        raise RuntimeError(f"Run uv sync --python 3.13 before launching Resolve Time Tracker: {{REPO_ROOT / '.venv'}}")
    command = [
        uv,
        "run",
        "--python",
        "3.13",
        "scripts/ResolveTimeTracker.py",
        "--companion",
    ]
subprocess.Popen(
    command,
    cwd=str(REPO_ROOT),
    env=env,
)
'''


def install_menu_script(
    *,
    repo_root: Path = REPO_ROOT,
    utility_dir: Path | None = None,
) -> Path:
    if utility_dir is None:
        utility_dir = default_utility_dir()
    utility_dir.mkdir(parents=True, exist_ok=True)
    target = utility_dir / MENU_SCRIPT_NAME
    target.write_text(launcher_text(repo_root.resolve()), encoding="utf-8")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--utility-dir", type=Path, default=default_utility_dir())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = install_menu_script(utility_dir=args.utility_dir)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
