import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const appSource = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8")

test("dashboard page charts share content-sized axis layout", () => {
  const [, axis] = appSource.match(/function PageAxis\(\)[\s\S]*?<YAxis\b([^>]*)\/>/) ?? []
  const uses = appSource.match(/<PageAxis \/>/g) ?? []

  assert.equal(uses.length, 2, "expected dashboard and export to share PageAxis")
  assert.match(axis ?? "", /\bwidth="auto"/)
  assert.doesNotMatch(axis ?? "", /\bwidth=\{\d+\}/)
})
