import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from resolve_time_tracker.api import create_app, run_api
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.report_projection import seconds_on_local_date
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


class ApiTest(unittest.TestCase):
    def test_local_day_uses_dst_aware_midnight_boundaries(self):
        spring_forward = datetime(2026, 3, 8).date()
        with patch(
            "resolve_time_tracker.report_projection.time.mktime",
            side_effect=[
                datetime(2026, 3, 8, 5, tzinfo=timezone.utc).timestamp(),
                datetime(2026, 3, 9, 4, tzinfo=timezone.utc).timestamp(),
            ],
        ):
            seconds = seconds_on_local_date(
                datetime(2026, 3, 8, tzinfo=timezone.utc),
                datetime(2026, 3, 10, tzinfo=timezone.utc),
                spring_forward,
            )

        self.assertEqual(23 * 60 * 60, seconds)

    def test_dashboard_returns_current_project_read_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                engine = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [RuntimeSnapshot("Project A", "edit", False, 0, True)]
                    ),
                )
                engine.poll(utc(9))
                engine.close(utc(10))
                session = store.sessions()[0]
                store.update_session(
                    session["id"],
                    started_at=utc(9),
                    ended_at=utc(10),
                    page="Edit",
                    activity_category="playback",
                )
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "Color", False, 0, True),
                            RuntimeSnapshot("Project A", "Color", False, 0, True),
                            RuntimeSnapshot("Project A", "Color", False, 0, True),
                        ]
                    ),
                )
                tracker.poll(utc(11))
                now = [utc(11)]
                client = TestClient(
                    create_app(store, tracking_engine=tracker, now=lambda: now[0])
                )

                just_opened = client.get("/dashboard").json()
                now[0] = utc(12)
                dashboard = client.get("/dashboard").json()

        self.assertEqual(2, just_opened["current_project"]["totals"]["session_count"])
        self.assertEqual("Project A", dashboard["status"]["project"])
        self.assertEqual(1, len(dashboard["projects"]))
        self.assertEqual(1, len(dashboard["sessions"]))
        self.assertEqual(300, dashboard["settings"]["idle_timeout_seconds"])
        current = dashboard["current_project"]
        self.assertEqual(7200, current["totals"]["tracked_seconds"])
        self.assertEqual(2, current["totals"]["session_count"])
        self.assertEqual(
            {"editing": 3600, "playback": 3600, "rendering": 0},
            current["activity_totals"],
        )
        self.assertEqual("2026-01-02T10:00:00Z", current["last_activity"])
        self.assertEqual("Project A", dashboard["export_preview"]["project"])
        self.assertEqual(
            "01/02/2026 - 01/02/2026", dashboard["export_preview"]["date_range"]
        )

    def test_status_reads_tracking_published_by_the_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [RuntimeSnapshot("Project A", "edit", False, 0, True)]
                    ),
                )
                app = create_app(store, tracking_engine=tracker, now=lambda: utc(9))
                app.state.api.tracking_runtime.observe(utc(9))
                client = TestClient(app)

                status = client.get("/status").json()

        self.assertEqual("active", status["tracking_status"])

    def test_status_and_dashboard_read_published_runtime_state_without_observing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                provider = SequenceSnapshotProvider(
                    [
                        RuntimeSnapshot("Project A", "edit", False, 0, True),
                        RuntimeSnapshot("Project A", "edit", False, 0, True),
                    ]
                )
                tracker = TrackingEngine(store, snapshot_provider=provider)
                app = create_app(store, tracking_engine=tracker, now=lambda: utc(9))
                app.state.api.tracking_runtime.observe(utc(9))
                client = TestClient(app)

                client.get("/status")
                client.get("/dashboard")

        self.assertEqual(1, len(provider.snapshots))

    def test_status_marks_an_old_heartbeat_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [RuntimeSnapshot("Project A", "edit", False, 0, True)]
                    ),
                )
                tracker.poll(utc(9))
                client = TestClient(create_app(store, now=lambda: utc(9, 1)))

                status = client.get("/status").json()

        self.assertEqual("stale", status["tracking_status"])

    def test_status_reports_whether_time_is_actually_being_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", False, 301, True),
                            RuntimeSnapshot(None, None, False, 0, False),
                        ]
                    ),
                )
                app = create_app(store, tracking_engine=tracker, now=lambda: utc(9))
                client = TestClient(app)

                runtime = app.state.api.tracking_runtime
                runtime.observe(utc(9))
                active = client.post("/refresh").json()
                runtime.observe(utc(9, 5))
                idle = client.post("/refresh").json()
                runtime.observe(utc(9, 10))
                closed = client.post("/refresh").json()
                paused = client.post("/tracking/pause").json()
                error = client.post("/tracking/resume").json()

        self.assertEqual("active", active["tracking_status"])
        self.assertEqual("idle", idle["tracking_status"])
        self.assertEqual("resolve_closed", closed["tracking_status"])
        self.assertEqual("paused", paused["tracking_status"])
        self.assertEqual("resolve_closed", error["tracking_status"])

    def test_status_projects_sessions_settings_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                engine = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [RuntimeSnapshot("Project A", "edit", False, 0, True)]
                    ),
                )
                engine.poll(utc(9))
                engine.close(utc(10))
                store.set_idle_timeout_seconds(600)
                app = create_app(store, now=lambda: utc(11))
                client = TestClient(app)

                dashboard = client.get("/dashboard").json()
                status = dashboard["status"]
                projects = dashboard["projects"]
                sessions = dashboard["sessions"]
                settings = dashboard["settings"]
                csv_text = client.get("/export.csv").text
                pdf = client.post(
                    "/export.pdf",
                    json={"project_name": "Project A", "show_recent_activity": False},
                )

        self.assertEqual("paused", status["state"])
        self.assertEqual("none", status["project"])
        self.assertEqual(600, settings["idle_timeout_seconds"])
        self.assertEqual("Project A", projects[0]["project_name"])
        self.assertEqual(3600, projects[0]["duration_seconds"])
        self.assertEqual("Project A", sessions[0]["project_name"])
        self.assertEqual(3600, sessions[0]["duration_seconds"])
        self.assertIn("session_id,project_name,date", csv_text)
        self.assertIn("Project A", csv_text)
        self.assertEqual("application/pdf", pdf.headers["content-type"])
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertIn("Project-A-time-report.pdf", pdf.headers["content-disposition"])

    def test_pdf_export_rejects_unknown_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                app = create_app(store, now=lambda: utc(11))
                client = TestClient(app)

                response = client.post(
                    "/export.pdf", json={"project_name": "Missing Project"}
                )

        self.assertEqual(404, response.status_code)

    def test_tracking_controls_and_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                        ]
                    ),
                )
                current_time = [utc(9)]
                app = create_app(
                    store, tracking_engine=tracker, now=lambda: current_time[0]
                )
                client = TestClient(app)

                app.state.api.tracking_runtime.observe(current_time[0])
                refreshed = client.post("/refresh").json()
                current_time[0] = utc(9, 1)
                paused = client.post("/tracking/pause").json()
                resumed = client.post("/tracking/resume").json()
                settings = client.post(
                    "/settings", json={"idle_timeout_seconds": 900}
                ).json()
                session = client.get("/dashboard").json()["sessions"][0]
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
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                app = create_app(store, now=lambda: utc(9))
                client = TestClient(app)

                with client.stream("GET", "/events?once=true") as response:
                    body = response.read().decode()

        self.assertEqual(
            "text/event-stream; charset=utf-8", response.headers["content-type"]
        )
        self.assertIn("event: status", body)
        self.assertIn("event: dashboard", body)
        self.assertIn("data: {}", body)

    def test_heartbeat_event_does_not_rebuild_dashboard_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                tracker = TrackingEngine(
                    store,
                    snapshot_provider=SequenceSnapshotProvider(
                        [
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                            RuntimeSnapshot("Project A", "edit", False, 0, True),
                        ]
                    ),
                )
                app = create_app(store, tracking_engine=tracker, now=lambda: utc(9))
                runtime = app.state.api.tracking_runtime
                runtime.observe(utc(9))
                events = app.state.api.events(once=False, poll_interval_seconds=0)

                first = next(events)
                initial_dashboard = next(events)
                runtime.observe(utc(9, 10))
                heartbeat = next(events)

        self.assertIn("event: status", first)
        self.assertIn("event: dashboard", initial_dashboard)
        self.assertIn("event: status", heartbeat)
        self.assertNotIn("event: dashboard", heartbeat)

    def test_allows_frontend_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                app = create_app(store, now=lambda: utc(9))
                client = TestClient(app)

                response = client.get(
                    "/status", headers={"origin": "http://127.0.0.1:5173"}
                )

        self.assertEqual("*", response.headers["access-control-allow-origin"])

    def test_health_does_not_poll_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Mock()
            with SQLiteStore(
                Path(tmp) / "tracker.sqlite3", check_same_thread=False
            ) as store:
                response = TestClient(create_app(store, tracking_engine=engine)).get(
                    "/health"
                )

        self.assertEqual({"ok": True}, response.json())
        engine.poll.assert_not_called()

    def test_diagnostics_reports_runtime_state_without_polling_or_project_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Mock()
            engine.runtime_diagnostics = {
                "scripting_module_available": True,
                "scripting_module_loaded": True,
                "resolve_product": "DaVinci Resolve Studio",
                "resolve_version": "21.0.2.4",
            }
            engine.previous_snapshot = RuntimeSnapshot(
                project_name="Private Client Project",
                page="edit",
                is_rendering=False,
                idle_seconds=0,
                resolve_is_foreground=True,
            )
            with SQLiteStore(
                Path(tmp) / "private-client.sqlite3", check_same_thread=False
            ) as store:
                app = create_app(store, tracking_engine=engine)
                response = TestClient(app).get("/diagnostics")

        self.assertEqual(200, response.status_code)
        diagnostics = response.json()
        self.assertEqual("connected", diagnostics["resolve_bridge"])
        self.assertTrue(diagnostics["resolve_project_detected"])
        self.assertTrue(diagnostics["scripting_module_loaded"])
        self.assertEqual("DaVinci Resolve Studio", diagnostics["resolve_product"])
        self.assertEqual("21.0.2.4", diagnostics["resolve_version"])
        self.assertIsNone(diagnostics["last_runtime_error"])
        self.assertIn("python_version", diagnostics)
        self.assertIn("platform", diagnostics)
        self.assertNotIn("Private Client Project", response.text)
        self.assertNotIn("private-client.sqlite3", response.text)
        engine.poll.assert_not_called()

    def test_run_api_starts_tracking_api_with_resolve_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("resolve_time_tracker.api.TrackingEngine") as engine,
                patch("resolve_time_tracker.resolve_bridge.ResolveBridge") as bridge,
                patch("uvicorn.run") as run,
            ):
                run_api(Path(tmp) / "tracker.sqlite3")

        app = run.call_args.args[0]
        self.assertIs(app.state.api.tracking_engine, engine.return_value)
        engine.assert_called_once()
        bridge.assert_called_once()

    def test_run_api_can_start_database_api_without_resolve_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("uvicorn.run") as run:
                run_api(Path(tmp) / "tracker.sqlite3", enable_tracking=False)

        app = run.call_args.args[0]
        self.assertIsNone(app.state.api.tracking_engine)


if __name__ == "__main__":
    unittest.main()
