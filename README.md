# Resolve Time Tracker

[![DaVinci Resolve](https://img.shields.io/badge/DaVinci_Resolve-Studio-233A51?style=for-the-badge&logo=davinciresolve&logoColor=white)](https://www.blackmagicdesign.com/products/davinciresolve)
[![Python](https://img.shields.io/badge/Python-3.10--3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-sidecar-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Electron](https://img.shields.io/badge/Electron-desktop-47848F?style=for-the-badge&logo=electron&logoColor=white)](https://www.electronjs.org/)
[![React](https://img.shields.io/badge/React-interface-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![shadcn/ui](https://img.shields.io/badge/shadcn%2Fui-components-000000?style=for-the-badge&logo=shadcnui&logoColor=white)](https://ui.shadcn.com/)
[![SQLite](https://img.shields.io/badge/SQLite-local_storage-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

Resolve Time Tracker is an MIT-licensed, open-source time tracker for DaVinci Resolve Studio. It tracks billable editing time per Resolve project while avoiding the classic mistake: counting time after the editor has walked away.

## Install

Resolve Time Tracker installs as a DaVinci Resolve Scripts-menu tool. After install, open Resolve and run:

```text
Workspace > Scripts > ResolveTimeTrackerMenu
```

### Windows

Download [install.ps1](https://raw.githubusercontent.com/Today20092/Davinci-Resolve-TimeTracker/main/install.ps1), then right-click it and choose **Run with PowerShell**.

If Windows blocks the downloaded script, open PowerShell in your Downloads folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer downloads the project source, installs Python dependencies, builds the companion app, and adds the DaVinci Resolve menu script.

### macOS

Download [install.sh](https://raw.githubusercontent.com/Today20092/Davinci-Resolve-TimeTracker/main/install.sh), then run it from Terminal:

```sh
sh ~/Downloads/install.sh
```

### Linux

Download [install.sh](https://raw.githubusercontent.com/Today20092/Davinci-Resolve-TimeTracker/main/install.sh), then run it from Terminal:

```sh
sh ~/Downloads/install.sh
```

For Linux activity detection, install `xprintidle` and `xdotool` with your distro package manager. Without them, the tracker can still run, but it falls back to always-active tracking.

### Update

Rerun the same installer you downloaded:

```powershell
.\install.ps1
```

```sh
sh install.sh
```

Restart Resolve if it was already open.

## Use

Open Resolve and run:

```text
Workspace > Scripts > ResolveTimeTrackerMenu
```

The companion window shows tracking status, current project, current page, activity category, heartbeat, sessions, settings, and CSV export. Use **Pause Tracking** when you want to stop tracking manually, and **Resume Tracking** when you want it to start again.

CSV export writes closed sessions only. Open active sessions are exported after they close.

## How Tracking Works

- Tracks while Resolve is the foreground app and you are not idle.
- Stops when Resolve is minimized or you switch to another app.
- Keeps tracking during Resolve render/export.
- Stores data locally in SQLite.
- Exports closed sessions to CSV.
- Never records keystrokes, mouse coordinates, screen contents, footage, or media contents.

Default data file:

```text
Windows: %LOCALAPPDATA%\ResolveTimeTracker\tracker.sqlite3
macOS: ~/Library/Application Support/ResolveTimeTracker/tracker.sqlite3
Linux: $XDG_DATA_HOME/ResolveTimeTracker/tracker.sqlite3 or ~/.local/share/ResolveTimeTracker/tracker.sqlite3
```

## Platform Support

- Windows: verified with DaVinci Resolve Studio 21.
- macOS: supported by installer and activity probes, needs real-machine smoke testing.
- Linux: supported by installer and Resolve scripting path; proper idle/focus detection requires `xprintidle` and `xdotool`.

More detail lives in [docs/platform-support.md](docs/platform-support.md).

## Install Details

The platform installer:

- Installs `uv` with Astral's official installer if missing.
- Syncs the project `.venv` with `uv` on Python 3.13.
- Installs and builds the Electron companion UI from `frontend/`.
- Installs `ResolveTimeTrackerMenu.py` into Resolve's Scripts/Utility folder.
- Verifies the Resolve menu script points at this checkout.

## Architecture

```mermaid
flowchart LR
  User["Editor in DaVinci Resolve"] --> Menu["Resolve Scripts menu<br/>ResolveTimeTrackerMenu.py"]
  Menu --> Entry["scripts/ResolveTimeTracker.py<br/>--companion"]
  Entry --> Electron["Electron desktop shell<br/>frontend/electron/main.cjs"]
  Electron --> Sidecar["Python sidecar<br/>FastAPI localhost API"]
  Electron --> React["React dashboard<br/>Vite + shadcn/ui"]
  React <-->|REST + server-sent events| Sidecar
  Sidecar --> Engine["TrackingEngine<br/>billable Session rules"]
  Engine --> Bridge["ResolveBridge<br/>Resolve project, Page, render state"]
  Bridge --> Resolve["DaVinci Resolve scripting API"]
  Engine --> Activity["Activity probe<br/>idle + foreground checks"]
  Engine --> Store["SQLiteStore<br/>Projects, Sessions, settings"]
  React --> Csv["CSV export"]
  Csv --> Store
```

```mermaid
flowchart TD
  Install["install.ps1 / install.sh"] --> Installer["install.py"]
  Installer --> Source["Find or clone source checkout"]
  Installer --> Python["uv sync --python 3.13"]
  Installer --> Frontend["npm ci + npm run build"]
  Installer --> MenuInstall["scripts/install_resolve_menu.py"]
  MenuInstall --> Launcher["Resolve Scripts/Utility<br/>ResolveTimeTrackerMenu.py"]
  Launcher --> Companion["Launch --companion from this checkout"]
```

| Area | Files | Responsibility |
| --- | --- | --- |
| Plugin entry | `scripts/ResolveTimeTracker.py` | Chooses launcher mode: Resolve UI, Electron companion, FastAPI sidecar, or version output. |
| Install path | `install.py`, `install.ps1`, `install.sh`, `scripts/install_resolve_menu.py` | Prepares Python and frontend dependencies, then installs the Resolve Scripts-menu launcher. |
| Interface | `frontend/` | Electron opens the desktop window; React, Vite, Tailwind, and shadcn/ui render status, history, settings, edits, and CSV export. |
| Backend API | `src/resolve_time_tracker/api.py` | FastAPI exposes localhost REST endpoints and server-sent live status events. |
| Tracking rules | `src/resolve_time_tracker/tracking_engine.py` | Converts Resolve/runtime snapshots into billable Sessions with heartbeats. |
| Resolve adapter | `src/resolve_time_tracker/resolve_bridge.py` | Reads project, Page, render, timeline, idle, and foreground state. |
| Storage | `src/resolve_time_tracker/database.py` | Stores Projects, active Session, closed Sessions, settings, heartbeat recovery, summaries, and CSV output in SQLite. |

## Development

This project targets Python because DaVinci Resolve exposes Python scripting.

```powershell
uv sync --python 3.13
uv run ruff format .
uv run ruff check .
uv run --python 3.13 scripts/ResolveTimeTracker.py --version
uv run -m unittest discover -s tests
cd frontend
npm run desktop:dev
```

Useful docs:

- [docs/roadmap.md](docs/roadmap.md)
- [docs/platform-support.md](docs/platform-support.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

## Credits

The project is inspired by Jamie Fenn's DaVinci Resolve time tracker concept and launch video:

- [I Built The Most POWERFUL Tool For Davinci Resolve](https://youtu.be/hPOm9HM6S_o)
- [Jamie Fenn Time Tracker](https://www.jamiefenn.com/p/time-tracker/)

This is an independent open-source implementation. It is not affiliated with, endorsed by, or a copy of Jamie Fenn's commercial product.

## License

MIT. See [LICENSE](LICENSE).
