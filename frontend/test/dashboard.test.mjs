import assert from "node:assert/strict"
import test from "node:test"

import { currentProjectDashboard } from "../src/lib/dashboard.ts"

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
