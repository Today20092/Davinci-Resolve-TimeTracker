"""Probe Resolve render-state transitions with a tiny local render job."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from probe_resolve_runtime import call, load_resolve_bridge


OUTPUT_DIR = Path(".scratch/probe-renders").resolve()


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    bridge = load_resolve_bridge()
    resolve = bridge.scriptapp("Resolve")
    if not resolve:
        print(json.dumps({"connected": False}, indent=2))
        return 2

    project_manager = call("GetProjectManager", resolve.GetProjectManager)
    project = call("GetCurrentProject", project_manager.GetCurrentProject)
    timeline = call("GetCurrentTimeline", project.GetCurrentTimeline)
    render_name = f"rtt_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    setup: dict[str, Any] = {
        "TargetDir": str(OUTPUT_DIR),
        "CustomName": render_name,
        "SelectAllFrames": False,
        "MarkIn": 0,
        "MarkOut": 30,
        "ExportVideo": True,
        "ExportAudio": False,
    }

    result: dict[str, Any] = {
        "connected": True,
        "page": call("GetCurrentPage", resolve.GetCurrentPage),
        "project": call("Project.GetName", project.GetName),
        "timeline": call("Timeline.GetName", timeline.GetName),
        "current_format_codec": call(
            "Project.GetCurrentRenderFormatAndCodec",
            project.GetCurrentRenderFormatAndCodec,
        ),
        "setup": setup,
        "set_render_settings": call(
            "Project.SetRenderSettings",
            lambda: project.SetRenderSettings(setup),
        ),
        "job_id": None,
        "start_rendering": None,
        "polls": [],
        "cleanup": {},
    }

    job_id = call("Project.AddRenderJob", project.AddRenderJob)
    result["job_id"] = job_id
    if not job_id or isinstance(job_id, dict):
        print(json.dumps(result, indent=2, default=str))
        return 1

    try:
        result["start_rendering"] = call(
            "Project.StartRendering",
            lambda: project.StartRendering([job_id], False),
        )
        for _ in range(60):
            rendering = call("Project.IsRenderingInProgress", project.IsRenderingInProgress)
            status = call("Project.GetRenderJobStatus", lambda: project.GetRenderJobStatus(job_id))
            result["polls"].append({"rendering": rendering, "status": status})
            if rendering is False and len(result["polls"]) > 1:
                break
            time.sleep(0.5)
    finally:
        if call("Project.IsRenderingInProgress", project.IsRenderingInProgress):
            result["cleanup"]["stop_rendering"] = call(
                "Project.StopRendering",
                project.StopRendering,
            )
        result["cleanup"]["delete_render_job"] = call(
            "Project.DeleteRenderJob",
            lambda: project.DeleteRenderJob(job_id),
        )

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
