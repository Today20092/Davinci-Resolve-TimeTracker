const fs = require("node:fs")
const path = require("node:path")

const startupFilename = "ResolveTimeTrackerBackground.cmd"

function startupPath(appData) {
  return path.join(
    appData,
    "Microsoft",
    "Windows",
    "Start Menu",
    "Programs",
    "Startup",
    startupFilename
  )
}

function startupEnabled(appData) {
  return fs.existsSync(startupPath(appData))
}

function setStartupEnabled({ appData, repoRoot, enabled }) {
  const target = startupPath(appData)
  if (!enabled) {
    fs.rmSync(target, { force: true })
    return false
  }

  const python = path.join(repoRoot, ".venv", "Scripts", "pythonw.exe")
  const launcher = path.join(repoRoot, "scripts", "ResolveTimeTracker.py")
  if (!fs.existsSync(python) || !fs.existsSync(launcher)) {
    throw new Error("Resolve Time Tracker installation is incomplete")
  }
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(
    target,
    [
      "@echo off",
      `cd /d "${repoRoot}"`,
      `start "" /min "${python}" "${launcher}" --companion --background`,
      "",
    ].join("\r\n"),
    "utf8"
  )
  return true
}

module.exports = { setStartupEnabled, startupEnabled, startupPath }
