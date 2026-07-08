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
import runpy
from pathlib import Path


REPO_ROOT = Path(r"{repo_root}")
os.environ["RESOLVE_TIME_TRACKER_REPO"] = str(REPO_ROOT)
runpy.run_path(
    str(REPO_ROOT / "scripts" / "ResolveTimeTracker.py"),
    run_name="__main__",
    init_globals={{
        "resolve": globals().get("resolve"),
        "project": globals().get("project"),
        "fusion": globals().get("fusion"),
        "bmd": globals().get("bmd"),
    }},
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
