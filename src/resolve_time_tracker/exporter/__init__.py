"""CSV export for Resolve Time Tracker."""

from __future__ import annotations

from typing import TextIO

from resolve_time_tracker.database import SQLiteStore


def export_sessions_csv(store: SQLiteStore, output: TextIO) -> None:
    store.write_csv(output)
