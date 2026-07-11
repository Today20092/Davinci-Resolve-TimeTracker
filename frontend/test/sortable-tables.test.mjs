import assert from "node:assert/strict"
import test from "node:test"
import { sortRows } from "../src/lib/sort.ts"

test("sorts table rows by text and numeric values without mutating input", () => {
  const rows = [
    { project: "zebra", seconds: 2 },
    { project: "Alpha", seconds: 10 },
  ]

  assert.deepEqual(
    sortRows(rows, "project", "ascending").map((row) => row.project),
    ["Alpha", "zebra"]
  )
  assert.deepEqual(
    sortRows(rows, "seconds", "descending").map((row) => row.seconds),
    [10, 2]
  )
  assert.equal(rows[0].project, "zebra")
})
