"""PDF report generation for tracked Resolve project time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from resolve_time_tracker.report_projection import ProjectReport


@dataclass(frozen=True)
class PdfExportOptions:
    show_totals: bool = True
    show_page_chart: bool = True
    show_activity_chart: bool = True
    show_recent_activity: bool = True


def build_project_pdf(
    *,
    project_name: str,
    report: ProjectReport,
    options: PdfExportOptions,
    generated_at: datetime | None = None,
) -> bytes:
    generated = generated_at or datetime.now(timezone.utc)
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"{project_name} Time Report",
    )
    styles = getSampleStyleSheet()
    story: list[Any] = [
        Paragraph("Resolve Time Report", styles["BodyText"]),
        Paragraph(project_name, styles["Title"]),
        Paragraph(
            f"Generated {generated.date().isoformat()} | {report.date_range}",
            styles["BodyText"],
        ),
        Spacer(1, 0.2 * inch),
    ]

    if options.show_totals:
        story.extend(
            [
                _section("Summary", styles),
                _table(
                    [
                        ["Total tracked", _duration(report.tracked_seconds)],
                        ["Editing", _duration(report.activity_totals["editing"])],
                        ["Rendering", _duration(report.activity_totals["rendering"])],
                        ["Tracked sessions", str(report.session_count)],
                    ],
                    widths=[2.2 * inch, 4.1 * inch],
                ),
                Spacer(1, 0.18 * inch),
            ]
        )

    if options.show_page_chart:
        story.extend(
            [
                _section("Time by page", styles),
                _bar_table(report.page_totals),
                Spacer(1, 0.18 * inch),
            ]
        )

    if options.show_activity_chart:
        story.extend(
            [
                _section("Activity mix", styles),
                _bar_table(
                    sorted(
                        (
                            item
                            for item in report.activity_totals.items()
                            if item[1] > 0
                        ),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                ),
                Spacer(1, 0.18 * inch),
            ]
        )

    if options.show_recent_activity:
        rows = [["Start", "Duration", "Page", "Activity"]]
        for session in report.recent_sessions[:8]:
            rows.append(
                [
                    _short_datetime(session["started_at_utc"]),
                    session["duration"],
                    session["page"],
                    session["activity_category"],
                ]
            )
        story.extend([_section("Recent page activity", styles), _table(rows)])

    doc.build(story)
    return output.getvalue()


def _bar_table(rows: list[tuple[str, int]]) -> Table:
    if not rows:
        return _table([["No tracked time yet"]])
    chart = _bar_chart(rows)
    data = [["Item", "Time"], *[[label, _duration(seconds)] for label, seconds in rows]]
    return Table(
        [[_table(data, widths=[1.7 * inch, 1.0 * inch]), chart]],
        colWidths=[2.9 * inch, 3.4 * inch],
        hAlign="LEFT",
    )


def _bar_chart(rows: list[tuple[str, int]]) -> Drawing:
    values = [seconds for _, seconds in rows]
    chart = HorizontalBarChart()
    chart.x = 92
    chart.y = 12
    chart.width = 230
    chart.height = max(86, len(rows) * 18)
    chart.data = [values]
    chart.categoryAxis.categoryNames = [label[:18] for label, _ in rows]
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.1
    chart.valueAxis.visibleLabels = False
    chart.valueAxis.visibleTicks = False
    chart.valueAxis.visibleAxis = False
    chart.bars[0].fillColor = colors.HexColor("#38bdf8")
    chart.bars.strokeColor = colors.white
    drawing = Drawing(3.4 * inch, chart.height + 24)
    drawing.add(chart)
    return drawing


def _table(rows: list[list[str]], widths: list[float] | None = None) -> Table:
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#18181b")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e4e4e7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _section(title: str, styles: Any) -> Paragraph:
    return Paragraph(title, styles["Heading2"])


def _short_datetime(value: str) -> str:
    return _parse_utc(value).strftime("%Y-%m-%d %H:%M")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _duration(seconds: int) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"
