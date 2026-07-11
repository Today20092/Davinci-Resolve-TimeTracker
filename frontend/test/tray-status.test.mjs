import assert from "node:assert/strict"
import { createRequire } from "node:module"
import test from "node:test"

const require = createRequire(import.meta.url)
const { trayPresentation } = require("../electron/tray-status.cjs")

test("tray presentation makes tracking certainty visible", () => {
  assert.deepEqual(
    trayPresentation({
      tracking_status: "active",
      project: "Client Film",
      active_elapsed: "1:02:03",
    }),
    {
      color: "#22c55e",
      label: "Tracking active",
      tooltip: "Tracking active — Client Film — 1:02:03",
    }
  )
  assert.equal(trayPresentation({ tracking_status: "idle" }).color, "#eab308")
  assert.equal(trayPresentation({ tracking_status: "paused" }).color, "#eab308")
  assert.equal(
    trayPresentation({ tracking_status: "resolve_closed" }).color,
    "#9ca3af"
  )
  assert.equal(trayPresentation({ tracking_status: "error" }).color, "#ef4444")
  assert.equal(trayPresentation({ tracking_status: "stale" }).color, "#ef4444")
  assert.equal(trayPresentation(null).color, "#ef4444")
})
