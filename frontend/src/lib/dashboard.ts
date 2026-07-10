import type { Session, Status } from "@/lib/api"

export type ProjectDashboard = {
  project: string | null
  trackedSeconds: number
  todaySeconds: number
  editingSeconds: number
  renderingSeconds: number
  sessionCount: number
  lastActivity: string
  recentSessions: Session[]
  pageData: Array<{ page: string; seconds: number }>
}

export type ProjectExportSummary = {
  project: string
  generatedAt: string
  dateRange: string
}

export function currentProjectDashboard(
  sessions: Session[],
  status: Pick<Status, "project" | "page" | "state" | "active_elapsed_seconds">
): ProjectDashboard {
  const project = status.project === "none" ? null : status.project
  if (!project) {
    return emptyDashboard()
  }

  const pageTotals = new Map<string, number>()
  let trackedSeconds = 0
  let editingSeconds = 0
  let renderingSeconds = 0
  let sessionCount = 0
  let todaySeconds = 0
  const recentSessions: Session[] = []
  const today = new Date().toISOString().slice(0, 10)

  function add(
    page: string,
    category: string,
    seconds: number,
    startedAt = ""
  ) {
    if (seconds <= 0) return
    trackedSeconds += seconds
    sessionCount += 1
    if (startedAt.startsWith(today)) todaySeconds += seconds
    const pageLabel = displayPage(page, category)
    pageTotals.set(pageLabel, (pageTotals.get(pageLabel) ?? 0) + seconds)
    if (category === "editing") editingSeconds += seconds
    if (category === "rendering") renderingSeconds += seconds
  }

  for (const session of sessions) {
    if (session.project_name === project) {
      recentSessions.push(session)
      add(
        session.page,
        session.activity_category,
        session.duration_seconds,
        session.started_at_utc
      )
    }
  }

  if (status.state === "editing" || status.state === "rendering") {
    add(
      status.page,
      status.state,
      status.active_elapsed_seconds,
      new Date().toISOString()
    )
  }

  recentSessions.sort((a, b) =>
    b.started_at_utc.localeCompare(a.started_at_utc)
  )

  return {
    project,
    trackedSeconds,
    todaySeconds,
    editingSeconds,
    renderingSeconds,
    sessionCount,
    lastActivity: recentSessions[0]?.ended_at_utc || "none",
    recentSessions: recentSessions.slice(0, 5),
    pageData: [...pageTotals.entries()]
      .map(([page, seconds]) => ({ page, seconds }))
      .sort((a, b) => b.seconds - a.seconds),
  }
}

export function projectExportSummary(
  dashboard: ProjectDashboard,
  sessions: Session[],
  generatedAt = new Date()
): ProjectExportSummary | null {
  if (!dashboard.project) return null

  const projectSessions = sessions.filter(
    (session) => session.project_name === dashboard.project
  )
  const starts = projectSessions
    .map((session) => session.started_at_utc)
    .filter(Boolean)
    .sort()
  const ends = projectSessions
    .map((session) => session.ended_at_utc)
    .filter(Boolean)
    .sort()

  return {
    project: dashboard.project,
    generatedAt: generatedAt.toLocaleDateString("en-US"),
    dateRange:
      starts.length && ends.length
        ? `${formatDate(starts[0])} - ${formatDate(ends.at(-1) ?? starts[0])}`
        : "Live project time",
  }
}

function emptyDashboard(): ProjectDashboard {
  return {
    project: null,
    trackedSeconds: 0,
    todaySeconds: 0,
    editingSeconds: 0,
    renderingSeconds: 0,
    sessionCount: 0,
    lastActivity: "none",
    recentSessions: [],
    pageData: [],
  }
}

function formatDate(value: string) {
  const normalized = value.includes("T") ? value : value.replace(" ", "T")
  const date = new Date(
    normalized.endsWith("Z") ? normalized : `${normalized}Z`
  )
  if (Number.isNaN(date.getTime())) return value.split("T")[0]
  return date.toLocaleDateString("en-US")
}

export function displayPage(page: string, category: string) {
  if (
    category === "rendering" &&
    (!page || page === "Unknown" || page === "none")
  ) {
    return "Render/Export"
  }
  return page || "Unknown"
}
