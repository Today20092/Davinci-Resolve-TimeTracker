"""Tkinter companion UI for Resolve Time Tracker."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Iterator, TextIO

from resolve_time_tracker.activity_tracker import RuntimeTracker
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.resolve_bridge import ResolveBridge
from resolve_time_tracker.session_engine import SessionEngine


class CompanionApp:
    def __init__(
        self,
        store: SQLiteStore,
        *,
        root: Any | None = None,
        runtime_tracker: RuntimeTracker | None = None,
        poll_interval_ms: int = 5000,
    ):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.store = store
        self.runtime_tracker = runtime_tracker
        self.poll_interval_ms = poll_interval_ms
        self.last_runtime_error: str | None = None
        self.root = root or tk.Tk()
        self.root.title("Resolve Time Tracker")
        self.root.geometry("900x560")
        self.status_vars: dict[str, Any] = {}
        self.session_rows: dict[str, Any] = {}

        self._build()
        self.refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.runtime_tracker is not None:
            self.root.after(100, self._poll_runtime)

    def run(self) -> None:
        self.root.mainloop()

    def refresh(self) -> None:
        self._refresh_status()
        self._refresh_dashboard()
        self._refresh_projects()
        self._refresh_sessions()
        self._refresh_settings()

    def _build(self) -> None:
        ttk = self.ttk

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        status = ttk.Frame(outer)
        status.pack(fill="x", pady=(0, 10))
        ttk.Button(status, text="Refresh", command=self.refresh).pack(side="right")
        for label, key in [
            ("Resolve", "connection"),
            ("Project", "project"),
            ("Page", "page"),
            ("State", "state"),
            ("Heartbeat", "heartbeat"),
        ]:
            self.status_vars[key] = self.tk.StringVar(value="-")
            ttk.Label(status, text=f"{label}:").pack(side="left")
            ttk.Label(status, textvariable=self.status_vars[key], width=14).pack(
                side="left",
                padx=(2, 12),
            )

        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)

        self.dashboard = ttk.Frame(self.tabs, padding=10)
        self.projects = ttk.Frame(self.tabs, padding=10)
        self.sessions = ttk.Frame(self.tabs, padding=10)
        self.settings = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.dashboard, text="Dashboard")
        self.tabs.add(self.projects, text="Projects")
        self.tabs.add(self.sessions, text="Sessions")
        self.tabs.add(self.settings, text="Settings")

        self._build_dashboard()
        self._build_projects()
        self._build_sessions()
        self._build_settings()

    def _build_dashboard(self) -> None:
        self.dashboard_vars: dict[str, Any] = {}
        for row, (label, key) in enumerate(
            [
                ("Connection", "connection"),
                ("Project", "project"),
                ("Page", "page"),
                ("Tracking state", "state"),
                ("Active elapsed", "active_elapsed"),
                ("Last heartbeat", "heartbeat"),
            ]
        ):
            self.ttk.Label(self.dashboard, text=label).grid(row=row, column=0, sticky="w")
            self.dashboard_vars[key] = self.tk.StringVar(value="-")
            self.ttk.Label(self.dashboard, textvariable=self.dashboard_vars[key]).grid(
                row=row,
                column=1,
                sticky="w",
                padx=12,
            )

    def _build_projects(self) -> None:
        self.project_tree = self._tree(
            self.projects,
            ("project_name", "session_count", "duration", "last_session_date"),
            ("Project", "Sessions", "Total", "Last Session"),
        )

    def _build_sessions(self) -> None:
        self.session_tree = self._tree(
            self.sessions,
            (
                "project_name",
                "started_at_utc",
                "ended_at_utc",
                "duration",
                "page",
                "activity_category",
            ),
            ("Project", "Start", "End", "Duration", "Page", "Activity"),
        )
        buttons = self.ttk.Frame(self.sessions)
        buttons.pack(fill="x", pady=(8, 0))
        self.ttk.Button(buttons, text="Edit Selected", command=self._edit_selected_session).pack(
            side="left",
        )
        self.ttk.Button(buttons, text="Export CSV...", command=self._export_csv).pack(
            side="left",
            padx=8,
        )

    def _build_settings(self) -> None:
        self.idle_minutes = self.tk.IntVar(value=5)
        self.ttk.Label(self.settings, text="Idle timeout minutes").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.ttk.Spinbox(
            self.settings,
            from_=1,
            to=120,
            textvariable=self.idle_minutes,
            width=8,
        ).grid(row=0, column=1, sticky="w", padx=12)
        self.ttk.Button(self.settings, text="Save", command=self._save_settings).grid(
            row=0,
            column=2,
            sticky="w",
        )
        self.ttk.Label(self.settings, text="Data file").grid(row=1, column=0, sticky="w")
        self.ttk.Label(self.settings, text=str(self.store.path)).grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="w",
            padx=12,
        )

    def _tree(self, parent: Any, columns: tuple[str, ...], headings: tuple[str, ...]) -> Any:
        tree = self.ttk.Treeview(parent, columns=columns, show="headings", height=14)
        for column, heading in zip(columns, headings, strict=True):
            tree.heading(column, text=heading)
            tree.column(column, width=130, anchor="w")
        tree.pack(fill="both", expand=True)
        return tree

    def _refresh_status(self) -> None:
        status = self._status()
        if self.runtime_tracker is not None and self.runtime_tracker.previous_snapshot is not None:
            snapshot = self.runtime_tracker.previous_snapshot
            status["connection"] = "connected"
            status["project"] = snapshot.project_name or "none"
            status["page"] = snapshot.page or "none"
        if self.last_runtime_error:
            status["connection"] = "error"
            status["heartbeat"] = self.last_runtime_error
        for key, value in status.items():
            if key in self.status_vars:
                self.status_vars[key].set(value)
            if key in getattr(self, "dashboard_vars", {}):
                self.dashboard_vars[key].set(value)

    def _status(self) -> dict[str, str]:
        active = self.store.active_session_summary()
        if active is None:
            return {
                "connection": "connected",
                "project": "none",
                "page": "none",
                "state": "paused",
                "active_elapsed": "0:00:00",
                "heartbeat": "none",
            }

        started = _parse_utc(active["started_at_utc"])
        elapsed = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
        return {
            "connection": "connected",
            "project": active["project_name"],
            "page": active["page"],
            "state": active["activity_category"],
            "active_elapsed": _duration(elapsed),
            "heartbeat": active["last_heartbeat_at_utc"] or "none",
        }

    def _refresh_dashboard(self) -> None:
        self._refresh_status()

    def _refresh_projects(self) -> None:
        self.project_tree.delete(*self.project_tree.get_children())
        for row in self.store.project_summaries():
            self.project_tree.insert(
                "",
                "end",
                values=(
                    row["project_name"],
                    row["session_count"],
                    _duration(row["duration_seconds"]),
                    row["last_session_date"] or "-",
                ),
            )

    def _refresh_sessions(self) -> None:
        self.session_rows = {}
        self.session_tree.delete(*self.session_tree.get_children())
        for row in self.store.sessions():
            duration = _session_duration(row)
            iid = str(row["id"])
            self.session_rows[iid] = row
            self.session_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    row["project_name"],
                    row["started_at_utc"],
                    row["ended_at_utc"],
                    _duration(duration),
                    row["page"],
                    row["activity_category"],
                ),
            )

    def _refresh_settings(self) -> None:
        self.idle_minutes.set(max(1, round(self.store.idle_timeout_seconds() / 60)))

    def _edit_selected_session(self) -> None:
        selected = self.session_tree.selection()
        if not selected:
            return
        row = self.session_rows[selected[0]]
        editor = self.tk.Toplevel(self.root)
        editor.title("Edit Session")
        fields = {
            "started_at_utc": self.tk.StringVar(value=row["started_at_utc"]),
            "ended_at_utc": self.tk.StringVar(value=row["ended_at_utc"]),
            "page": self.tk.StringVar(value=row["page"]),
            "activity_category": self.tk.StringVar(value=row["activity_category"]),
        }
        for index, (key, value) in enumerate(fields.items()):
            self.ttk.Label(editor, text=key).grid(row=index, column=0, sticky="w", padx=8, pady=4)
            self.ttk.Entry(editor, textvariable=value, width=32).grid(
                row=index,
                column=1,
                sticky="w",
                padx=8,
                pady=4,
            )

        def save() -> None:
            from tkinter import messagebox

            try:
                self.store.update_session(
                    row["id"],
                    started_at=_parse_utc(fields["started_at_utc"].get()),
                    ended_at=_parse_utc(fields["ended_at_utc"].get()),
                    page=fields["page"].get(),
                    activity_category=fields["activity_category"].get(),
                )
            except ValueError as exc:
                messagebox.showerror("Invalid session", str(exc), parent=editor)
                return
            editor.destroy()
            self.refresh()

        self.ttk.Button(editor, text="Save", command=save).grid(row=4, column=0, padx=8, pady=8)
        self.ttk.Button(editor, text="Cancel", command=editor.destroy).grid(
            row=4,
            column=1,
            sticky="w",
            padx=8,
            pady=8,
        )

    def _export_csv(self) -> None:
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        with Path(path).open("w", newline="", encoding="utf-8") as output:
            self.store.write_csv(output)

    def _save_settings(self) -> None:
        from tkinter import messagebox

        try:
            self.store.set_idle_timeout_seconds(int(self.idle_minutes.get()) * 60)
        except ValueError as exc:
            messagebox.showerror("Invalid setting", str(exc), parent=self.root)
            return
        self.refresh()

    def _poll_runtime(self) -> None:
        if self.runtime_tracker is None:
            return
        try:
            poll_runtime_once(self.store, self.runtime_tracker, datetime.now(timezone.utc))
            self.last_runtime_error = None
        except Exception as exc:
            self.last_runtime_error = f"{type(exc).__name__}: {exc}"
        self.refresh()
        self.root.after(self.poll_interval_ms, self._poll_runtime)

    def _on_close(self) -> None:
        if self.runtime_tracker is not None:
            close_runtime_once(self.runtime_tracker, datetime.now(timezone.utc))
        self.root.destroy()


def run_companion(db_path: str | Path) -> None:
    with companion_instance_lock(db_path):
        with SQLiteStore(db_path) as store:
            prepare_companion_store(store)
            runtime_tracker = RuntimeTracker(
                SessionEngine(store),
                idle_timeout_seconds=store.idle_timeout_seconds(),
                snapshot_provider=ResolveBridge(),
            )
            CompanionApp(store, runtime_tracker=runtime_tracker).run()


def companion_lock_path(db_path: str | Path) -> Path:
    return Path(db_path).with_suffix(".lock")


@contextmanager
def companion_instance_lock(db_path: str | Path) -> Iterator[None]:
    lock_path = companion_lock_path(db_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+", encoding="utf-8")
    locked = False
    try:
        _lock_file(lock_file)
        locked = True
        yield
    finally:
        if locked:
            _unlock_file(lock_file)
        lock_file.close()


def _lock_file(lock_file: TextIO) -> None:
    lock_file.seek(0)
    lock_file.write("1")
    lock_file.flush()
    lock_file.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise RuntimeError("Resolve Time Tracker is already running") from exc


def _unlock_file(lock_file: TextIO) -> None:
    lock_file.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def poll_runtime_once(
    store: SQLiteStore,
    runtime_tracker: RuntimeTracker,
    observed_at: datetime,
) -> None:
    runtime_tracker.idle_timeout_seconds = store.idle_timeout_seconds()
    runtime_tracker.poll(observed_at)


def prepare_companion_store(store: SQLiteStore) -> None:
    store.recover_active_session()


def close_runtime_once(runtime_tracker: RuntimeTracker, observed_at: datetime) -> None:
    runtime_tracker.engine.resolve_closed(observed_at)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _session_duration(row: Any) -> int:
    started = _parse_utc(row["started_at_utc"])
    ended = _parse_utc(row["ended_at_utc"])
    return max(0, int((ended - started).total_seconds()))


def _duration(seconds: int) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"
