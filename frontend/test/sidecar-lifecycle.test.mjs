import assert from "node:assert/strict"
import { createRequire } from "node:module"
import test from "node:test"

const require = createRequire(import.meta.url)
const { restartSidecar } = require("../electron/sidecar-lifecycle.cjs")

test("restarts a dead sidecar unless the app is quitting", async () => {
  let starts = 0
  let completions = 0
  const restart = (running, quitting = false) =>
    restartSidecar({
      apiIsRunning: async () => running,
      isQuitting: () => quitting,
      onComplete: () => (completions += 1),
      startSidecar: () => (starts += 1),
    })()

  await restart(false)
  await restart(true)
  await restart(false, true)

  assert.equal(starts, 1)
  assert.equal(completions, 3)
})
