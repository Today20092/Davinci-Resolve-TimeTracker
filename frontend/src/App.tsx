import { useEffect, useMemo, useState } from "react"
import { Bar, BarChart, LabelList, XAxis, YAxis } from "recharts"
import {
  IconDeviceFloppy,
  IconDownload,
  IconFolderOpen,
  IconPencil,
  IconPlayerPause,
  IconPlayerPlay,
  IconRefresh,
} from "@tabler/icons-react"

import {
  createSidecarClient,
  formatSidecarError,
  type ProjectSummary,
  type Session,
  type SessionUpdate,
  type Settings,
  type Status,
} from "@/lib/api"
import { currentProjectDashboard } from "@/lib/dashboard"
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
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
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

const sidecar = createSidecarClient()
type Dashboard = Awaited<ReturnType<typeof sidecar.loadDashboard>>

const pageChartConfig = {
  seconds: { label: "Tracked time", color: "var(--chart-1)" },
} satisfies ChartConfig

function App() {
  const [status, setStatus] = useState<Status>(emptyStatus)
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [editForm, setEditForm] = useState<SessionUpdate | null>(null)
  const [idleMinutes, setIdleMinutes] = useState("5")
  const [theme, setTheme] = useState(() => localStorage.theme || "light")
  const [error, setError] = useState<string | null>(null)

  function applyDashboard(dashboard: Dashboard) {
    setStatus(dashboard.status)
    setSettings(dashboard.settings)
    setProjects(dashboard.projects)
    setSessions(dashboard.sessions)
    setIdleMinutes(String(dashboard.settings.idle_timeout_minutes))
    setError(null)
  }

  useEffect(() => {
    void sidecar.loadDashboard().then(applyDashboard, (error) => {
      setError(formatSidecarError(error))
    })
    return sidecar.watchDashboard({
      onUpdate: (update) => {
        setStatus(update.status)
        setProjects(update.projects)
        setSessions(update.sessions)
        setError(null)
      },
      onError: (error) => setError(formatSidecarError(error)),
    })
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
    localStorage.theme = theme
  }, [theme])

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

  const projectDashboard = useMemo(
    () => currentProjectDashboard(sessions, status),
    [sessions, status]
  )

  const pageChartData = projectDashboard.pageData

  const projectName =
    status.project === "none" ? "No Resolve project detected" : status.project
  const isLive = status.state === "editing" || status.state === "rendering"

  async function runAction(action: () => Promise<Dashboard>) {
    try {
      applyDashboard(await action())
    } catch (caught) {
      setError(formatSidecarError(caught))
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
    await runAction(() => sidecar.updateSession(selectedSession.id, editForm))
    setSelectedSession(null)
    setEditForm(null)
  }

  async function saveSettings() {
    await runAction(() =>
      sidecar.updateSettings(Math.max(1, Number(idleMinutes) || 1) * 60)
    )
  }

  function exportCsv() {
    window.location.href = sidecar.csvExportUrl()
  }

  return (
    <main className="min-h-svh bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 lg:p-6">
        <header className="flex flex-col gap-3 border-b pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="truncate text-xl font-semibold">{projectName}</h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <StatusBadge value={status.connection} />
              <TrackingBadge live={isLive} enabled={status.tracking_enabled} />
              <span>Page: {status.page}</span>
              <span>Elapsed: {status.active_elapsed}</span>
              <span>Signal: {status.heartbeat}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() =>
                runAction(() => sidecar.setTracking(!status.tracking_enabled))
              }
            >
              {status.tracking_enabled ? (
                <IconPlayerPause data-icon="inline-start" />
              ) : (
                <IconPlayerPlay data-icon="inline-start" />
              )}
              {status.tracking_enabled ? "Pause Tracking" : "Resume Tracking"}
            </Button>
            <Button
              variant="outline"
              size="icon"
              aria-label="Refresh"
              onClick={() => runAction(() => sidecar.refresh())}
            >
              <IconRefresh />
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
            <TabsTrigger value="sessions">Page activity</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="flex flex-col gap-4">
            {!projectDashboard.project ? (
              <Empty className="min-h-96 rounded-lg border">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <IconFolderOpen />
                  </EmptyMedia>
                  <EmptyTitle>No Resolve project detected</EmptyTitle>
                  <EmptyDescription>
                    Open a project in Resolve and the dashboard will switch to
                    its tracked time.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                  <Metric
                    title="Tracked today"
                    value={duration(projectDashboard.todaySeconds)}
                  />
                  <Metric
                    title="Project total"
                    value={duration(projectDashboard.trackedSeconds)}
                  />
                  <Metric
                    title="Render time"
                    value={duration(projectDashboard.renderingSeconds)}
                  />
                  <Metric
                    title="Last activity"
                    value={friendlyDateTime(projectDashboard.lastActivity)}
                  />
                </div>
                <Card>
                  <CardHeader>
                    <CardTitle>Time by page</CardTitle>
                    <CardDescription>
                      {projectDashboard.project} -{" "}
                      {projectDashboard.sessionCount} page activity rows
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {pageChartData.length === 0 ? (
                      <ChartEmpty />
                    ) : (
                      <ChartContainer
                        config={pageChartConfig}
                        className="h-64 w-full"
                        initialDimension={{ width: 800, height: 256 }}
                      >
                        <BarChart
                          accessibilityLayer
                          data={pageChartData}
                          layout="vertical"
                          barCategoryGap={12}
                          margin={{ left: 0, right: 48 }}
                        >
                          <XAxis dataKey="seconds" hide type="number" />
                          <YAxis
                            dataKey="page"
                            axisLine={false}
                            tickLine={false}
                            type="category"
                            width={64}
                          />
                          <ChartTooltip
                            content={
                              <ChartTooltipContent
                                formatter={(value) => duration(Number(value))}
                              />
                            }
                          />
                          <Bar
                            dataKey="seconds"
                            fill="var(--color-seconds)"
                            radius={4}
                          >
                            <LabelList
                              dataKey="seconds"
                              formatter={(value) => duration(Number(value))}
                              position="right"
                            />
                          </Bar>
                        </BarChart>
                      </ChartContainer>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Recent page activity</CardTitle>
                    <CardDescription>
                      Latest rows saved for this project.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ActivityTable sessions={projectDashboard.recentSessions} />
                  </CardContent>
                </Card>
              </>
            )}
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
                <CardTitle>Page activity</CardTitle>
                <CardDescription>
                  {sessions.length} saved page activity rows
                </CardDescription>
                <CardAction>
                  <Button variant="outline" onClick={exportCsv}>
                    <IconDownload data-icon="inline-start" />
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
                          {friendlyDateTime(session.started_at_utc)}
                        </TableCell>
                        <TableCell>
                          {friendlyDateTime(session.ended_at_utc)}
                        </TableCell>
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
                            <IconPencil />
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
                      <IconDeviceFloppy data-icon="inline-start" />
                      Save
                    </Button>
                  </div>
                  <Label htmlFor="theme">Theme</Label>
                  <Select value={theme} onValueChange={setTheme}>
                    <SelectTrigger id="theme" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="light">Light</SelectItem>
                        <SelectItem value="dark">Dark</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
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
            <DialogTitle>Edit page activity</DialogTitle>
            <DialogDescription>
              {selectedSession?.project_name ?? "Session"}
            </DialogDescription>
          </DialogHeader>
          {editForm && (
            <div className="grid gap-3">
              <LabeledInput
                label="Started"
                value={editForm.started_at_utc}
                onChange={(value) =>
                  setEditForm({ ...editForm, started_at_utc: value })
                }
              />
              <LabeledInput
                label="Ended"
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
              <IconDeviceFloppy data-icon="inline-start" />
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  )
}

function StatusBadge({ value }: { value: string }) {
  const connected = value === "connected"
  return (
    <Badge
      className={
        connected
          ? "border-emerald-200 bg-emerald-100 text-emerald-800"
          : "border-red-200 bg-red-100 text-red-800"
      }
    >
      {connected ? "Connected" : "Not connected"}
    </Badge>
  )
}

function TrackingBadge({ live, enabled }: { live: boolean; enabled: boolean }) {
  if (!enabled) {
    return (
      <Badge className="border-amber-200 bg-amber-100 text-amber-800">
        Tracking paused
      </Badge>
    )
  }
  return (
    <Badge
      className={
        live
          ? "border-sky-200 bg-sky-100 text-sky-800"
          : "border-zinc-200 bg-zinc-100 text-zinc-700"
      }
    >
      {live ? "Tracking now" : "Waiting for activity"}
    </Badge>
  )
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

function ActivityTable({ sessions }: { sessions: Session[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Start</TableHead>
          <TableHead>Duration</TableHead>
          <TableHead>Page</TableHead>
          <TableHead>Activity</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sessions.map((session) => (
          <TableRow key={session.id}>
            <TableCell>{friendlyDateTime(session.started_at_utc)}</TableCell>
            <TableCell>{session.duration}</TableCell>
            <TableCell>{session.page}</TableCell>
            <TableCell>{session.activity_category}</TableCell>
          </TableRow>
        ))}
        {sessions.length === 0 && <EmptyRow columns={4} />}
      </TableBody>
    </Table>
  )
}

function ChartEmpty() {
  return (
    <Empty className="min-h-72">
      <EmptyHeader>
        <EmptyTitle>No tracked time yet</EmptyTitle>
        <EmptyDescription>
          Time will appear here once tracking records this project.
        </EmptyDescription>
      </EmptyHeader>
    </Empty>
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

function friendlyDateTime(value: string) {
  if (!value || value === "none") return "None yet"
  const normalized = value.includes("T") ? value : value.replace(" ", "T")
  const date = new Date(normalized.endsWith("Z") ? normalized : `${normalized}Z`)
  if (Number.isNaN(date.getTime())) return shortDate(value).split(".")[0]
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

function duration(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`
}

export default App
