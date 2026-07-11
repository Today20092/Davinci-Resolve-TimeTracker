export function displayPage(page: string, category: string) {
  if (
    category === "rendering" &&
    (!page || page === "Unknown" || page === "none")
  ) {
    return "Render/Export"
  }
  return page || "Unknown"
}
