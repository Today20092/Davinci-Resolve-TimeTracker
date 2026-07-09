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

export const apiBase =
  new URLSearchParams(window.location.search).get("api") ??
  import.meta.env.VITE_API_BASE ??
  "http://127.0.0.1:8765"

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
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

export function downloadUrl(path: string) {
  return `${apiBase}${path}`
}
