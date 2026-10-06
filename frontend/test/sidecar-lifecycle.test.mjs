import assert from "node:assert/strict"
import { createRequire } from "node:module"
import test from "node:test"

const require = createRequire(import.meta.url)
const { connectRuntime } = require("../electron/sidecar-lifecycle.cjs")
const endpoint = JSON.stringify({ port: 54321, token: "test-token" })

test("reuses an owner and detaches without starting or stopping it", async () => {
  const requests = []
  const connection = await connectRuntime({
    db: "tracker.sqlite3", pid: 42, readFile: async () => endpoint,
    startSidecar: () => assert.fail("must reuse owner"),
    request: async (url, options) => { requests.push({ url, options }); return { ok: true } },
  })
  await connection.release()
  assert.deepEqual(requests.map(({ url }) => url.split("/").at(-1)), ["attach", "detach"])
  for (const { options } of requests) {
    assert.equal(options.headers["X-Runtime-Token"], "test-token")
    assert.deepEqual(JSON.parse(options.body), { pid: 42 })
  }
})

test("missing endpoint starts once and waits for publication", async () => {
  let starts = 0
  let reads = 0
  await connectRuntime({
    db: "tracker.sqlite3", pid: 42,
    readFile: async () => { if (++reads < 3) throw new Error("not ready"); return endpoint },
    startSidecar: () => { starts++ }, request: async () => ({ ok: true }), wait: async () => {},
  })
  assert.equal(starts, 1)
  assert.equal(reads, 3)
})

test("invalid endpoint is never contacted and retries are bounded", async () => {
  let starts = 0
  let reads = 0
  let requests = 0
  await assert.rejects(connectRuntime({
    db: "tracker.sqlite3", pid: 42,
    readFile: async () => { reads++; return JSON.stringify({ port: 70000, token: "secret" }) },
    startSidecar: () => { starts++ }, request: async () => { requests++; return { ok: false } }, wait: async () => {},
  }), /Tracker did not start/)
  assert.equal(starts, 1)
  assert.equal(reads, 101)
  assert.equal(requests, 0)
})

test("stale owner starts only one replacement", async () => {
  let starts = 0
  let requests = 0
  await connectRuntime({
    db: "tracker.sqlite3", pid: 42, readFile: async () => endpoint,
    startSidecar: () => { starts++ },
    request: async () => ({ ok: ++requests > 1, status: 409 }), wait: async () => {},
  })
  assert.equal(starts, 1)
  assert.equal(requests, 2)
})
