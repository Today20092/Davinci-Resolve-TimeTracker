export function sortRows<T>(
  rows: T[],
  key: keyof T,
  direction: "ascending" | "descending"
) {
  const multiplier = direction === "ascending" ? 1 : -1
  return [...rows].sort(
    (a, b) =>
      String(a[key] ?? "").localeCompare(String(b[key] ?? ""), undefined, {
        numeric: true,
      }) * multiplier
  )
}
