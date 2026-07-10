export type Status = {
  connection: string
  project: string
  page: string
  state: string
  active_elapsed: string
  active_elapsed_seconds: number
  heartbeat: string
  tracking_enabled: boolean
  db_path: string
}

export type ProjectSummary = {
  project_name: string
  session_count: number
  duration_seconds: number
  duration: string
  last_session_date: string | null
}

export type Session = {
  id: number
  project_name: string
  started_at_utc: string
  ended_at_utc: string
  duration_seconds: number
  duration: string
  page: string
  activity_category: string
}

export type Settings = {
  idle_timeout_seconds: number
  idle_timeout_minutes: number
}

export type SessionUpdate = {
  started_at_utc: string
  ended_at_utc: string
  page: string
  activity_category: string
}

export type PdfExportOptions = {
  project_name: string
  show_totals: boolean
  show_page_chart: boolean
  show_activity_chart: boolean
  show_recent_activity: boolean
}

export function formatSidecarError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

export const apiBase =
  (typeof window === "undefined"
    ? null
    : new URLSearchParams(window.location.search).get("api")) ??
  import.meta.env?.VITE_API_BASE ??
  "http://127.0.0.1:8765"

type Fetch = typeof fetch
type EventSourceConstructor = typeof EventSource

export function createSidecarClient({
  baseUrl = apiBase,
  fetch: fetchRequest = fetch,
  eventSource,
}: {
  baseUrl?: string
  fetch?: Fetch
  eventSource?: EventSourceConstructor
} = {}) {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetchRequest(`${baseUrl}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...init?.headers,
      },
    })
    if (!response.ok) {
      const body = await response.text()
      throw new Error(body || response.statusText)
    }
    return response.json() as Promise<T>
  }

  async function loadHistory() {
    const [projects, sessions] = await Promise.all([
      request<ProjectSummary[]>("/projects"),
      request<Session[]>("/sessions"),
    ])
    return { projects, sessions }
  }

  async function loadDashboard() {
    const [status, settings, history] = await Promise.all([
      request<Status>("/status"),
      request<Settings>("/settings"),
      loadHistory(),
    ])
    return { status, settings, ...history }
  }

  async function runAndReload(action: () => Promise<unknown>) {
    await action()
    return loadDashboard()
  }

  async function exportPdf(options: PdfExportOptions) {
    const response = await fetchRequest(`${baseUrl}/export.pdf`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(options),
    })
    if (!response.ok) {
      const body = await response.text()
      throw new Error(body || response.statusText)
    }
    return response.blob()
  }

  return {
    loadDashboard,
    loadHistory,
    csvExportUrl: () => `${baseUrl}/export.csv`,
    exportPdf,
    refresh: () =>
      runAndReload(() => request<Status>("/refresh", { method: "POST" })),
    setTracking: (enabled: boolean) =>
      runAndReload(() =>
        request<Status>(enabled ? "/tracking/resume" : "/tracking/pause", {
          method: "POST",
        })
      ),
    updateSettings: (idleTimeoutSeconds: number) =>
      runAndReload(() =>
        request<Settings>("/settings", {
          method: "POST",
          body: JSON.stringify({ idle_timeout_seconds: idleTimeoutSeconds }),
        })
      ),
    updateSession: (sessionId: number, update: SessionUpdate) =>
      runAndReload(() =>
        request<Session>(`/sessions/${sessionId}`, {
          method: "POST",
          body: JSON.stringify(update),
        })
      ),
    watchDashboard({
      onUpdate,
      onError,
    }: {
      onUpdate: (update: {
        status: Status
        projects: ProjectSummary[]
        sessions: Session[]
      }) => void
      onError: (error: unknown) => void
    }) {
      const Source = eventSource ?? EventSource
      const source = new Source(`${baseUrl}/events`)
      source.addEventListener("status", (event) => {
        const status = JSON.parse((event as MessageEvent).data) as Status
        void loadHistory().then(
          (history) => onUpdate({ status, ...history }),
          onError
        )
      })
      source.onerror = () => onError(new Error("Waiting for the sidecar API"))
      return () => source.close()
    },
  }
}
