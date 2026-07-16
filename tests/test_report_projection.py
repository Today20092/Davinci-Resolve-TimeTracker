from datetime import datetime, timezone

from resolve_time_tracker.report_projection import project_report


def test_project_report_concentrates_closed_and_active_session_rules():
    sessions = [
        {
            "project_name": "Project A",
            "started_at_utc": "2026-01-02T09:00:00+00:00",
            "ended_at_utc": "2026-01-02T10:00:00+00:00",
            "duration_seconds": 3600,
            "duration": "01:00:00",
            "page": "Edit",
            "activity_category": "playback",
        },
        {
            "project_name": "Project B",
            "started_at_utc": "2026-01-02T08:00:00+00:00",
            "ended_at_utc": "2026-01-02T09:00:00+00:00",
            "duration_seconds": 3600,
            "duration": "01:00:00",
            "page": "Color",
            "activity_category": "editing",
        },
    ]
    active = {
        "project_name": "Project A",
        "started_at_utc": "2026-01-02T10:00:00+00:00",
        "page": "Deliver",
        "activity_category": "rendering",
    }

    report = project_report(
        "Project A",
        sessions,
        session_count=1,
        active_session=active,
        active_seconds=1800,
        now=datetime(2026, 1, 2, 10, 30, tzinfo=timezone.utc),
    )

    assert report.tracked_seconds == 5400
    assert report.today_seconds == 5400
    assert report.session_count == 1
    assert report.activity_totals == {
        "editing": 0,
        "playback": 3600,
        "rendering": 1800,
    }
    assert report.page_totals == [("Edit", 3600), ("Deliver", 1800)]
    assert report.date_range == "01/02/2026 - 01/02/2026"
    assert report.recent_sessions == sessions[:1]


def test_project_report_dates_live_only_active_work():
    report = project_report(
        "Project A",
        [],
        active_session={
            "project_name": "Project A",
            "started_at_utc": "2026-01-02T23:30:00+00:00",
            "page": "Edit",
            "activity_category": "editing",
        },
        active_seconds=25200,
        now=datetime(2026, 1, 3, 6, 30, tzinfo=timezone.utc),
    )

    assert report.date_range == "01/02/2026 - 01/03/2026"
