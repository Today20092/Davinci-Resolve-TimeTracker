# Troubleshooting

## ResolveTimeTrackerMenu is missing

Restart DaVinci Resolve after installation, then check **Workspace > Scripts**. Rerun the installer if the item is still missing; it verifies the installed menu script before reporting success.

## The tracker is disconnected

Quit Resolve Time Tracker from its system-tray menu, then start it again from Resolve. Only one desktop app instance should run. If port `8765` is occupied by an older tracker, the current app selects another local port automatically.

## Resolve is open but time is not increasing

The timer only counts when a project is open and one of these conditions is true:

- Resolve is the foreground application and the computer is not idle.
- Resolve is rendering or exporting.

Check that tracking is resumed and the tray is green. Switching applications, minimizing Resolve, becoming idle, or manually pausing tracking stops billable time.

## Linux counts time while idle

Install `xprintidle` and `xdotool` with the distribution package manager. Without them, the tracker cannot reliably detect idle time or the foreground window and falls back to always-active tracking.

## The installer reports a missing prerequisite

The installer supplies Python 3.13 and `uv`. Git and Node.js with npm must be installed first:

- [Install Git](https://git-scm.com/downloads)
- [Install Node.js LTS](https://nodejs.org/en/download)

Rerun the same installer afterward.

## Find or back up tracked time

The database is a single local file named `tracker.sqlite3`:

```text
Windows: %LOCALAPPDATA%\ResolveTimeTracker\tracker.sqlite3
macOS: ~/Library/Application Support/ResolveTimeTracker/tracker.sqlite3
Linux: $XDG_DATA_HOME/ResolveTimeTracker/tracker.sqlite3 or ~/.local/share/ResolveTimeTracker/tracker.sqlite3
```

Quit the tracker before copying or restoring this file.

## Get more diagnostic information

Run the tracker from a terminal to keep startup errors visible:

```powershell
uv run --python 3.13 scripts/ResolveTimeTracker.py --companion
```

When reporting a problem, include the operating system, Resolve version, installation method, tray color, and terminal error. Do not upload `tracker.sqlite3` unless you intend to share project names and timing history.

## Still stuck?

[Open a GitHub issue](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues) with the diagnostic information above.
