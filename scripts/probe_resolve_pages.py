"""Probe Resolve page switching and page-specific timecode availability."""

from __future__ import annotations

import json
import time

from probe_resolve_runtime import call, load_resolve_bridge, timeline_snapshot


PAGES = ["media", "cut", "edit", "fusion", "color", "fairlight", "deliver"]


def main() -> int:
    bridge = load_resolve_bridge()
    resolve = bridge.scriptapp("Resolve")
    if not resolve:
        print(json.dumps({"connected": False}, indent=2))
        return 2

    project_manager = call("GetProjectManager", resolve.GetProjectManager)
    project = call("GetCurrentProject", project_manager.GetCurrentProject)
    result = {"connected": True, "pages": []}

    for page in PAGES:
        opened = call(f"OpenPage({page})", lambda page=page: resolve.OpenPage(page))
        time.sleep(0.5)
        result["pages"].append(
            {
                "requested": page,
                "opened": opened,
                "current": call("GetCurrentPage", resolve.GetCurrentPage),
                **timeline_snapshot(project),
            }
        )

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
