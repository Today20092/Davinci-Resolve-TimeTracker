"""Resolve UIManager window for Resolve Time Tracker."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from resolve_time_tracker.activity_tracker import RuntimeTracker
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.resolve_bridge import ResolveBridge
from resolve_time_tracker.session_engine import SessionEngine


POLL_SECONDS = 2


def run_resolve_ui(
    db_path: str | Path,
    *,
    resolve: Any | None = None,
    fusion: Any | None = None,
    bmd: Any | None = None,
) -> None:
    if resolve is None and bmd is not None and hasattr(bmd, "scriptapp"):
        resolve = bmd.scriptapp("Resolve")
    if fusion is None and resolve is not None:
        fusion = resolve.Fusion()
    if fusion is None or bmd is None:
        raise RuntimeError("Resolve UIManager is unavailable. Run this from Resolve's Scripts menu.")

    ui = _ui_manager(fusion)
    dispatcher = bmd.UIDispatcher(ui)
    db_path = Path(db_path)
    store = SQLiteStore(db_path, check_same_thread=False)
    store.recover_active_session()
    tracker = RuntimeTracker(
        SessionEngine(store),
        idle_timeout_seconds=store.idle_timeout_seconds(),
        snapshot_provider=ResolveBridge(resolve_object=resolve),
    )

    win = dispatcher.AddWindow(
        {
            "ID": "ResolveTimeTracker",
            "WindowTitle": "Resolve Time Tracker",
            "Geometry": [100, 100, 520, 300],
        },
        ui.VGroup(
            [
                ui.Label({"ID": "Status", "Text": "Starting..."}),
                ui.Label({"ID": "Project", "Text": "Project: -"}),
                ui.Label({"ID": "Page", "Text": "Page: -"}),
                ui.Label({"ID": "Activity", "Text": "Activity: -"}),
                ui.Label({"ID": "Heartbeat", "Text": "Heartbeat: -"}),
                ui.Label({"ID": "Database", "Text": f"Database: {db_path}"}),
                ui.HGroup(
                    [
                        ui.Button({"ID": "Refresh", "Text": "Refresh"}),
                        ui.Button({"ID": "Export", "Text": "Export CSV"}),
                        ui.Button({"ID": "Close", "Text": "Close"}),
                    ]
                ),
            ]
        ),
    )
    items = win.GetItems()
    stopped = threading.Event()
    lock = threading.Lock()

    def set_text(item_id: str, text: str) -> None:
        items[item_id].Text = text

    def poll_once() -> None:
        with lock:
            snapshot = tracker.poll(datetime.now(timezone.utc))
            active = store.active_session_summary()
        state = "tracking" if active is not None else "paused"
        if snapshot.is_rendering:
            state = "rendering"
        set_text("Status", f"Status: {state}")
        set_text("Project", f"Project: {snapshot.project_name or '-'}")
        set_text("Page", f"Page: {snapshot.page or 'Unknown'}")
        set_text("Activity", f"Activity: {'rendering' if snapshot.is_rendering else 'editing'}")
        set_text("Heartbeat", f"Heartbeat: {datetime.now().strftime('%H:%M:%S')}")

    def export_csv() -> None:
        output_path = db_path.with_suffix(".csv")
        with lock:
            with output_path.open("w", encoding="utf-8", newline="") as output:
                store.write_csv(output)
        set_text("Status", f"Exported: {output_path}")

    def close() -> None:
        stopped.set()
        with lock:
            tracker.engine.resolve_closed(datetime.now(timezone.utc))
            store.close()
        dispatcher.ExitLoop(0)

    def polling_loop() -> None:
        while not stopped.is_set():
            try:
                poll_once()
            except Exception as exc:
                set_text("Status", f"Resolve connection waiting: {exc}")
            stopped.wait(POLL_SECONDS)

    win.On.ResolveTimeTracker.Close = lambda ev: close()
    win.On.Refresh.Clicked = lambda ev: poll_once()
    win.On.Export.Clicked = lambda ev: export_csv()
    win.On.Close.Clicked = lambda ev: close()

    thread = threading.Thread(target=polling_loop, daemon=True)
    thread.start()
    win.Show()
    dispatcher.RunLoop()
    stopped.set()


def _ui_manager(fusion: Any) -> Any:
    manager = fusion.UIManager
    return manager() if callable(manager) else manager
