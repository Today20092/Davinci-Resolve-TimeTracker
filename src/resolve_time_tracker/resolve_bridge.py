"""Boundary for DaVinci Resolve scripting API access."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from resolve_time_tracker.activity_tracker import RuntimeSnapshot, default_activity_probe


SCRIPTING_ROOT = Path(
    os.environ.get(
        "RESOLVE_SCRIPT_API",
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
    )
)
MODULE_PATH = SCRIPTING_ROOT / "Modules" / "DaVinciResolveScript.py"


class ResolveBridge:
    def __init__(
        self,
        module_path: str | Path = MODULE_PATH,
        activity_probe: Any | None = None,
        resolve_object: Any | None = None,
    ):
        self.module_path = Path(module_path)
        self.activity_probe = activity_probe or default_activity_probe()
        self._resolve_object = resolve_object
        self._module: Any | None = None

    def snapshot(self) -> RuntimeSnapshot:
        resolve = self.resolve()
        project = self._current_project(resolve)
        page = _call(resolve.GetCurrentPage)

        project_name = None
        is_rendering = False
        timeline_name = None
        timeline_id = None
        timecode = None

        if project is not None:
            project_name = _call(project.GetName)
            is_rendering = bool(_call(project.IsRenderingInProgress) or False)
            timeline = _call(project.GetCurrentTimeline)
            if timeline is not None:
                timeline_name = _call(timeline.GetName)
                timeline_id = _call(timeline.GetUniqueId)
                timecode = _call(timeline.GetCurrentTimecode)

        return RuntimeSnapshot(
            project_name=project_name,
            page=page,
            is_rendering=is_rendering,
            idle_seconds=self.activity_probe.idle_seconds(),
            resolve_is_foreground=self.activity_probe.resolve_is_foreground(),
            timeline_name=timeline_name,
            timeline_id=timeline_id,
            timecode=timecode,
        )

    def resolve(self) -> Any:
        if self._resolve_object is not None:
            return self._resolve_object
        module = self._load_module()
        resolve = module.scriptapp("Resolve")
        if not resolve:
            raise RuntimeError("DaVinci Resolve scripting bridge is not connected")
        return resolve

    def _load_module(self) -> Any:
        if self._module is not None:
            return self._module
        spec = importlib.util.spec_from_file_location("DaVinciResolveScript", self.module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load Resolve bridge from {self.module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._module = sys.modules.get("DaVinciResolveScript", module)
        return self._module

    def _current_project(self, resolve: Any) -> Any | None:
        project_manager = _call(resolve.GetProjectManager)
        if project_manager is None:
            return None
        return _call(project_manager.GetCurrentProject)


def _call(func: Any) -> Any | None:
    try:
        return func()
    except Exception:
        return None
