const {
  app,
  BrowserWindow,
  clipboard,
  dialog,
  ipcMain,
  shell,
} = require("electron")
const { spawn } = require("node:child_process")
const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")
const { buildSupportReport } = require("./support-report.cjs")
const { connectRuntime } = require("./sidecar-lifecycle.cjs")

const frontendRoot = path.resolve(__dirname, "..")
const repoRoot = path.resolve(frontendRoot, "..")
const appName = "Resolve Time Tracker"
app.setName(appName)
app.setAppUserModelId("com.resolve-time-tracker.app")
const devMode = process.argv.includes("--dev")
const single = app.requestSingleInstanceLock()
if (!single) app.quit()
let win = null
let connection = null
let child = null
let quitting = false
let released = false
let sidecarStderr = ""
let lastSidecarError = null

function readArg(name) {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : null
}
function defaultDb() {
  const root =
    process.platform === "win32"
      ? process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local")
      : process.platform === "darwin"
        ? path.join(os.homedir(), "Library", "Application Support")
        : process.env.XDG_DATA_HOME ||
          path.join(os.homedir(), ".local", "share")
  return path.join(root, "ResolveTimeTracker", "tracker.sqlite3")
}
const db = path.resolve(
  readArg("--db") || process.env.RESOLVE_TIME_TRACKER_DB || defaultDb()
)

ipcMain.handle("open-data-folder", (_event, dbPath) => {
  if (typeof dbPath !== "string" || !dbPath) return false
  shell.showItemInFolder(path.resolve(dbPath))
  return true
})
ipcMain.handle("export-pdf", async (event, filename) => {
  const { canceled, filePath } = await dialog.showSaveDialog(
    BrowserWindow.fromWebContents(event.sender),
    {
      defaultPath: filename,
      filters: [{ name: "PDF", extensions: ["pdf"] }],
    }
  )
  if (canceled || !filePath) return false
  const pdf = await event.sender.printToPDF({
    pageSize: "Letter",
    printBackground: true,
    preferCSSPageSize: true,
  })
  fs.writeFileSync(filePath, pdf)
  return true
})
ipcMain.handle("copy-support-report", (_event, report) => {
  clipboard.writeText(String(report))
  return true
})
ipcMain.handle("get-support-report", () => supportReport())
ipcMain.handle("save-support-report", async (event, report) => {
  const { canceled, filePath } = await dialog.showSaveDialog(
    BrowserWindow.fromWebContents(event.sender),
    {
      defaultPath: "Resolve-Time-Tracker-support.txt",
      filters: [{ name: "Text", extensions: ["txt"] }],
    }
  )
  if (canceled || !filePath) return false
  fs.writeFileSync(filePath, String(report), "utf8")
  return true
})

function startSidecar() {
  const python =
    readArg("--python") ||
    process.env.RESOLVE_TIME_TRACKER_PYTHON ||
    path.join(
      repoRoot,
      ".venv",
      process.platform === "win32" ? "Scripts" : "bin",
      process.platform === "win32" ? "python.exe" : "python"
    )
  if (!fs.existsSync(python))
    throw new Error("Python environment is missing. Run the installer first.")
  child = spawn(
    python,
    [
      path.join(repoRoot, "scripts", "ResolveTimeTracker.py"),
      "--api",
      "--db",
      db,
      "--dashboard-pid",
      String(process.pid),
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["ignore", "ignore", "pipe"],
      windowsHide: true,
    }
  )
  child.stderr.on("data", (data) => {
    sidecarStderr = (sidecarStderr + data).slice(-4000)
  })
  child.on("error", (error) => {
    lastSidecarError = error.message
  })
  child.unref()
}

async function supportReport() {
  let sidecar
  try {
    const response = await fetch(connection.apiBase + "/diagnostics", {
      signal: AbortSignal.timeout(1000),
    })
    if (!response.ok) throw new Error("status " + response.status)
    sidecar = { reachable: true, diagnostics: await response.json() }
  } catch (error) {
    sidecar = { reachable: false, error: lastSidecarError || error.message }
  }
  return buildSupportReport({
    generatedAt: new Date().toISOString(),
    appVersion: app.getVersion(),
    electronVersion: process.versions.electron,
    platform: process.platform + " " + os.release() + " " + process.arch,
    apiBase: connection?.apiBase,
    electronMemoryMb: Math.round(process.memoryUsage().rss / 1024 / 1024),
    launchMode: app.isPackaged
      ? "packaged"
      : devMode
        ? "development"
        : "source checkout",
    sidecar: { ...sidecar, stderr: sidecarStderr },
    userHome: os.homedir(),
  })
}

function createWindow() {
  win = new BrowserWindow({
    width: 1120,
    height: 720,
    minWidth: 900,
    minHeight: 560,
    title: appName,
    icon: path.join(frontendRoot, "public", "app-icon.png"),
    backgroundColor: "#ffffff",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
  })
  win.on("closed", () => {
    win = null
  })
  if (process.argv.includes("--smoke-test")) {
    const timer = setTimeout(() => {
      process.exitCode = 1
      app.quit()
    }, 15000)
    win.webContents.once("dom-ready", async () => {
      const ok = await win.webContents.executeJavaScript(
        'document.body.innerText.includes("Dashboard")'
      )
      console.log(JSON.stringify({ ok, apiBase: connection.apiBase }))
      clearTimeout(timer)
      process.exitCode = ok ? 0 : 1
      app.quit()
    })
  }
  if (devMode) {
    void win.loadURL(
      "http://127.0.0.1:5173/?api=" + encodeURIComponent(connection.apiBase)
    )
  } else {
    void win.loadFile(path.join(frontendRoot, "dist", "index.html"), {
      query: { api: connection.apiBase },
    })
  }
}

app.on("second-instance", () => {
  if (win) {
    if (win.isMinimized()) win.restore()
    win.show()
    win.focus()
  }
})
app.whenReady().then(async () => {
  if (!single) return
  try {
    connection = await connectRuntime({ db, pid: process.pid, startSidecar })
    if (quitting) {
      await connection.release()
      return
    }
    createWindow()
  } catch (error) {
    dialog.showErrorBox(appName, lastSidecarError || error.message)
    app.quit()
  }
})
app.on("window-all-closed", () => app.quit())
app.on("before-quit", (event) => {
  quitting = true
  if (released) return
  event.preventDefault()
  released = true
  Promise.resolve(connection?.release())
    .catch(() => {})
    .finally(() => {
      child?.stderr?.destroy()
      app.quit()
    })
})
