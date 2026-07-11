import assert from "node:assert/strict"
import test from "node:test"

import { displayPage } from "../src/lib/dashboard.ts"

test("rendering with no Resolve Page is shown as render export time", () => {
  assert.equal(displayPage("Unknown", "rendering"), "Render/Export")
})
