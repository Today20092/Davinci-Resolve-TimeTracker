"""Install the Resolve Utility menu launcher for this checkout."""

from __future__ import annotations

import argparse
import os
import platform
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MENU_SCRIPT_NAME = "ResolveTimeTrackerMenu.py"
DEV_MENU_SCRIPT_NAME = "ResolveTimeTrackerDevMenu.py"
NATIVE_PROBE_SCRIPT_NAME = "ResolveTimeTrackerNativeProbe.py"


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


def launcher_text(repo_root: Path, *, dev: bool = False) -> str:
    mode = '"--companion", "--dev"' if dev else '"--tracked-launch"'
    return f'''"""Generated Resolve Utility launcher for Resolve Time Tracker."""
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(r"{repo_root}")
env = os.environ.copy()
env["RESOLVE_TIME_TRACKER_REPO"] = str(REPO_ROOT)
python = REPO_ROOT / ".venv" / ("Scripts/pythonw.exe" if os.name == "nt" else "bin/python")
if not python.is_file():
    raise RuntimeError("Run the Resolve Time Tracker installer first.")
subprocess.Popen(
    [str(python), str(REPO_ROOT / "scripts" / "ResolveTimeTracker.py"), {mode}],
    cwd=str(REPO_ROOT), env=env,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
    (utility_dir / DEV_MENU_SCRIPT_NAME).write_text(
        launcher_text(repo_root.resolve(), dev=True), encoding="utf-8"
    )
    return target


def native_probe_launcher_text(repo_root: Path) -> str:
    source = repo_root.resolve() / "scripts" / "native_ui_probe.py"
    return f'''"""Disposable native Resolve Time Tracker probe; generated opt-in entry."""
import json
import runpy
from pathlib import Path

_probe_globals = runpy.run_path(
    {str(source)!r},
    init_globals={{"resolve": resolve, "fusion": fusion, "bmd": bmd, "native_probe_menu_worker": True}},
    run_name="__main__",
)
_probe_result = _probe_globals.get("PROBE_RESULT", {{}})
if _probe_result.get("report_path"):
    _report_path = Path(_probe_result["report_path"])
    _report = json.loads(_report_path.read_text(encoding="utf-8"))
    _report["menu_invocation_returned"] = True
    _report_path.write_text(json.dumps(_report, indent=2), encoding="utf-8")
'''


def install_native_probe(
    *, repo_root: Path = REPO_ROOT, utility_dir: Path | None = None
) -> Path:
    utility_dir = default_utility_dir() if utility_dir is None else utility_dir
    target = utility_dir / NATIVE_PROBE_SCRIPT_NAME
    text = native_probe_launcher_text(repo_root)
    if target.exists() and target.read_text(encoding="utf-8") != text:
        raise FileExistsError(f"Refusing to replace a different script: {target}")
    utility_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def remove_native_probe(
    *, repo_root: Path = REPO_ROOT, utility_dir: Path | None = None
) -> bool:
    utility_dir = default_utility_dir() if utility_dir is None else utility_dir
    target = utility_dir / NATIVE_PROBE_SCRIPT_NAME
    if not target.exists():
        return False
    if target.read_text(encoding="utf-8") != native_probe_launcher_text(repo_root):
        raise ValueError(f"Refusing to remove a different script: {target}")
    target.unlink()
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--utility-dir", type=Path, default=default_utility_dir())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--native-probe",
        action="store_true",
        help="Install only the disposable native probe entry.",
    )
    mode.add_argument(
        "--remove-native-probe",
        action="store_true",
        help="Remove only this checkout's generated native probe entry.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.remove_native_probe:
        removed = remove_native_probe(utility_dir=args.utility_dir)
        print(
            "Native probe entry removed."
            if removed
            else "Native probe entry was not installed."
        )
        return 0
    installer = install_native_probe if args.native_probe else install_menu_script
    target = installer(utility_dir=args.utility_dir)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
