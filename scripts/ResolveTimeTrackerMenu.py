"""DaVinci Resolve Utility menu launcher for Resolve Time Tracker."""

from __future__ import annotations

import os
import runpy
from pathlib import Path


REPO_ROOT = Path(os.environ.get("RESOLVE_TIME_TRACKER_REPO", Path(__file__).resolve().parents[1]))
ENTRYPOINT = REPO_ROOT / "scripts" / "ResolveTimeTracker.py"


def main() -> None:
    runpy.run_path(
        str(ENTRYPOINT),
        run_name="__main__",
        init_globals={
            "resolve": globals().get("resolve"),
            "project": globals().get("project"),
            "fusion": globals().get("fusion"),
            "bmd": globals().get("bmd"),
        },
    )


if __name__ == "__main__":
    main()
