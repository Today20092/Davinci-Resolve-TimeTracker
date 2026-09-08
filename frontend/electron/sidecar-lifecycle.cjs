const fs = require("node:fs/promises")
const path = require("node:path")

async function connectRuntime({
  db,
  pid,
  startSidecar,
  readFile = fs.readFile,
  request = fetch,
  wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}) {
  const parsed = path.parse(db)
  const infoPath = path.join(parsed.dir, parsed.name + ".runtime.json")
  async function attach() {
    const info = JSON.parse(await readFile(infoPath, "utf8"))
    if (
      !Number.isInteger(info.port) ||
      info.port < 1 ||
      info.port > 65535 ||
      typeof info.token !== "string"
    )
      throw new Error("Invalid tracker endpoint")
    const apiBase = "http://127.0.0.1:" + info.port
    async function send(route) {
      const response = await request(apiBase + "/runtime/" + route, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Runtime-Token": info.token,
        },
        body: JSON.stringify({ pid }),
        signal: AbortSignal.timeout(1000),
      })
      if (!response.ok) throw new Error("Tracker returned " + response.status)
    }
    await send("attach")
    return { apiBase, release: () => send("detach") }
  }
  try {
    return await attach()
  } catch {
    /* Missing or stale runtime; start once. */
  }
  startSidecar()
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      return await attach()
    } catch {
      await wait(100)
    }
  }
  throw new Error(
    "Tracker did not start. Reopen the dashboard or run the installer."
  )
}
module.exports = { connectRuntime }
