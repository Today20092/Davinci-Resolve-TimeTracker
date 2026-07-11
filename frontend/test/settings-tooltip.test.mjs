import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

test("idle timeout explains that rendering still counts", async () => {
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8")

  assert.match(app, /aria-label="About idle timeout"/)
  assert.match(
    app,
    /Rendering and exporting continue to count as active work,[\s\S]*even after this idle timeout\./
  )
})

test("settings expose desktop preferences", async () => {
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8")
  const main = await readFile(
    new URL("../electron/main.cjs", import.meta.url),
    "utf8"
  )

  for (const label of [
    "System",
    "Start minimized to tray",
    "Keep running in tray",
    "Quit tracker",
    "Open data folder",
  ]) {
    assert.match(app, new RegExp(label))
  }
  assert.match(main, /startupEnabled/)
  assert.match(main, /closeBehavior === "tray"/)
  assert.match(main, /shell\.showItemInFolder/)
})
