import assert from "node:assert/strict"
import { EventEmitter } from "node:events"
import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"
import path from "node:path"
import vm from "node:vm"
import test from "node:test"

const require = createRequire(import.meta.url)
const mainPath = fileURLToPath(new URL("../electron/main.cjs", import.meta.url))
const source = readFileSync(mainPath, "utf8")
const flush = () => new Promise((resolve) => setImmediate(resolve))

function desktop({ single = true, connect } = {}) {
  const windows = []
  const errors = []
  const counts = { connections: 0, releases: 0, quits: 0, starts: 0, pipeClosed: 0 }
  const connection = { apiBase: "http://127.0.0.1:54321", release: async () => { counts.releases++ } }
  const app = new EventEmitter()
  Object.assign(app, {
    setName() {}, setAppUserModelId() {}, requestSingleInstanceLock: () => single,
    whenReady: () => Promise.resolve(),
    quit() {
      const event = { prevented: false, preventDefault() { this.prevented = true } }
      app.emit("before-quit", event)
      if (!event.prevented) counts.quits++
    },
  })
  class BrowserWindow extends EventEmitter {
    constructor(options) { super(); this.options = options; this.focused = 0; windows.push(this) }
    loadFile(file, options) { this.loaded = { file, options }; return Promise.resolve() }
    isMinimized() { return true }
    restore() { this.restored = true }
    show() { this.shown = true }
    focus() { this.focused++ }
    close() {
      const event = { prevented: false, preventDefault() { this.prevented = true } }
      this.emit("close", event)
      if (!event.prevented) { this.destroyed = true; this.emit("closed"); app.emit("window-all-closed") }
    }
  }
  const child = new EventEmitter()
  child.stderr = new EventEmitter()
  child.stderr.destroy = () => { counts.pipeClosed++ }
  child.unref = () => {}
  const electron = {
    app, BrowserWindow, ipcMain: { handle() {} }, clipboard: {}, shell: {},
    dialog: { showErrorBox: (...args) => errors.push(args) },
    Tray: class { constructor() { assert.fail("No tray should be created") } },
  }
  vm.runInNewContext(source, {
    require(name) {
      if (name === "electron") return electron
      if (name === "node:fs") return { existsSync: () => true }
      if (name === "node:child_process") return { spawn: () => { counts.starts++; return child } }
      if (name === "./support-report.cjs") return { buildSupportReport: () => "report" }
      if (name === "./sidecar-lifecycle.cjs") return { connectRuntime: async (options) => {
        counts.connections++
        return connect ? connect(options, connection) : connection
      } }
      return require(name)
    },
    __dirname: path.dirname(mainPath),
    process: { argv: ["electron", mainPath], env: {}, platform: process.platform, pid: 42 },
    console, setTimeout, clearTimeout, AbortSignal,
  }, { filename: mainPath })
  return { app, windows, counts, errors, connection }
}

test("requested launch creates one visible renderer; close destroys and detaches", async () => {
  const host = desktop()
  await flush()
  assert.equal(host.windows.length, 1)
  assert.notEqual(host.windows[0].options.show, false)
  assert.equal(host.windows[0].loaded.options.query.api, host.connection.apiBase)
  host.windows[0].close()
  await flush()
  assert.equal(host.windows[0].destroyed, true)
  assert.equal(host.counts.releases, 1)
  assert.equal(host.counts.quits, 1)
  assert.equal(host.counts.starts, 0)
})

test("second instance focuses dashboard without another renderer or owner", async () => {
  const host = desktop()
  await flush()
  host.app.emit("second-instance")
  assert.equal(host.windows[0].focused, 1)
  assert.equal(host.windows[0].restored, true)
  assert.equal(host.windows.length, 1)
  assert.equal(host.counts.connections, 1)
  const duplicate = desktop({ single: false })
  await flush()
  assert.equal(duplicate.windows.length, 0)
  assert.equal(duplicate.counts.connections, 0)
})

test("startup failure cleans child pipe and exits without a hidden renderer", async () => {
  const host = desktop({ connect: async ({ startSidecar }) => {
    startSidecar()
    throw new Error("startup failed")
  } })
  await flush()
  assert.equal(host.windows.length, 0)
  assert.equal(host.errors.length, 1)
  assert.equal(host.counts.pipeClosed, 1)
  assert.equal(host.counts.quits, 1)
})

test("quit during connection detaches late connection without opening renderer", async () => {
  let resolveConnection
  const pending = new Promise((resolve) => { resolveConnection = resolve })
  const host = desktop({ connect: () => pending })
  await flush()
  host.app.quit()
  await flush()
  resolveConnection(host.connection)
  await flush()
  assert.equal(host.windows.length, 0)
  assert.equal(host.counts.releases, 1)
  assert.equal(host.counts.quits, 1)
})
