const {
  app,
  BrowserWindow,
  Menu,
  Tray,
  dialog,
  ipcMain,
  nativeImage,
  shell,
} = require("electron")
const { spawn } = require("node:child_process")
const fs = require("node:fs")
const http = require("node:http")
const path = require("node:path")
const { trayPresentation } = require("./tray-status.cjs")
const { restartSidecar } = require("./sidecar-lifecycle.cjs")
const {
  setStartupEnabled,
  startupEnabled,
} = require("./startup-settings.cjs")

const frontendRoot = path.resolve(__dirname, "..")
const repoRoot = path.resolve(frontendRoot, "..")
const appName = "Resolve Time Tracker"
const appIcon = path.join(frontendRoot, "public", "app-icon.png")
app.setName(appName)
app.setAppUserModelId("com.resolve-time-tracker.app")
const hasSingleInstanceLock = app.requestSingleInstanceLock()
if (!hasSingleInstanceLock) {
  app.quit()
}
let apiPort = Number(
  process.env.RESOLVE_TIME_TRACKER_API_PORT || readArg("--port") || 8765
)
let apiBase = `http://127.0.0.1:${apiPort}`
let sidecar = null
let sidecarRestartTimer = null
let tray = null
let trayTimer = null
let win = null
let quitting = false
let closeBehavior = "tray"
let smokeFinished = false

ipcMain.handle("desktop-settings", () => ({
  launchAtStartup:
    process.platform === "win32" && startupEnabled(app.getPath("appData")),
}))

ipcMain.handle("set-launch-at-startup", (_event, enabled) => {
  if (process.platform !== "win32") return false
  return setStartupEnabled({
    appData: app.getPath("appData"),
    repoRoot,
    enabled: Boolean(enabled),
  })
})

ipcMain.handle("set-close-behavior", (_event, behavior) => {
  closeBehavior = behavior === "quit" ? "quit" : "tray"
})

ipcMain.handle("open-data-folder", (_event, dbPath) => {
  if (typeof dbPath !== "string" || !dbPath) return false
  shell.showItemInFolder(path.resolve(dbPath))
  return true
})

ipcMain.handle("export-pdf", async (event, filename) => {
  const window = BrowserWindow.fromWebContents(event.sender)
  const { canceled, filePath } = await dialog.showSaveDialog(window, {
    defaultPath: filename,
    filters: [{ name: "PDF", extensions: ["pdf"] }],
  })
  if (canceled || !filePath) return false

  const pdf = await event.sender.printToPDF({
    pageSize: "Letter",
    printBackground: true,
    preferCSSPageSize: true,
  })
  fs.writeFileSync(filePath, pdf)
  return true
})

function readArg(name) {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : null
}

function hasArg(name) {
  return process.argv.includes(name)
}

function startSidecar() {
  const db = readArg("--db") || process.env.RESOLVE_TIME_TRACKER_DB
  const python = readArg("--python") || process.env.RESOLVE_TIME_TRACKER_PYTHON
  const command = python || "uv"
  const args = python
    ? [path.join(repoRoot, "scripts", "ResolveTimeTracker.py")]
    : [
        "run",
        "--isolated",
        "--python",
        "3.13",
        "--with",
        "fastapi",
        "--with",
        "reportlab",
        "--with",
        "uvicorn",
        "scripts/ResolveTimeTracker.py",
      ]

  args.push("--api", "--host", "127.0.0.1", "--port", String(apiPort))
  if (db) {
    args.push("--db", db)
  }

  sidecar = spawn(command, args, {
    cwd: repoRoot,
    env: process.env,
    stdio: "pipe",
    windowsHide: true,
  })

  sidecar.stdout.on("data", (data) => process.stdout.write(data))
  sidecar.stderr.on("data", (data) => process.stderr.write(data))
  sidecar.on("exit", (code, signal) => {
    sidecar = null
    console.error(`Python sidecar exited: code=${code} signal=${signal}`)
    scheduleSidecarRestart()
  })

  sidecar.on("error", (error) => {
    dialog.showErrorBox(
      "Resolve Time Tracker",
      `Could not start Python sidecar:\n${error.message}`
    )
  })
}

function scheduleSidecarRestart() {
  if (quitting || sidecarRestartTimer) return
  sidecarRestartTimer = setTimeout(
    restartSidecar({
      apiIsRunning,
      isQuitting: () => quitting,
      onComplete: () => (sidecarRestartTimer = null),
      startSidecar,
    }),
    1000
  )
}

function stopSidecar() {
  if (sidecar && !sidecar.killed) {
    sidecar.kill()
  }
}

async function apiIsRunning(timeoutMs = 250) {
  try {
    await fetchHealth(timeoutMs)
    return true
  } catch {
    return false
  }
}

function fetchHealth(timeoutMs = 1000) {
  return new Promise((resolve, reject) => {
    const request = http.get(`${apiBase}/health`, (response) => {
      response.resume()
      response.statusCode === 200
        ? resolve()
        : reject(new Error(`status ${response.statusCode}`))
    })
    request.on("error", reject)
    request.setTimeout(timeoutMs, () => request.destroy(new Error("timeout")))
  })
}

function fetchStatus(timeoutMs = 1000) {
  return new Promise((resolve, reject) => {
    const request = http.get(`${apiBase}/status`, (response) => {
      let body = ""
      response.setEncoding("utf8")
      response.on("data", (chunk) => (body += chunk))
      response.on("end", () => {
        if (response.statusCode !== 200) {
          reject(new Error(`status ${response.statusCode}`))
          return
        }
        resolve(JSON.parse(body))
      })
    })
    request.on("error", reject)
    request.setTimeout(timeoutMs, () => request.destroy(new Error("timeout")))
  })
}

function trayIcon(color) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><circle cx="8" cy="8" r="7" fill="${color}"/></svg>`
  return nativeImage.createFromDataURL(
    `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`
  )
}

async function updateTray() {
  let status = null
  try {
    status = await fetchStatus()
  } catch {
    scheduleSidecarRestart()
  }
  const presentation = trayPresentation(status)
  tray.setImage(trayIcon(presentation.color))
  tray.setToolTip(presentation.tooltip)
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: presentation.label, enabled: false },
      { label: "Open Resolve Time Tracker", click: showWindow },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() },
    ])
  )
}

function showWindow() {
  if (!win || win.isDestroyed()) {
    createWindow()
  } else {
    win.show()
    win.focus()
  }
}

function createTray() {
  tray = new Tray(trayIcon("#ef4444"))
  tray.on("click", showWindow)
  void updateTray()
  trayTimer = setInterval(updateTray, 5000)
}

async function apiSupportsPdf(timeoutMs = 250) {
  try {
    const paths = await new Promise((resolve, reject) => {
      const request = http.get(`${apiBase}/openapi.json`, (response) => {
        let body = ""
        response.setEncoding("utf8")
        response.on("data", (chunk) => {
          body += chunk
        })
        response.on("end", () => {
          if (response.statusCode !== 200) {
            reject(new Error(`status ${response.statusCode}`))
            return
          }
          resolve(JSON.parse(body).paths || {})
        })
      })
      request.on("error", reject)
      request.setTimeout(timeoutMs, () => {
        request.destroy(new Error("timeout"))
      })
    })
    return Object.hasOwn(paths, "/export.pdf")
  } catch {
    return false
  }
}

function useNextApiPort() {
  apiPort += 1
  apiBase = `http://127.0.0.1:${apiPort}`
}

async function chooseApiPort() {
  while ((await apiIsRunning()) && !(await apiSupportsPdf())) {
    useNextApiPort()
  }
}

function finishSmoke(ok, message = null) {
  if (smokeFinished) {
    return
  }
  smokeFinished = true
  console.log(JSON.stringify({ ok, apiBase, message }))
  stopSidecar()
  app.exit(ok ? 0 : 1)
  setTimeout(() => process.exit(ok ? 0 : 1), 100)
}

async function waitForApi() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (await apiIsRunning(1000)) {
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error(`Sidecar did not respond at ${apiBase}`)
}

function createWindow() {
  win = new BrowserWindow({
    width: 1120,
    height: 720,
    minWidth: 900,
    minHeight: 560,
    title: appName,
    icon: appIcon,
    backgroundColor: "#ffffff",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
  })
  win.on("close", (event) => {
    if (!quitting && closeBehavior === "tray") {
      event.preventDefault()
      win.hide()
    } else if (!quitting) {
      event.preventDefault()
      quitting = true
      app.quit()
    }
  })

  const devUrl = hasArg("--dev")
    ? `http://127.0.0.1:5173/?api=${encodeURIComponent(apiBase)}`
    : null
  const builtIndex = path.join(frontendRoot, "dist", "index.html")

  if (hasArg("--smoke-test")) {
    const timer = setTimeout(() => finishSmoke(false, "timeout"), 15000)
    win.webContents.once("dom-ready", async () => {
      await new Promise((resolve) => setTimeout(resolve, 500))
      const result = await win.webContents.executeJavaScript(`
          document.body.innerText.includes("Dashboard") &&
          document.body.innerText.includes("Page activity")
        `)
      clearTimeout(timer)
      finishSmoke(result)
    })
    win.webContents.once("did-fail-load", (_event, code, description) =>
      finishSmoke(false, `${code}: ${description}`)
    )
  }

  if (devUrl) {
    void win.loadURL(devUrl)
  } else if (fs.existsSync(builtIndex)) {
    void win.loadFile(builtIndex, { query: { api: apiBase } })
  } else {
    void win.loadURL(
      `http://127.0.0.1:5173/?api=${encodeURIComponent(apiBase)}`
    )
  }
}

app.on("second-instance", showWindow)

app.whenReady().then(async () => {
  if (!hasSingleInstanceLock) return
  try {
    await chooseApiPort()
    if (!(await apiIsRunning())) {
      startSidecar()
    }
    await waitForApi()
    createTray()
    createWindow()
    if (hasArg("--background")) {
      win.hide()
    }
  } catch (error) {
    if (hasArg("--smoke-test")) {
      finishSmoke(false, error.message)
    } else {
      dialog.showErrorBox("Resolve Time Tracker", error.message)
      app.quit()
    }
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on("window-all-closed", () => {
  // The tray owns the background tracker lifecycle.
})

app.on("before-quit", () => {
  quitting = true
  clearInterval(trayTimer)
  clearTimeout(sidecarRestartTimer)
  stopSidecar()
})
