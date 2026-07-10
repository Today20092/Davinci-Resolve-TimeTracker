import assert from "node:assert/strict"
import test from "node:test"

import {
  currentProjectDashboard,
  displayPage,
  projectExportSummary,
} from "../src/lib/dashboard.ts"

test("current project dashboard includes saved and live project time", () => {
  const dashboard = currentProjectDashboard(
    [
      {
        id: 1,
        project_name: "Open Project",
        started_at_utc: "",
        ended_at_utc: "",
        duration_seconds: 120,
        duration: "0:02:00",
        page: "Edit",
        activity_category: "editing",
      },
      {
        id: 2,
        project_name: "Other Project",
        started_at_utc: "",
        ended_at_utc: "",
        duration_seconds: 999,
        duration: "0:16:39",
        page: "Color",
        activity_category: "editing",
      },
    ],
    {
      project: "Open Project",
      page: "Deliver",
      state: "rendering",
      active_elapsed_seconds: 30,
    }
  )

  assert.equal(dashboard.trackedSeconds, 150)
  assert.equal(dashboard.editingSeconds, 120)
  assert.equal(dashboard.renderingSeconds, 30)
  assert.equal(dashboard.sessionCount, 2)
  assert.equal(dashboard.recentSessions.length, 1)
  assert.equal(dashboard.lastActivity, "none")
  assert.deepEqual(dashboard.pageData, [
    { page: "Edit", seconds: 120 },
    { page: "Deliver", seconds: 30 },
  ])
})

test("rendering with no Resolve page is shown as render export time", () => {
  const dashboard = currentProjectDashboard(
    [
      {
        id: 1,
        project_name: "Food Photography",
        started_at_utc: "",
        ended_at_utc: "",
        duration_seconds: 90,
        duration: "0:01:30",
        page: "Unknown",
        activity_category: "rendering",
      },
    ],
    {
      project: "Food Photography",
      page: "none",
      state: "paused",
      active_elapsed_seconds: 0,
    }
  )

  assert.deepEqual(dashboard.pageData, [{ page: "Render/Export", seconds: 90 }])
  assert.equal(displayPage("Unknown", "editing"), "Unknown")
  assert.equal(displayPage("none", "rendering"), "Render/Export")
})

test("project export summary reports the current project date range", () => {
  const sessions = [
    {
      id: 1,
      project_name: "Food Photography",
      started_at_utc: "2026-07-01T12:00:00Z",
      ended_at_utc: "2026-07-01T13:00:00Z",
      duration_seconds: 3600,
      duration: "1:00:00",
      page: "Edit",
      activity_category: "editing",
    },
    {
      id: 2,
      project_name: "Other Project",
      started_at_utc: "2026-06-01T12:00:00Z",
      ended_at_utc: "2026-06-01T13:00:00Z",
      duration_seconds: 3600,
      duration: "1:00:00",
      page: "Color",
      activity_category: "editing",
    },
  ]
  const dashboard = currentProjectDashboard(sessions, {
    project: "Food Photography",
    page: "Edit",
    state: "paused",
    active_elapsed_seconds: 0,
  })

  assert.deepEqual(
    projectExportSummary(dashboard, sessions, new Date("2026-07-10T12:00:00Z")),
    {
      project: "Food Photography",
      generatedAt: "7/10/2026",
      dateRange: "7/1/2026 - 7/1/2026",
    }
  )
})
