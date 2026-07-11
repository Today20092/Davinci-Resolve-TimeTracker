import { useEffect, useMemo, useState } from "react"
import { Bar, BarChart, Cell, LabelList, XAxis, YAxis } from "recharts"
import {
  IconDeviceFloppy,
  IconDownload,
  IconFolderOpen,
  IconPencil,
  IconPlayerPause,
  IconPlayerPlay,
  IconPrinter,
  IconRefresh,
  IconSelector,
  IconSortAscending,
  IconSortDescending,
} from "@tabler/icons-react"

import {
  createSidecarClient,
  formatSidecarError,
  type PdfExportOptions,
  type ProjectSummary,
  type Session,
  type SessionUpdate,
  type Settings,
  type Status,
} from "@/lib/api"
import {
  currentProjectDashboard,
  displayPage,
  projectExportSummary,
} from "@/lib/dashboard"
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
import { Checkbox } from "@/components/ui/checkbox"
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
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

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
  page1: { color: "var(--chart-1)" },
  page2: { color: "var(--chart-2)" },
  page3: { color: "var(--chart-3)" },
  page4: { color: "var(--chart-4)" },
  page5: { color: "var(--chart-5)" },
} satisfies ChartConfig

const pageChartColors = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

const activityChartConfig = {
  editing: { label: "Editing", color: "var(--chart-2)" },
  rendering: { label: "Rendering", color: "var(--chart-4)" },
} satisfies ChartConfig

const defaultPdfOptions = {
  show_totals: true,
  show_page_chart: true,
  show_activity_chart: true,
  show_recent_activity: true,
}

function SortHead({
  label,
  direction,
  onClick,
}: {
  label: string
  direction?: "ascending" | "descending"
  onClick: () => void
}) {
  const Icon = direction === "ascending"
    ? IconSortAscending
    : direction === "descending"
      ? IconSortDescending
      : IconSelector
  return (
    <TableHead aria-sort={direction ?? "none"}>
      <Button variant="ghost" className="-ml-3" onClick={onClick}>
        {label}<Icon />
      </Button>
    </TableHead>
  )
}

function App() {
  const [status, setStatus] = useState<Status>(emptyStatus)
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [editForm, setEditForm] = useState<SessionUpdate | null>(null)
  const [idleMinutes, setIdleMinutes] = useState("5")
  const [pdfOptions, setPdfOptions] = useState(defaultPdfOptions)
  const [theme, setTheme] = useState(() => localStorage.theme || "light")
  const [error, setError] = useState<string | null>(null)
  const [sessionSort, setSessionSort] = useState<{
    key: keyof Session
    direction: "ascending" | "descending"
  } | null>(null)

  const sortedSessions = useMemo(() => {
    if (!sessionSort) return sessions
    const direction = sessionSort.direction === "ascending" ? 1 : -1
    return [...sessions].sort((a, b) =>
      String(a[sessionSort.key]).localeCompare(String(b[sessionSort.key]), undefined, {
        numeric: true,
      }) * direction
    )
  }, [sessions, sessionSort])

  function sortSessions(key: keyof Session) {
    setSessionSort((current) => ({
      key,
      direction:
        current?.key === key && current.direction === "ascending"
          ? "descending"
          : "ascending",
    }))
  }

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
  const pageDonutData = pageChartData.map((item, index) => ({
    ...item,
    fill: pageChartColors[index % pageChartColors.length],
  }))
  const activityChartData = [
    {
      activity: "editing",
      label: "Editing",
      seconds: projectDashboard.editingSeconds,
      fill: "var(--color-editing)",
    },
    {
      activity: "rendering",
      label: "Rendering",
      seconds: projectDashboard.renderingSeconds,
      fill: "var(--color-rendering)",
    },
  ].filter((item) => item.seconds > 0)
  const exportSummary = projectExportSummary(projectDashboard, sessions)

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

  async function exportPdf() {
    if (!projectDashboard.project) return
    try {
      const filename = `${projectDashboard.project.replaceAll(" ", "-")}-time-report.pdf`
      if (window.desktop) {
        await window.desktop.exportPdf(filename)
        setError(null)
        return
      }
      const options: PdfExportOptions = {
        project_name: projectDashboard.project,
        ...pdfOptions,
      }
      const blob = await sidecar.exportPdf(options)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
      setError(null)
    } catch (caught) {
      setError(formatSidecarError(caught))
    }
  }

  function setPdfSection(section: keyof typeof pdfOptions, checked: boolean) {
    setPdfOptions((options) => ({ ...options, [section]: checked }))
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
              <InfoBadge
                label="Page"
                value={displayPage(status.page, status.state)}
              />
              {isLive && (
                <InfoBadge label="Session" value={status.active_elapsed} />
              )}
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
            <TabsTrigger value="export">Export</TabsTrigger>
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
                      {projectDashboard.sessionCount} tracked sessions
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {pageChartData.length === 0 ? (
                      <ChartEmpty />
                    ) : (
                      <ChartContainer
                        config={pageChartConfig}
                        className="mx-auto h-72 max-w-3xl"
                        initialDimension={{ width: 800, height: 256 }}
                      >
                        <BarChart
                          accessibilityLayer
                          data={pageDonutData}
                          layout="vertical"
                          barCategoryGap={12}
                          margin={{ left: 0, right: 56 }}
                        >
                          <XAxis dataKey="seconds" hide type="number" />
                          <YAxis
                            dataKey="page"
                            axisLine={false}
                            tickLine={false}
                            type="category"
                            width={96}
                          />
                          <ChartTooltip
                            content={
                              <ChartTooltipContent
                                formatter={(value, _name, item) => (
                                  <div className="flex min-w-32 items-center gap-2">
                                    <span
                                      className="size-2.5 shrink-0 rounded-sm"
                                      style={{
                                        backgroundColor: item.payload.fill,
                                      }}
                                    />
                                    <span className="capitalize">
                                      {item.payload.page}
                                    </span>
                                    <span className="ml-auto font-mono font-medium">
                                      {duration(Number(value))}
                                    </span>
                                  </div>
                                )}
                              />
                            }
                          />
                          <Bar dataKey="seconds" radius={4}>
                            {pageDonutData.map((item) => (
                              <Cell key={item.page} fill={item.fill} />
                            ))}
                            <LabelList
                              dataKey="seconds"
                              formatter={(value) => duration(Number(value))}
                              position="right"
                            />
                          </Bar>
                        </BarChart>
                      </ChartContainer>
                    )}
                    {pageDonutData.length > 0 && (
                      <div className="mx-auto mt-3 grid max-w-3xl grid-cols-[repeat(auto-fit,minmax(13rem,1fr))] gap-2">
                        {pageDonutData.map((item) => (
                          <div
                            key={item.page}
                            className="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
                          >
                            <span className="flex min-w-0 items-center gap-2">
                              <span
                                className="size-2.5 shrink-0 rounded-sm"
                                style={{ backgroundColor: item.fill }}
                              />
                              <span className="capitalize">
                                {item.page}
                              </span>
                            </span>
                            <span className="font-mono text-xs text-muted-foreground">
                              {duration(item.seconds)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Recent page activity</CardTitle>
                    <CardDescription>
                      Latest tracked sessions for this project.
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
                  {sessions.length} saved tracked sessions
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
                      {[["Project", "project_name"], ["Start", "started_at_utc"], ["End", "ended_at_utc"], ["Duration", "duration_seconds"], ["Page", "page"], ["Activity", "activity_category"]].map(([label, key]) => (
                        <SortHead
                          key={key}
                          label={label}
                          direction={sessionSort?.key === key ? sessionSort.direction : undefined}
                          onClick={() => sortSessions(key as keyof Session)}
                        />
                      ))}
                      <TableHead className="w-12">
                        <span className="sr-only">Edit</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedSessions.map((session) => (
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
                        <TableCell>
                          {displayPage(session.page, session.activity_category)}
                        </TableCell>
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

          <TabsContent value="export">
            {!exportSummary ? (
              <Empty className="min-h-96 rounded-lg border">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <IconDownload />
                  </EmptyMedia>
                  <EmptyTitle>No project to export</EmptyTitle>
                  <EmptyDescription>
                    Open a Resolve project before creating a client report.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <section className="export-report flex flex-col gap-4">
                <Card className="no-print">
                  <CardHeader>
                    <CardTitle>PDF export options</CardTitle>
                    <CardDescription>
                      Choose what appears in the client report.
                    </CardDescription>
                    <CardAction>
                      <Button onClick={exportPdf}>
                        <IconDownload data-icon="inline-start" />
                        Export PDF
                      </Button>
                    </CardAction>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      <PdfOption
                        checked={pdfOptions.show_totals}
                        id="pdf-show-totals"
                        label="Summary totals"
                        onCheckedChange={(checked) =>
                          setPdfSection("show_totals", checked)
                        }
                      />
                      <PdfOption
                        checked={pdfOptions.show_page_chart}
                        id="pdf-show-page-chart"
                        label="Time by page"
                        onCheckedChange={(checked) =>
                          setPdfSection("show_page_chart", checked)
                        }
                      />
                      <PdfOption
                        checked={pdfOptions.show_activity_chart}
                        id="pdf-show-activity-chart"
                        label="Activity mix"
                        onCheckedChange={(checked) =>
                          setPdfSection("show_activity_chart", checked)
                        }
                      />
                      <PdfOption
                        checked={pdfOptions.show_recent_activity}
                        id="pdf-show-recent-activity"
                        label="Recent activity"
                        onCheckedChange={(checked) =>
                          setPdfSection("show_recent_activity", checked)
                        }
                      />
                    </div>
                  </CardContent>
                </Card>

                <div className="no-print flex justify-end">
                  <Button variant="outline" onClick={() => window.print()}>
                    <IconPrinter data-icon="inline-start" />
                    Print Preview
                  </Button>
                </div>

                <div className="rounded-lg border bg-card p-6 text-card-foreground">
                  <div className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">
                        Resolve Time Report
                      </p>
                      <h2 className="mt-1 text-3xl font-semibold">
                        {exportSummary.project}
                      </h2>
                    </div>
                    <div className="text-sm text-muted-foreground sm:text-right">
                      <p>Generated {exportSummary.generatedAt}</p>
                      <p>{exportSummary.dateRange}</p>
                    </div>
                  </div>

                  {pdfOptions.show_totals && (
                    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      <Metric
                        title="Total tracked"
                        value={duration(projectDashboard.trackedSeconds)}
                      />
                      <Metric
                        title="Editing"
                        value={duration(projectDashboard.editingSeconds)}
                      />
                      <Metric
                        title="Rendering"
                        value={duration(projectDashboard.renderingSeconds)}
                      />
                      <Metric
                        title="Tracked sessions"
                        value={String(projectDashboard.sessionCount)}
                      />
                    </div>
                  )}

                  {(pdfOptions.show_page_chart ||
                    pdfOptions.show_activity_chart) && (
                    <div className="mt-5 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
                      {pdfOptions.show_page_chart && (
                        <Card>
                          <CardHeader>
                            <CardTitle>Time by page</CardTitle>
                            <CardDescription>
                              DaVinci Resolve page activity
                            </CardDescription>
                          </CardHeader>
                          <CardContent>
                            {pageChartData.length === 0 ? (
                              <ChartEmpty />
                            ) : (
                              <ChartContainer
                                config={pageChartConfig}
                                className="h-72 w-full"
                                initialDimension={{ width: 800, height: 288 }}
                              >
                                <BarChart
                                  accessibilityLayer
                                  data={pageChartData}
                                  layout="vertical"
                                  barCategoryGap={12}
                                  margin={{ left: 0, right: 56 }}
                                >
                                  <XAxis dataKey="seconds" hide type="number" />
                                  <YAxis
                                    dataKey="page"
                                    axisLine={false}
                                    tickLine={false}
                                    type="category"
                                    width={72}
                                  />
                                  <Bar
                                    dataKey="seconds"
                                    fill="var(--color-seconds)"
                                    radius={4}
                                  >
                                    <LabelList
                                      dataKey="seconds"
                                      formatter={(value) =>
                                        duration(Number(value))
                                      }
                                      position="right"
                                    />
                                  </Bar>
                                </BarChart>
                              </ChartContainer>
                            )}
                          </CardContent>
                        </Card>
                      )}

                      {pdfOptions.show_activity_chart && (
                        <Card>
                          <CardHeader>
                            <CardTitle>Activity mix</CardTitle>
                            <CardDescription>
                              Editing and rendering time
                            </CardDescription>
                          </CardHeader>
                          <CardContent>
                            {activityChartData.length === 0 ? (
                              <ChartEmpty />
                            ) : (
                              <ChartContainer
                                config={activityChartConfig}
                                className="h-72 w-full"
                                initialDimension={{ width: 360, height: 288 }}
                              >
                                <BarChart
                                  accessibilityLayer
                                  data={activityChartData}
                                  margin={{ top: 24, right: 8, left: 8 }}
                                >
                                  <XAxis
                                    dataKey="label"
                                    axisLine={false}
                                    tickLine={false}
                                  />
                                  <YAxis hide type="number" />
                                  <ChartTooltip
                                    content={
                                      <ChartTooltipContent
                                        hideLabel
                                        formatter={(value, _name, item) => (
                                          <div className="flex min-w-32 items-center gap-2">
                                            <span
                                              className="size-2.5 shrink-0 rounded-sm"
                                              style={{
                                                backgroundColor:
                                                  item.payload.fill,
                                              }}
                                            />
                                            <span>{item.payload.label}</span>
                                            <span className="ml-auto font-mono font-medium">
                                              {duration(Number(value))}
                                            </span>
                                          </div>
                                        )}
                                      />
                                    }
                                  />
                                  <Bar dataKey="seconds" radius={4}>
                                    {activityChartData.map((item) => (
                                      <Cell
                                        key={item.activity}
                                        fill={item.fill}
                                      />
                                    ))}
                                    <LabelList
                                      dataKey="seconds"
                                      formatter={(value) =>
                                        duration(Number(value))
                                      }
                                      position="top"
                                    />
                                  </Bar>
                                </BarChart>
                              </ChartContainer>
                            )}
                          </CardContent>
                        </Card>
                      )}
                    </div>
                  )}

                  {pdfOptions.show_recent_activity && (
                    <div className="mt-5">
                      <Card>
                        <CardHeader>
                          <CardTitle>Recent page activity</CardTitle>
                          <CardDescription>
                            Latest tracked rows for this project.
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <ActivityTable
                            sessions={projectDashboard.recentSessions}
                          />
                        </CardContent>
                      </Card>
                    </div>
                  )}

                  {!Object.values(pdfOptions).some(Boolean) && (
                    <div className="mt-5">
                      <Card>
                        <CardHeader>
                          <CardTitle>No sections selected</CardTitle>
                          <CardDescription>
                            Select at least one option for a useful report.
                          </CardDescription>
                        </CardHeader>
                      </Card>
                    </div>
                  )}
                </div>
              </section>
            )}
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
                  <ToggleGroup
                    id="theme"
                    type="single"
                    value={theme}
                    variant="outline"
                    spacing={0}
                    className="w-full"
                    onValueChange={(value) => value && setTheme(value)}
                  >
                    <ToggleGroupItem className="flex-1" value="light">
                      Light
                    </ToggleGroupItem>
                    <ToggleGroupItem className="flex-1" value="dark">
                      Dark
                    </ToggleGroupItem>
                  </ToggleGroup>
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

function InfoBadge({ label, value }: { label: string; value: string }) {
  return (
    <Badge variant="outline" className="font-normal capitalize">
      <span className="text-muted-foreground">{label}</span>
      {value}
    </Badge>
  )
}

function PdfOption({
  checked,
  id,
  label,
  onCheckedChange,
}: {
  checked: boolean
  id: string
  label: string
  onCheckedChange: (checked: boolean) => void
}) {
  return (
    <label
      className="flex items-center gap-2 rounded-lg border p-3 text-sm font-medium"
      htmlFor={id}
    >
      <Checkbox
        checked={checked}
        id={id}
        onCheckedChange={(value) => onCheckedChange(value === true)}
      />
      {label}
    </label>
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
            <TableCell>
              {displayPage(session.page, session.activity_category)}
            </TableCell>
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
  const date = new Date(
    normalized.endsWith("Z") ? normalized : `${normalized}Z`
  )
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
