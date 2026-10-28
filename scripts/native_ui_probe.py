"""Disposable UIManager experiment; run from Resolve, never the production launcher."""

import json
from html import escape
from importlib import import_module
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

WINDOW_ID = "com.resolve-time-tracker.NativeProbe"


def run_probe(resolve, fusion, bmd, *, report_path=None, menu_worker=False):
    ui = fusion.UIManager
    existing = ui.FindWindow(WINDOW_ID)
    if existing:
        existing.Show()
        existing.Raise()
        return {"reused_window": True, "window_id": WINDOW_ID}

    report_path = Path(
        report_path
        or Path(tempfile.mkdtemp(prefix="resolve-native-probe-")) / "probe.json"
    )
    capabilities = {}
    for name in ("sqlite3", "ctypes"):
        try:
            module = import_module(name)
            if name == "sqlite3":
                with module.connect(":memory:") as connection:
                    connection.execute("SELECT 1").fetchone()
            capabilities[name] = True
        except (ImportError, OSError):
            capabilities[name] = False
    report: dict[str, Any] = {
        "window_id": WINDOW_ID,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "sqlite_available": capabilities["sqlite3"],
        "ctypes_available": capabilities["ctypes"],
        "tracking_connected": False,
        "periodic_scheduler_verified": False,
        "periodic_scope": "menu_worker_noop_only" if menu_worker else "not_tested",
        "periodic_callbacks": [],
        "report_path": str(report_path),
        "hidden_count": 0,
        "stopped": False,
        "dispatch_callbacks": [],
        "dispatch_queued": 0,
        "phases": [],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def phase(name, operation):
        report["phase"] = f"before_{name}"
        report["phases"].append(report["phase"])
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        try:
            result = operation()
        except BaseException as error:
            report.update(
                phase="failed", failed_phase=name, error_type=type(error).__name__
            )
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise
        report["phase"] = f"after_{name}"
        report["phases"].append(report["phase"])
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return result

    dispatcher = phase("dispatcher", lambda: bmd.UIDispatcher(ui))
    layout = phase(
        "layout",
        lambda: ui.VGroup(
            [
                ui.Label(
                    {
                        "Text": "Feasibility probe only. No time is billed and no history is changed."
                    }
                ),
                ui.Label(
                    {
                        "Text": "Closing hides this probe. Re-run the menu entry to reopen; Stop ends it."
                    }
                ),
                ui.Button({"ID": "Hide", "Text": "Hide probe"}),
                ui.Button(
                    {"ID": "Dispatch", "Text": "Run 10 queued callbacks (not a timer)"}
                ),
                ui.Button({"ID": "Callback", "Text": "", "Hidden": True}),
                ui.Button({"ID": "Read", "Text": "Read Resolve once (idle only)"}),
                ui.Label({"ID": "Status", "Text": "Ready. Tracking is not connected."}),
                ui.Label({"Text": f"Report: {escape(str(report_path))}"}),
                ui.Button({"ID": "Stop", "Text": "Stop probe"}),
            ]
        ),
    )
    window = phase(
        "window",
        lambda: dispatcher.AddWindow(
            {
                "ID": WINDOW_ID,
                "WindowTitle": "Resolve native UI probe",
                "Geometry": [100, 100, 640, 240],
            },
            layout,
        ),
    )

    def hide(event):
        window.Hide()
        report["hidden_count"] += 1
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    dispatch_active = False
    queued_at = 0.0

    def stop(event):
        nonlocal dispatch_active
        dispatch_active = False
        report["stopped"] = True
        try:
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        finally:
            dispatcher.ExitLoop()

    def queue_next():
        nonlocal queued_at
        queued_at = time.monotonic()
        report["dispatch_queued"] += 1
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        ui.QueueEvent(window.Find("Callback"), "Clicked", {})

    def start_dispatch(event):
        nonlocal dispatch_active
        if dispatch_active or report["stopped"]:
            return
        dispatch_active = True
        report["dispatch_callbacks"] = []
        report["dispatch_queued"] = 0
        queue_next()

    def dispatch(event):
        nonlocal dispatch_active
        if not dispatch_active or report["stopped"]:
            return
        report["dispatch_callbacks"].append(
            {"latency_seconds": time.monotonic() - queued_at}
        )
        count = len(report["dispatch_callbacks"])
        window.Find(
            "Status"
        ).Text = (
            f"Queued callbacks: {count}/10. Periodic scheduling remains unverified."
        )
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if count < 10:
            queue_next()
        else:
            dispatch_active = False

    def read_resolve(event):
        started_at = time.monotonic()
        try:
            project = resolve.GetProjectManager().GetCurrentProject()
            page = resolve.GetCurrentPage()
            rendering = project.IsRenderingInProgress() if project else False
            name = project.GetName() if project else "No project"
            report["resolve_read"] = {
                "available": True,
                "project_open": project is not None,
                "page": page,
                "rendering": rendering,
                "duration_seconds": time.monotonic() - started_at,
            }
            window.Find(
                "Status"
            ).Text = f"{escape(str(name))} / {escape(str(page))}, rendering: {rendering}. Not tracking."
        except Exception as error:
            report["resolve_read"] = {
                "available": False,
                "error_type": type(error).__name__,
            }
            window.Find(
                "Status"
            ).Text = "Resolve read unavailable. No time is being billed."
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def handlers():
        window.On[WINDOW_ID].Close = hide
        window.On["Hide"].Clicked = hide
        window.On["Stop"].Clicked = stop
        window.On["Dispatch"].Clicked = start_dispatch
        window.On["Read"].Clicked = read_resolve
        window.On["Callback"].Clicked = dispatch

    def worker_loop():
        step_loop = getattr(dispatcher, "StepLoop", None)
        if not callable(step_loop):
            raise RuntimeError(
                "This host does not expose UIDispatcher.StepLoop(wait=False)."
            )
        started_at = time.monotonic()
        next_tick = started_at + 5.0
        start_dispatch(None)
        while not report["stopped"] and len(report["periodic_callbacks"]) < 3:
            step_loop(wait=False)
            if report["stopped"]:
                break
            now = time.monotonic()
            if now >= next_tick:
                report["periodic_callbacks"].append(
                    {"elapsed_seconds": now - started_at}
                )
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                next_tick = now + 5.0
            time.sleep(max(0.0, min(0.05, next_tick - time.monotonic())))
        if not report["stopped"]:
            report["periodic_scheduler_verified"] = True
            report["stop_reason"] = "periodic_limit"
            stop(None)

    phase("handlers", handlers)
    phase("show", window.Show)
    try:
        phase("worker_loop", worker_loop) if menu_worker else phase(
            "run_loop", dispatcher.RunLoop
        )
    finally:
        window.Hide()
    return report


def main(namespace):
    if not namespace.get("fusion") or not namespace.get("bmd"):
        raise RuntimeError(
            "Run this probe from Resolve's Python console or a native Scripts-menu entry."
        )
    return run_probe(
        namespace.get("resolve"),
        namespace["fusion"],
        namespace["bmd"],
        menu_worker=namespace.get("native_probe_menu_worker", False),
    )


if __name__ == "__main__":
    PROBE_RESULT = main(globals())
