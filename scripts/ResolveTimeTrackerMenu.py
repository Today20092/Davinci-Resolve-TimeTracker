"""DaVinci Resolve Utility menu launcher for Resolve Time Tracker."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(os.environ.get("RESOLVE_TIME_TRACKER_REPO", Path(__file__).resolve().parents[1]))
ENTRYPOINT = REPO_ROOT / "scripts" / "ResolveTimeTracker.py"


def python_command() -> list[str]:
    configured = os.environ.get("RESOLVE_TIME_TRACKER_PYTHON")
    if configured:
        return [configured]
    py_launcher = shutil.which("py")
    if py_launcher:
        return [py_launcher, "-3.13"]
    return [sys.executable]


def launch_command() -> list[str]:
    return [*python_command(), str(ENTRYPOINT)]


def main() -> None:
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        launch_command(),
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


if __name__ == "__main__":
    main()
