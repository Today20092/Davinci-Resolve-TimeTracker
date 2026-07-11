import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { createRequire } from "node:module"
import test from "node:test"

const require = createRequire(import.meta.url)
const { startupEnabled, setStartupEnabled, startupPath } = require(
  "../electron/startup-settings.cjs"
)

test("startup preference manages the installer launcher", () => {
  const appData = fs.mkdtempSync(path.join(os.tmpdir(), "tracker-startup-"))
  const repoRoot = path.join(appData, "Resolve Time Tracker")
  fs.mkdirSync(path.join(repoRoot, ".venv", "Scripts"), { recursive: true })
  fs.mkdirSync(path.join(repoRoot, "scripts"))
  fs.writeFileSync(path.join(repoRoot, ".venv", "Scripts", "pythonw.exe"), "")
  fs.writeFileSync(path.join(repoRoot, "scripts", "ResolveTimeTracker.py"), "")

  assert.equal(startupEnabled(appData), false)
  setStartupEnabled({ appData, repoRoot, enabled: true })
  assert.equal(startupEnabled(appData), true)
  assert.match(fs.readFileSync(startupPath(appData), "utf8"), /--background/)

  setStartupEnabled({ appData, repoRoot, enabled: false })
  assert.equal(startupEnabled(appData), false)
})
