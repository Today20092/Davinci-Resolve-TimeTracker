"""Install the Resolve Utility menu launcher for this checkout."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UTILITY_DIR = (
    Path(os.environ.get("APPDATA", Path.home()))
    / "Blackmagic Design"
    / "DaVinci Resolve"
    / "Support"
    / "Fusion"
    / "Scripts"
    / "Utility"
)
MENU_SCRIPT_NAME = "ResolveTimeTrackerMenu.py"


def launcher_text(repo_root: Path) -> str:
    return f'''"""Generated Resolve Utility launcher for Resolve Time Tracker."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


REPO_ROOT = Path(r"{repo_root}")
os.environ["RESOLVE_TIME_TRACKER_REPO"] = str(REPO_ROOT)
runpy.run_path(str(REPO_ROOT / "scripts" / "ResolveTimeTrackerMenu.py"), run_name="__main__")
'''


def install_menu_script(
    *,
    repo_root: Path = REPO_ROOT,
    utility_dir: Path = DEFAULT_UTILITY_DIR,
) -> Path:
    utility_dir.mkdir(parents=True, exist_ok=True)
    target = utility_dir / MENU_SCRIPT_NAME
    target.write_text(launcher_text(repo_root.resolve()), encoding="utf-8")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--utility-dir", type=Path, default=DEFAULT_UTILITY_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = install_menu_script(utility_dir=args.utility_dir)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
