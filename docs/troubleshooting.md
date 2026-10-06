# Troubleshooting

## ResolveTimeTrackerMenu is missing

Restart DaVinci Resolve after installation, then check **Workspace > Scripts**. Rerun the installer if the item is still missing; it verifies the installed menu script before reporting success.

## The tracker is disconnected

Close the dashboard, then reopen it. To start or reattach tracking, use **DaVinci Resolve + Time Tracker** or **Workspace > Scripts > ResolveTimeTrackerMenu**. The dashboard alone opens saved data without starting tracking.

The runtime selects an available localhost port and publishes its endpoint in `tracker.runtime.json` beside `tracker.sqlite3`. There is no fixed port `8765` to configure. The dashboard connects to the runtime for its database.

## Resolve is open but time is not increasing

The timer only counts when a project is open and one of these conditions is true:

- Resolve is the foreground application and the computer is not idle.
- Resolve is rendering or exporting.

Check the dashboard's tracking status and confirm tracking is resumed. If you opened Resolve through its ordinary shortcut, attach tracking from its Scripts menu. Switching applications, minimizing Resolve, becoming idle, or manually pausing tracking stops billable time.

## The tracker still runs after the dashboard closes

Closing the dashboard exits Electron. The headless runtime continues recording while the tracked Resolve session is open. Close Resolve too when you want the runtime to exit. If Resolve closes first, the dashboard can still show saved data until you close it.

No tracker starts at login or waits for future Resolve sessions. Rerun the installer to remove legacy tracker startup entries left by an older installation.

## The dashboard says it is not built

Rerun the installer to build the dashboard and install its dependencies. Ordinary launches start the prebuilt Electron app directly. Only development mode uses pnpm to start Vite and Electron.

## Linux counts time while idle

Install `xprintidle` and `xdotool` with the distribution package manager. Without them, the tracker cannot reliably detect idle time or the foreground window and falls back to always-active tracking.

## The installer reports a missing prerequisite

The installer supplies Python 3.13 and `uv`. Git and Node.js with pnpm must be installed first. The pnpm version is pinned in `frontend/package.json`:

- [Install Git](https://git-scm.com/downloads)
- [Install Node.js LTS](https://nodejs.org/en/download)
- [Install pnpm](https://pnpm.io/installation)

Rerun the same installer afterward.

## Find or back up tracked time

The database is a single local file named `tracker.sqlite3`:

```text
Windows: %LOCALAPPDATA%\ResolveTimeTracker\tracker.sqlite3
macOS: ~/Library/Application Support/ResolveTimeTracker/tracker.sqlite3
Linux: $XDG_DATA_HOME/ResolveTimeTracker/tracker.sqlite3 or ~/.local/share/ResolveTimeTracker/tracker.sqlite3
```

Close Resolve and the dashboard before copying or restoring this file.

## Get more diagnostic information

In the desktop app, open **Settings > Support report**, then choose **Copy
report** or **Save report**. Paste or attach the result when opening a GitHub
issue. Review it before sharing; the generated report excludes Resolve project
names and tracking history.

Run tracking from a terminal to keep startup errors visible:

```powershell
uv run --python 3.13 scripts/ResolveTimeTracker.py --tracked-launch
```

When reporting a problem, include the operating system, Resolve version, installation method, dashboard tracking status, and terminal error. Do not upload `tracker.sqlite3` unless you intend to share project names and timing history.

Automated performance checks use synthetic activity and lifecycle scenarios. For a real-session performance problem, also report whether Resolve and the dashboard were open and what Task Manager showed for the tracker processes.

## Still stuck?

[Open a GitHub issue](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues) with the diagnostic information above.
