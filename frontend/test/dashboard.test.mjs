import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

import { displayPage } from "../src/lib/dashboard.ts"

test("rendering with no Resolve Page is shown as render export time", () => {
  assert.equal(displayPage("Unknown", "rendering"), "Render/Export")
})

test("PDF export keeps the selected theme", async () => {
  const css = await readFile(
    new URL("../src/index.css", import.meta.url),
    "utf8"
  )

  assert.match(css, /@page\s*{[\s\S]*background:\s*var\(--background\)/)
  assert.match(css, /body\s*{\s*background:\s*var\(--background\)/)
})
