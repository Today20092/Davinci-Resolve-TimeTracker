import { useEffect, useMemo, useState } from "react"
import {
  DownloadIcon,
  PauseIcon,
  PencilIcon,
  PlayIcon,
  RefreshCwIcon,
  SaveIcon,
} from "lucide-react"

import {
  api,
  apiBase,
  downloadUrl,
  type ProjectSummary,
  type Session,
  type SessionUpdate,
  type Settings,
  type Status,
} from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const emptyStatus: Status = {
  connection: "waiting",
  project: "none",
  page: "none",
  state: "paused",
  active_elapsed: "0:00:00",
  active_elapsed_seconds: 0,
  heartbeat: "none",
  tracking_enabled: true,
  db_path: "",
}

function App() {
  const [status, setStatus] = useState<Status>(emptyStatus)
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [editForm, setEditForm] = useState<SessionUpdate | null>(null)
  const [idleMinutes, setIdleMinutes] = useState("5")
  const [error, setError] = useState<string | null>(null)

  async function loadTables() {
    const [nextProjects, nextSessions] = await Promise.all([
      api<ProjectSummary[]>("/projects"),
      api<Session[]>("/sessions"),
    ])
    setProjects(nextProjects)
    setSessions(nextSessions)
  }

  async function loadAll() {
    try {
      const [nextStatus, nextSettings] = await Promise.all([
        api<Status>("/status"),
        api<Settings>("/settings"),
        loadTables(),
      ])
      setStatus(nextStatus)
      setSettings(nextSettings)
      setIdleMinutes(String(nextSettings.idle_timeout_minutes))
      setError(null)
    } catch (caught) {
      setError(messageFrom(caught))
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadAll()
    const events = new EventSource(`${apiBase}/events`)
    events.addEventListener("status", (event) => {
      setStatus(JSON.parse((event as MessageEvent).data) as Status)
      void loadTables().catch((caught) => setError(messageFrom(caught)))
    })
    events.onerror = () => setError("Waiting for the sidecar API")
    return () => events.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const totals = useMemo(() => {
    const seconds = projects.reduce(
      (sum, project) => sum + project.duration_seconds,
      0
    )
    return {
      projects: projects.length,
      sessions: projects.reduce(
        (sum, project) => sum + project.session_count,
        0
      ),
      duration: duration(seconds),
    }
  }, [projects])

  async function runAction(action: () => Promise<unknown>) {
    try {
      await action()
      await loadAll()
      setError(null)
    } catch (caught) {
      setError(messageFrom(caught))
    }
  }

  function startEditing(session: Session) {
    setSelectedSession(session)
    setEditForm({
      started_at_utc: session.started_at_utc,
      ended_at_utc: session.ended_at_utc,
      page: session.page,
      activity_category: session.activity_category,
    })
  }

  async function saveSession() {
    if (!selectedSession || !editForm) return
    await runAction(() =>
      api(`/sessions/${selectedSession.id}`, {
        method: "POST",
        body: JSON.stringify(editForm),
      })
    )
    setSelectedSession(null)
    setEditForm(null)
  }

  async function saveSettings() {
    await runAction(() =>
      api("/settings", {
        method: "POST",
        body: JSON.stringify({
          idle_timeout_seconds: Math.max(1, Number(idleMinutes) || 1) * 60,
        }),
      })
    )
  }

  function exportCsv() {
    window.location.href = downloadUrl("/export.csv")
  }

  return (
    <main className="min-h-svh bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 lg:p-6">
        <header className="flex flex-col gap-3 border-b pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="truncate text-xl font-semibold">
              Resolve Time Tracker
            </h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <StatusBadge value={status.connection} />
              <span className="truncate">Project: {status.project}</span>
              <span>Page: {status.page}</span>
              <span>State: {status.state}</span>
              <span>Heartbeat: {status.heartbeat}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() =>
                runAction(() =>
                  api(
                    status.tracking_enabled
                      ? "/tracking/pause"
                      : "/tracking/resume",
                    { method: "POST" }
                  )
                )
              }
            >
              {status.tracking_enabled ? (
                <PauseIcon data-icon="inline-start" />
              ) : (
                <PlayIcon data-icon="inline-start" />
              )}
              {status.tracking_enabled ? "Pause Tracking" : "Resume Tracking"}
            </Button>
            <Button
              variant="outline"
              size="icon"
              aria-label="Refresh"
              onClick={() =>
                runAction(() => api("/refresh", { method: "POST" }))
              }
            >
              <RefreshCwIcon />
            </Button>
          </div>
        </header>

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <Tabs defaultValue="dashboard">
          <TabsList>
            <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
            <TabsTrigger value="projects">Projects</TabsTrigger>
            <TabsTrigger value="sessions">Sessions</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="flex flex-col gap-4">
            <div className="grid gap-3 md:grid-cols-3">
              <Metric title="Active elapsed" value={status.active_elapsed} />
              <Metric title="Projects" value={String(totals.projects)} />
              <Metric title="Total tracked" value={totals.duration} />
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Current Session</CardTitle>
                <CardDescription>
                  {status.db_path || "Database pending"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-3 text-sm md:grid-cols-2 lg:grid-cols-3">
                  <Field label="Connection" value={status.connection} />
                  <Field label="Project" value={status.project} />
                  <Field label="Page" value={status.page} />
                  <Field label="Tracking state" value={status.state} />
                  <Field label="Active elapsed" value={status.active_elapsed} />
                  <Field label="Last heartbeat" value={status.heartbeat} />
                </dl>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="projects">
            <Card>
              <CardHeader>
                <CardTitle>Projects</CardTitle>
                <CardDescription>
                  {totals.sessions} sessions across {totals.projects} projects
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Project</TableHead>
                      <TableHead>Sessions</TableHead>
                      <TableHead>Total</TableHead>
                      <TableHead>Last Session</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {projects.map((project) => (
                      <TableRow key={project.project_name}>
                        <TableCell className="font-medium">
                          {project.project_name}
                        </TableCell>
                        <TableCell>{project.session_count}</TableCell>
                        <TableCell>{project.duration}</TableCell>
                        <TableCell>
                          {project.last_session_date || "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                    {projects.length === 0 && <EmptyRow columns={4} />}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="sessions">
            <Card>
              <CardHeader>
                <CardTitle>Sessions</CardTitle>
                <CardDescription>
                  {sessions.length} saved sessions
                </CardDescription>
                <CardAction>
                  <Button variant="outline" onClick={exportCsv}>
                    <DownloadIcon data-icon="inline-start" />
                    Export CSV
                  </Button>
                </CardAction>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Project</TableHead>
                      <TableHead>Start</TableHead>
                      <TableHead>End</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Page</TableHead>
                      <TableHead>Activity</TableHead>
                      <TableHead className="w-12">
                        <span className="sr-only">Edit</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sessions.map((session) => (
                      <TableRow key={session.id}>
                        <TableCell className="font-medium">
                          {session.project_name}
                        </TableCell>
                        <TableCell>
                          {shortDate(session.started_at_utc)}
                        </TableCell>
                        <TableCell>{shortDate(session.ended_at_utc)}</TableCell>
                        <TableCell>{session.duration}</TableCell>
                        <TableCell>{session.page}</TableCell>
                        <TableCell>{session.activity_category}</TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="Edit session"
                            onClick={() => startEditing(session)}
                          >
                            <PencilIcon />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {sessions.length === 0 && <EmptyRow columns={7} />}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle>Settings</CardTitle>
                <CardDescription>
                  Idle timeout: {settings?.idle_timeout_minutes ?? "-"} minutes
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex max-w-md flex-col gap-2">
                  <Label htmlFor="idle-timeout">Idle timeout minutes</Label>
                  <div className="flex gap-2">
                    <Input
                      id="idle-timeout"
                      min={1}
                      type="number"
                      value={idleMinutes}
                      onChange={(event) => setIdleMinutes(event.target.value)}
                    />
                    <Button onClick={saveSettings}>
                      <SaveIcon data-icon="inline-start" />
                      Save
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <Dialog
        open={selectedSession !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedSession(null)
            setEditForm(null)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Session</DialogTitle>
            <DialogDescription>
              {selectedSession?.project_name ?? "Session"}
            </DialogDescription>
          </DialogHeader>
          {editForm && (
            <div className="grid gap-3">
              <LabeledInput
                label="Started at UTC"
                value={editForm.started_at_utc}
                onChange={(value) =>
                  setEditForm({ ...editForm, started_at_utc: value })
                }
              />
              <LabeledInput
                label="Ended at UTC"
                value={editForm.ended_at_utc}
                onChange={(value) =>
                  setEditForm({ ...editForm, ended_at_utc: value })
                }
              />
              <LabeledInput
                label="Page"
                value={editForm.page}
                onChange={(value) => setEditForm({ ...editForm, page: value })}
              />
              <div className="flex flex-col gap-2">
                <Label>Activity</Label>
                <Select
                  value={editForm.activity_category}
                  onValueChange={(value) =>
                    setEditForm({ ...editForm, activity_category: value })
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="editing">editing</SelectItem>
                      <SelectItem value="playback">playback</SelectItem>
                      <SelectItem value="rendering">rendering</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedSession(null)}>
              Cancel
            </Button>
            <Button onClick={saveSession}>
              <SaveIcon data-icon="inline-start" />
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  )
}

function StatusBadge({ value }: { value: string }) {
  const variant = value === "connected" ? "secondary" : "destructive"
  return <Badge variant={variant}>{value}</Badge>
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-2xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border p-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium">{value}</dd>
    </div>
  )
}

function EmptyRow({ columns }: { columns: number }) {
  return (
    <TableRow>
      <TableCell
        colSpan={columns}
        className="h-24 text-center text-muted-foreground"
      >
        No rows
      </TableCell>
    </TableRow>
  )
}

function LabeledInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  const id = label.toLowerCase().replaceAll(" ", "-")
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

function shortDate(value: string) {
  return value.replace("T", " ").replace("Z", "")
}

function duration(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

export default App
