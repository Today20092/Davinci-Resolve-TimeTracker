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
    pageTotals.set(page || "Unknown", (pageTotals.get(page) ?? 0) + seconds)
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
