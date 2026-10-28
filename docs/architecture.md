# Architecture

[Back to the README](../README.md) · [Development guide](development.md)

### Diagram Key

Both diagrams use the same visual language:

- **Orange:** where the user starts an action.
- **Blue:** DaVinci Resolve.
- **Green:** the desktop app and results visible to the user.
- **Purple:** background work performed by the tracker.
- **Pink:** data stored privately on the computer.
- **Rectangle:** an action or part of the tracker; **diamond:** a choice; **cylinder:** stored data; **dotted line:** an explanatory note rather than a runtime step.

### Runtime Flow

How Resolve, the desktop companion, the local Python sidecar, and local storage talk to each other while the tracker is running.

```mermaid
flowchart TD
  Menu["Tracked Resolve shortcut<br/>or Resolve's Scripts menu"] --> Tracker["Headless runtime<br/>tracks this Resolve session"]
  Dashboard["You open the dashboard"] --> App["Desktop dashboard<br/>saved data without tracking by default"]
  App <-->|Local API| Tracker

  Resolve["DaVinci Resolve<br/>project, page, and render status"] --> Tracker
  Activity["Your computer<br/>active, idle, or Resolve in background"] --> Tracker

  Tracker --> Decision{"Should this time count?"}
  Decision -->|Yes| Database[("Private local database<br/>projects, time, and settings")]
  Decision -->|No| Wait["Wait without adding time"]
  Wait --> Tracker

  Database --> App
  App --> Reports["Dashboard, CSV,<br/>and PDF reports"]

  Note["Dashboard close exits Electron.<br/>Runtime exits when the tracked Resolve session and dashboard have closed."] -.-> App

  classDef user fill:#fff7ed,stroke:#f97316,color:#7c2d12
  classDef resolve fill:#eff6ff,stroke:#2563eb,color:#1e3a8a
  classDef desktop fill:#f0fdf4,stroke:#16a34a,color:#14532d
  classDef backend fill:#eef2ff,stroke:#4f46e5,color:#312e81
  classDef data fill:#fdf2f8,stroke:#db2777,color:#831843

  class Menu,Dashboard user
  class Resolve resolve
  class App,Reports desktop
  class Tracker,Decision,Activity,Wait backend
  class Database data
```

### Install Flow

What the one-file installer prepares before the menu item appears inside DaVinci Resolve.

```mermaid
flowchart TD
  Download["Download and run<br/>the installer for your computer"]
  Download --> Prepare["The installer prepares<br/>the tracker and desktop app"]
  Prepare --> Menu["The tracker is added to<br/>Resolve's Scripts menu"]
  Prepare --> Shortcuts["Windows tracking and dashboard shortcuts<br/>replace legacy login-startup entries"]
  Shortcuts --> Ready["Installation complete<br/>nothing runs at sign-in"]
  Menu --> Ready
  Ready --> Use["Use the tracked Resolve shortcut<br/>or attach from Resolve's Scripts menu"]

  classDef bootstrap fill:#fff7ed,stroke:#f97316,color:#7c2d12
  classDef setup fill:#eef2ff,stroke:#4f46e5,color:#312e81
  classDef resolve fill:#eff6ff,stroke:#2563eb,color:#1e3a8a

  class Download bootstrap
  class Prepare setup
  class Menu,Shortcuts,Ready,Use resolve
```

| Area | Files | Responsibility |
| --- | --- | --- |
| Plugin entry | `scripts/ResolveTimeTracker.py` | Opens the built dashboard by default; `--tracked-launch` starts or attaches Resolve tracking, and `--api` attaches a dashboard owner to the managed runtime. |
| Install path | `install.py`, `install.ps1`, `install.sh`, `scripts/install_resolve_menu.py` | Prepares Python and frontend dependencies, then installs the Resolve Scripts-menu launcher. |
| Interface | `frontend/` | Electron owns the dashboard window and desktop PDF printing and exits when the window closes; React, Vite, Tailwind, and shadcn/ui render the dashboard. |
| Runtime lifecycle | `src/resolve_time_tracker/runtime_host.py`, `src/resolve_time_tracker/tracked_launch.py` | Shares one runtime per database while a tracked Resolve session or dashboard owns it. Publishes an ephemeral localhost endpoint in the database's `.runtime.json` file. |
| Backend API | `src/resolve_time_tracker/api.py` | FastAPI exposes localhost commands, exports, server-sent invalidations, and the complete dashboard read model consumed by React. |
| Tracking rules | `src/resolve_time_tracker/tracking_engine.py` | Converts Resolve/runtime snapshots into billable Sessions with heartbeats. |
| Resolve adapter | `src/resolve_time_tracker/resolve_bridge.py` | Reads project, Page, render, timeline, idle, and foreground state. |
| Storage | `src/resolve_time_tracker/database.py` | Stores Projects, active Session, closed Sessions, settings, heartbeat recovery, summaries, and CSV output in SQLite. |
