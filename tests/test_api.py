import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from resolve_time_tracker.activity_tracker import RuntimeSnapshot, RuntimeTracker
from resolve_time_tracker.api import create_app
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.session_engine import SessionEngine


def utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


class SequenceSnapshotProvider:
    def __init__(self, snapshots: list[RuntimeSnapshot]):
        self.snapshots = list(snapshots)

    def snapshot(self) -> RuntimeSnapshot:
        if not self.snapshots:
            raise RuntimeError("No dry-run snapshots remain")
        return self.snapshots.pop(0)


class ApiTest(unittest.TestCase):
    def test_status_projects_sessions_settings_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3", check_same_thread=False) as store:
                engine = SessionEngine(store)
                engine.project_changed(utc(9), "Project A")
                engine.resolve_closed(utc(10))
                store.set_idle_timeout_seconds(600)
                app = create_app(store, now=lambda: utc(11))
                client = TestClient(app)

                status = client.get("/status").json()
                projects = client.get("/projects").json()
                sessions = client.get("/sessions").json()
                settings = client.get("/settings").json()
                csv_text = client.get("/export.csv").text

        self.assertEqual("paused", status["state"])
        self.assertEqual("none", status["project"])
        self.assertEqual(600, settings["idle_timeout_seconds"])
        self.assertEqual("Project A", projects[0]["project_name"])
        self.assertEqual(3600, projects[0]["duration_seconds"])
        self.assertEqual("Project A", sessions[0]["project_name"])
        self.assertEqual(3600, sessions[0]["duration_seconds"])
        self.assertIn("session_id,project_name,date", csv_text)
        self.assertIn("Project A", csv_text)

    def test_tracking_controls_and_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3", check_same_thread=False) as store:
                tracker = RuntimeTracker(
                    SessionEngine(store),
                    idle_timeout_seconds=300,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                        ]
                    ),
                )
                app = create_app(store, runtime_tracker=tracker, now=lambda: utc(9))
                client = TestClient(app)

                refreshed = client.post("/refresh").json()
                paused = client.post("/tracking/pause").json()
                resumed = client.post("/tracking/resume").json()
                settings = client.post(
                    "/settings", json={"idle_timeout_seconds": 900}
                ).json()
                session = client.get("/sessions").json()[0]
                edited = client.post(
                    f"/sessions/{session['id']}",
                    json={
                        "started_at_utc": "2026-01-02T09:00:00Z",
                        "ended_at_utc": "2026-01-02T09:30:00Z",
                        "page": "color",
                        "activity_category": "rendering",
                    },
                ).json()

        self.assertEqual("Project A", refreshed["project"])
        self.assertEqual("manual pause", paused["state"])
        self.assertEqual("Project A", resumed["project"])
        self.assertEqual(900, settings["idle_timeout_seconds"])
        self.assertEqual("color", edited["page"])
        self.assertEqual("rendering", edited["activity_category"])

    def test_events_stream_status_as_sse(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(Path(tmp) / "tracker.sqlite3", check_same_thread=False) as store:
                app = create_app(store, now=lambda: utc(9))
                client = TestClient(app)

                with client.stream("GET", "/events?once=true") as response:
                    body = response.read().decode()

        self.assertEqual("text/event-stream; charset=utf-8", response.headers["content-type"])
        self.assertIn("event: status", body)
        self.assertIn('"state":"paused"', body)


if __name__ == "__main__":
    unittest.main()
