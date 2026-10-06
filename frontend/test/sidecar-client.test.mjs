import assert from "node:assert/strict"
import test from "node:test"

import {
  advanceActiveElapsed,
  createSidecarClient,
  formatSidecarError,
} from "../src/lib/api.ts"

const responses = {
  "/status": { connection: "connected" },
  "/dashboard": {
    status: { connection: "connected" },
    settings: { idle_timeout_seconds: 300, idle_timeout_minutes: 5 },
    projects: [{ project_name: "Demo" }],
    sessions: [{ id: 7, project_name: "Demo" }],
    current_project: null,
    export_preview: null,
  },
}

test("loads dashboard data through the sidecar client interface", async () => {
  const requested = []
  const client = createSidecarClient({
    baseUrl: "http://sidecar.test",
    fetch: async (url) => {
      const path = new URL(url).pathname
      requested.push(path)
      return Response.json(responses[path])
    },
  })

  const dashboard = await client.loadDashboard()

  assert.deepEqual(dashboard, responses["/dashboard"])
  assert.deepEqual(requested, ["/dashboard"])
})

test("performs tracking and edit commands through domain methods", async () => {
  const requests = []
  const client = createSidecarClient({
    baseUrl: "http://sidecar.test",
    fetch: async (url, init = {}) => {
      requests.push({
        path: new URL(url).pathname,
        method: init.method ?? "GET",
        body: init.body ? JSON.parse(init.body) : null,
      })
      return Response.json(
        init.method === "POST" ? {} : responses[new URL(url).pathname]
      )
    },
  })
  const update = {
    started_at_utc: "2026-01-02T09:00:00Z",
    ended_at_utc: "2026-01-02T10:00:00Z",
    page: "Edit",
    activity_category: "editing",
  }

  await client.refresh()
  await client.setTracking(false)
  await client.setTracking(true)
  await client.updateSettings(600)
  await client.updateSession(7, update)

  assert.deepEqual(
    requests.filter((request) => request.method === "POST"),
    [
      { path: "/refresh", method: "POST", body: null },
      { path: "/tracking/pause", method: "POST", body: null },
      { path: "/tracking/resume", method: "POST", body: null },
      {
        path: "/settings",
        method: "POST",
        body: { idle_timeout_seconds: 600 },
      },
      { path: "/sessions/7", method: "POST", body: update },
    ]
  )
})

test("reloads the dashboard after a command", async () => {
  const requested = []
  const client = createSidecarClient({
    baseUrl: "http://sidecar.test",
    fetch: async (url, init = {}) => {
      const path = new URL(url).pathname
      requested.push(path)
      return Response.json(init.method === "POST" ? {} : responses[path])
    },
  })

  const dashboard = await client.refresh()

  assert.deepEqual(dashboard, responses["/dashboard"])
  assert.deepEqual(requested, ["/refresh", "/dashboard"])
})

test("uses published status without rebuilding the dashboard", async () => {
  let source
  class FakeEventSource {
    constructor(url) {
      this.url = url
      this.listeners = new Map()
      this.closed = false
      source = this
    }

    addEventListener(name, listener) {
      this.listeners.set(name, listener)
    }

    close() {
      this.closed = true
    }
  }
  let publishStatus
  const statusPublished = new Promise((resolve) => {
    publishStatus = resolve
  })
  const errors = []
  const client = createSidecarClient({
    baseUrl: "http://sidecar.test",
    eventSource: FakeEventSource,
    fetch: async (url) => Response.json(responses[new URL(url).pathname]),
  })

  const stop = client.watchDashboard({
    onDashboard: () => assert.fail("heartbeat must not rebuild the dashboard"),
    onStatus: publishStatus,
    onError: (error) => errors.push(formatSidecarError(error)),
  })
  source.listeners.get("status")({ data: JSON.stringify(responses["/status"]) })
  const status = await statusPublished
  source.onerror()
  stop()

  assert.equal(source.url, "http://sidecar.test/events")
  assert.deepEqual(status, responses["/status"])
  assert.deepEqual(errors, ["Waiting for the sidecar API"])
  assert.equal(source.closed, true)
})

test("reloads the dashboard only after a dashboard event", async () => {
  let source
  class FakeEventSource {
    constructor() {
      this.listeners = new Map()
      source = this
    }

    addEventListener(name, listener) {
      this.listeners.set(name, listener)
    }

    close() {}
  }
  const requested = []
  let publishDashboard
  const dashboardPublished = new Promise((resolve) => {
    publishDashboard = resolve
  })
  const client = createSidecarClient({
    baseUrl: "http://sidecar.test",
    eventSource: FakeEventSource,
    fetch: async (url) => {
      const path = new URL(url).pathname
      requested.push(path)
      return Response.json(responses[path])
    },
  })

  client.watchDashboard({
    onDashboard: publishDashboard,
    onStatus: () => {},
    onError: () => {},
  })
  source.listeners.get("dashboard")({ data: "{}" })

  assert.deepEqual(await dashboardPublished, responses["/dashboard"])
  assert.deepEqual(requested, ["/dashboard"])
})

test("exposes the CSV export location", async () => {
  const client = createSidecarClient({
    baseUrl: "http://sidecar.test",
    fetch: async (url) => {
      const path = new URL(url).pathname
      return Response.json(responses[path])
    },
  })

  assert.equal(client.csvExportUrl(), "http://sidecar.test/export.csv")
})

test("exports a configured PDF report", async () => {
  const requests = []
  const client = createSidecarClient({
    baseUrl: "http://sidecar.test",
    fetch: async (url, init = {}) => {
      requests.push({
        path: new URL(url).pathname,
        method: init.method,
        body: JSON.parse(init.body),
      })
      return new Response(new Blob(["pdf"]))
    },
  })
  const options = {
    project_name: "Demo",
    show_totals: true,
    show_page_chart: false,
    show_activity_chart: true,
    show_recent_activity: false,
  }

  const blob = await client.exportPdf(options)

  assert.equal(blob.size, 3)
  assert.deepEqual(requests, [
    { path: "/export.pdf", method: "POST", body: options },
  ])
})

test("normalizes sidecar errors for presentation", () => {
  assert.equal(
    formatSidecarError(new Error("sidecar failed")),
    "sidecar failed"
  )
  assert.equal(formatSidecarError("sidecar failed"), "sidecar failed")
})

test("advances an active session timer locally", () => {
  assert.deepEqual(
    advanceActiveElapsed({
      ...responses["/status"],
      tracking_status: "active",
      active_elapsed_seconds: 62,
      active_elapsed: "0:01:02",
    }),
    {
      ...responses["/status"],
      tracking_status: "active",
      active_elapsed_seconds: 63,
      active_elapsed: "0:01:03",
    }
  )
})
