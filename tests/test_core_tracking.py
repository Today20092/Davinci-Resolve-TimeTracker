import csv
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.tracking_engine import RuntimeSnapshot, TrackingEngine


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


class SequenceSnapshotProvider:
    def __init__(self, snapshots: list[RuntimeSnapshot]):
        self.snapshots = list(snapshots)

    def snapshot(self) -> RuntimeSnapshot:
        if not self.snapshots:
            raise RuntimeError("No dry-run snapshots remain")
        return self.snapshots.pop(0)


class CoreTrackingTest(unittest.TestCase):
    def test_snapshots_create_only_billable_sessions(self):
        snapshots = [
            RuntimeSnapshot("Project A", None, False, 0, True),
            RuntimeSnapshot("Project A", "edit", False, 0, True),
            RuntimeSnapshot("Project A", "edit", False, 301, True),
            RuntimeSnapshot("Project A", "edit", False, 0, True),
            RuntimeSnapshot("Project A", "edit", False, 0, False),
            RuntimeSnapshot("Project A", "edit", False, 0, True),
            RuntimeSnapshot("Project A", "edit", True, 0, True),
            RuntimeSnapshot("Project A", "edit", True, 0, False),
            RuntimeSnapshot("Project A", "edit", False, 0, False),
            RuntimeSnapshot("Project A", "edit", False, 0, True),
            RuntimeSnapshot("Project B", "edit", False, 0, True),
            RuntimeSnapshot(None, "edit", False, 0, True),
        ]
        observed_at = [
            utc(9),
            utc(9, 5),
            utc(9, 30),
            utc(9, 45),
            utc(10),
            utc(10, 15),
            utc(10, 30),
            utc(10, 40),
            utc(11),
            utc(11, 15),
            utc(11, 30),
            utc(12),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = TrackingEngine(
                    store, snapshot_provider=SequenceSnapshotProvider(snapshots)
                )
                for timestamp in observed_at:
                    engine.poll(timestamp)
                rows = store.sessions()

        self.assertEqual(
            [
                (
                    "Project A",
                    "edit",
                    "editing",
                    9 * 3600,
                    9 * 3600 + 30 * 60,
                ),
                (
                    "Project A",
                    "edit",
                    "editing",
                    9 * 3600 + 45 * 60,
                    10 * 3600,
                ),
                (
                    "Project A",
                    "edit",
                    "editing",
                    10 * 3600 + 15 * 60,
                    10 * 3600 + 30 * 60,
                ),
                (
                    "Project A",
                    "edit",
                    "rendering",
                    10 * 3600 + 30 * 60,
                    11 * 3600,
                ),
                (
                    "Project A",
                    "edit",
                    "editing",
                    11 * 3600 + 15 * 60,
                    11 * 3600 + 30 * 60,
                ),
                (
                    "Project B",
                    "edit",
                    "editing",
                    11 * 3600 + 30 * 60,
                    12 * 3600,
                ),
            ],
            [
                (
                    row["project_name"],
                    row["page"],
                    row["activity_category"],
                    _seconds(row["started_at_utc"]),
                    _seconds(row["ended_at_utc"]),
                )
                for row in rows
            ],
        )

    def test_missing_page_reads_keep_one_last_known_page_session(self):
        snapshots = [
            RuntimeSnapshot("Project A", None, False, 0, True),
            RuntimeSnapshot("Project A", "edit", False, 0, True),
            RuntimeSnapshot("Project A", None, False, 0, True),
            RuntimeSnapshot("Project A", "edit", False, 0, True),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = TrackingEngine(
                    store, snapshot_provider=SequenceSnapshotProvider(snapshots)
                )
                engine.poll(utc(9))
                engine.poll(utc(9, 1))
                engine.poll(utc(9, 2))
                engine.poll(utc(9, 3))
                engine.close(utc(9, 4))
                rows = store.sessions()

        self.assertEqual(
            [("edit", 9 * 3600, 9 * 3600 + 4 * 60)],
            [
                (
                    row["page"],
                    _seconds(row["started_at_utc"]),
                    _seconds(row["ended_at_utc"]),
                )
                for row in rows
            ],
        )

    def test_store_repairs_historical_startup_unknown_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.sqlite3"
            with SQLiteStore(path) as store:
                project_id = store.upsert_project("Project A")
                store.open_active_session(
                    project_id=project_id,
                    started_at=utc(9),
                    page="Unknown",
                    activity_category="editing",
                )
                store.close_active_session(utc(9, 1))
                store.open_active_session(
                    project_id=project_id,
                    started_at=utc(9, 1),
                    page="edit",
                    activity_category="editing",
                )
                store.close_active_session(utc(9, 2))

            with SQLiteStore(path) as store:
                self.assertEqual(
                    ["edit", "edit"], [row["page"] for row in store.sessions()]
                )

    def test_blank_page_when_rendering_does_not_inherit_edit_page(self):
        snapshots = [
            RuntimeSnapshot("Project A", "edit", False, 0, True),
            RuntimeSnapshot("Project A", None, True, 0, True),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = TrackingEngine(
                    store, snapshot_provider=SequenceSnapshotProvider(snapshots)
                )
                engine.poll(utc(9))
                engine.poll(utc(9, 1))
                engine.close(utc(9, 2))
                rows = store.sessions()

        self.assertEqual(
            [("edit", "editing"), ("Unknown", "rendering")],
            [(row["page"], row["activity_category"]) for row in rows],
        )

    def test_project_and_page_transition_does_not_create_boundary_session(self):
        snapshots = [
            RuntimeSnapshot("Project A", "edit", False, 0, True),
            RuntimeSnapshot("Project B", None, False, 0, True),
            RuntimeSnapshot("Project B", "edit", False, 0, True),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = TrackingEngine(
                    store, snapshot_provider=SequenceSnapshotProvider(snapshots)
                )
                engine.poll(utc(9))
                engine.poll(utc(9, 1))
                engine.poll(utc(9, 2))
                engine.close(utc(9, 3))
                rows = store.sessions()

        self.assertEqual(
            [("Project A", "edit"), ("Project B", "edit")],
            [(row["project_name"], row["page"]) for row in rows],
        )

    def test_focus_and_project_transition_does_not_create_boundary_session(self):
        snapshots = [
            RuntimeSnapshot("Project A", "edit", False, 0, False),
            RuntimeSnapshot("Project B", "edit", False, 0, True),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = TrackingEngine(
                    store, snapshot_provider=SequenceSnapshotProvider(snapshots)
                )
                engine.poll(utc(9))
                engine.poll(utc(9, 1))
                engine.close(utc(9, 2))
                rows = store.sessions()

        self.assertEqual(
            [("Project B", "edit")],
            [(row["project_name"], row["page"]) for row in rows],
        )

    def test_engine_startup_recovers_at_the_last_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.sqlite3"
            with SQLiteStore(path) as store:
                engine = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                        ]
                    ),
                )
                engine.poll(utc(13))
                engine.poll(utc(13, 10))

            with SQLiteStore(path) as recovered:
                TrackingEngine(
                    recovered, snapshot_provider=SequenceSnapshotProvider([])
                )
                rows = recovered.sessions()

        self.assertEqual(1, len(rows))
        self.assertEqual(13 * 3600, _seconds(rows[0]["started_at_utc"]))
        self.assertEqual(13 * 3600 + 10 * 60, _seconds(rows[0]["ended_at_utc"]))

    def test_csv_export_contains_closed_sessions_with_durations(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3") as store:
                engine = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [RuntimeSnapshot("Project A", "edit", False, 0, True)]
                    ),
                )
                engine.poll(utc(14))
                engine.close(utc(15, 30))

                output = io.StringIO()
                store.write_csv(output)

        rows = list(csv.DictReader(io.StringIO(output.getvalue())))
        self.assertEqual(1, len(rows))
        self.assertEqual("Project A", rows[0]["project_name"])
        self.assertEqual("editing", rows[0]["activity_category"])
        self.assertEqual("5400", rows[0]["duration_seconds"])
        self.assertEqual("1.5000", rows[0]["duration_hours"])


def _seconds(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.hour * 3600 + parsed.minute * 60 + parsed.second
