"""Resolve Scripts-menu probe that launches a short-lived companion poll."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(r"C:\Users\User\Documents\Davinci-Resolve-TimeTracker")
PYTHON_EXE = Path(r"C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe")
OUT_DIR = REPO_ROOT / ".scratch" / "resolve-menu-probe"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().isoformat(timespec="seconds")
    marker = OUT_DIR / "menu-script-started.json"
    stdout_path = OUT_DIR / "companion-stdout.json"
    stderr_path = OUT_DIR / "companion-stderr.txt"

    marker.write_text(
        json.dumps({"started_at": started_at, "python": str(PYTHON_EXE)}, indent=2),
        encoding="utf-8",
    )

    code = (
        "import sys; "
        f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r}); "
        "from probe_resolve_runtime import main; "
        "sys.argv=['probe_resolve_runtime.py','--samples','3','--interval','1']; "
        "raise SystemExit(main())"
    )
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
        "w",
        encoding="utf-8",
    ) as stderr:
        subprocess.Popen(
            [str(PYTHON_EXE), "-c", code],
            cwd=str(REPO_ROOT),
            stdout=stdout,
            stderr=stderr,
        )


if __name__ == "__main__":
    main()
