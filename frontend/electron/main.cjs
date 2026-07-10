const { app, BrowserWindow, dialog } = require("electron")
const { spawn } = require("node:child_process")
const fs = require("node:fs")
const http = require("node:http")
const path = require("node:path")

const frontendRoot = path.resolve(__dirname, "..")
const repoRoot = path.resolve(frontendRoot, "..")
const apiPort = Number(
  process.env.RESOLVE_TIME_TRACKER_API_PORT || readArg("--port") || 8765
)
const apiBase = `http://127.0.0.1:${apiPort}`
let sidecar = null
let smokeFinished = false

function readArg(name) {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : null
}

function hasArg(name) {
  return process.argv.includes(name)
}

function startSidecar() {
  const db = readArg("--db")
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
    console.error(`Python sidecar exited: code=${code} signal=${signal}`)
  })

  sidecar.on("error", (error) => {
    dialog.showErrorBox(
      "Resolve Time Tracker",
      `Could not start Python sidecar:\n${error.message}`
    )
  })
}

function stopSidecar() {
  if (sidecar && !sidecar.killed) {
    sidecar.kill()
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
    try {
      const status = await new Promise((resolve, reject) => {
        const request = http.get(`${apiBase}/status`, (response) => {
          response.resume()
          resolve(response.statusCode)
        })
        request.on("error", reject)
        request.setTimeout(1000, () => {
          request.destroy(new Error("timeout"))
        })
      })
      if (status === 200) {
        return
      }
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error(`Sidecar did not respond at ${apiBase}`)
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1120,
    height: 720,
    minWidth: 900,
    minHeight: 560,
    title: "Resolve Time Tracker",
    backgroundColor: "#ffffff",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
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

app.whenReady().then(async () => {
  try {
    startSidecar()
    await waitForApi()
    createWindow()
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
  if (process.platform !== "darwin") {
    app.quit()
  }
})

app.on("before-quit", () => {
  stopSidecar()
})
