"""Phase 0 runtime probe for DaVinci Resolve Free on Windows."""

from __future__ import annotations

import ctypes
import argparse
import importlib.util
import json
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any


SCRIPTING_ROOT = Path(
    os.environ.get(
        "RESOLVE_SCRIPT_API",
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
    )
)
MODULE_PATH = SCRIPTING_ROOT / "Modules" / "DaVinciResolveScript.py"


def call(label: str, func: Any) -> Any:
    try:
        return func()
    except Exception as exc:  # Resolve's bridge can raise opaque runtime errors.
        return {"error": f"{type(exc).__name__}: {exc}"}


def load_resolve_bridge() -> Any:
    spec = importlib.util.spec_from_file_location("DaVinciResolveScript", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Resolve bridge from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return sys.modules.get("DaVinciResolveScript", module)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds() -> float | None:
    last_input = LASTINPUTINFO()
    last_input.cbSize = ctypes.sizeof(last_input)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input)):
        return None
    tick_count = ctypes.windll.kernel32.GetTickCount()
    elapsed_ms = (tick_count - last_input.dwTime) & 0xFFFFFFFF
    return round(elapsed_ms / 1000, 3)


def foreground_window() -> dict[str, Any]:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    title = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(hwnd, title, len(title))
    return {"hwnd": hwnd, "pid": pid.value, "title": title.value}


def timeline_snapshot(project: Any) -> dict[str, Any]:
    timeline = call("GetCurrentTimeline", project.GetCurrentTimeline)
    if isinstance(timeline, dict) and "error" in timeline:
        return {"timeline_error": timeline["error"]}
    if not timeline:
        return {"timeline": None}
    return {
        "timeline_name": call("Timeline.GetName", timeline.GetName),
        "timeline_id": call("Timeline.GetUniqueId", timeline.GetUniqueId),
        "timecode": call("Timeline.GetCurrentTimecode", timeline.GetCurrentTimecode),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--interval", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bridge = load_resolve_bridge()
    resolve = bridge.scriptapp("Resolve")
    if not resolve:
        print(json.dumps({"connected": False, "bridge": str(MODULE_PATH)}, indent=2))
        return 2

    project_manager = call("GetProjectManager", resolve.GetProjectManager)
    project = None
    if project_manager and not isinstance(project_manager, dict):
        project = call("GetCurrentProject", project_manager.GetCurrentProject)

    result: dict[str, Any] = {
        "connected": True,
        "python": sys.version,
        "bridge": str(MODULE_PATH),
        "resolve": {
            "product": call("GetProductName", resolve.GetProductName),
            "version": call("GetVersionString", resolve.GetVersionString),
            "page": call("GetCurrentPage", resolve.GetCurrentPage),
        },
        "windows": {
            "idle_seconds": idle_seconds(),
            "foreground": foreground_window(),
        },
        "project": None,
        "polls": [],
    }

    if project and not isinstance(project, dict):
        result["project"] = {
            "name": call("Project.GetName", project.GetName),
            "rendering": call("Project.IsRenderingInProgress", project.IsRenderingInProgress),
            **timeline_snapshot(project),
        }

        for _ in range(args.samples):
            result["polls"].append(
                {
                    "page": call("GetCurrentPage", resolve.GetCurrentPage),
                    "rendering": call(
                        "Project.IsRenderingInProgress",
                        project.IsRenderingInProgress,
                    ),
                    **timeline_snapshot(project),
                }
            )
            time.sleep(args.interval)

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
