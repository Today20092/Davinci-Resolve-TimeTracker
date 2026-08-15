import assert from "node:assert/strict"
import test from "node:test"

import { buildSupportReport } from "../electron/support-report.cjs"

test("builds a privacy-safe support report when the sidecar is unavailable", () => {
  const report = buildSupportReport({
    generatedAt: "2026-08-15T18:00:00.000Z",
    appVersion: "0.1.0",
    electronVersion: "43.1.0",
    platform: "win32 10.0.26100 x64",
    apiBase: "http://127.0.0.1:8765",
    launchMode: "source checkout",
    sidecar: {
      reachable: false,
      error: "connect ECONNREFUSED C:\\Users\\Alice\\secret",
      stderr: "Traceback at C:\\Users\\Alice\\tracker.py",
    },
    userHome: "C:\\Users\\Alice",
  })

  assert.match(report, /Sidecar reachable: no/)
  assert.match(
    report,
    /Sidecar error: connect ECONNREFUSED \[user-home\]\\secret/
  )
  assert.match(report, /Resolve bridge: unavailable/)
  assert.match(report, /Launch mode: source checkout/)
  assert.match(report, /Traceback at \[user-home\]\\tracker.py/)
  assert.doesNotMatch(report, /Alice/)
})

test("includes cached Resolve bridge diagnostics without project data", () => {
  const report = buildSupportReport({
    generatedAt: "2026-08-15T18:00:00.000Z",
    appVersion: "0.1.0",
    electronVersion: "43.1.0",
    platform: "win32 10.0.26100 x64",
    apiBase: "http://127.0.0.1:8765",
    launchMode: "packaged",
    sidecar: {
      reachable: true,
      diagnostics: {
        python_version: "3.13.7",
        platform: "Windows-11",
        resolve_bridge: "error",
        resolve_project_detected: false,
        scripting_module_available: true,
        scripting_module_loaded: true,
        resolve_product: "DaVinci Resolve Studio",
        resolve_version: "21.0.2.4",
        last_runtime_error: "DaVinci Resolve scripting bridge is not connected",
      },
    },
    userHome: "C:\\Users\\Alice",
  })

  assert.match(report, /Python: 3.13.7/)
  assert.match(report, /Resolve bridge: error/)
  assert.match(report, /Resolve project detected: no/)
  assert.match(report, /Scripting module loaded: yes/)
  assert.match(report, /Resolve: DaVinci Resolve Studio 21.0.2.4/)
  assert.match(report, /DaVinci Resolve scripting bridge is not connected/)
  assert.doesNotMatch(report, /Private Client Project/)
})
