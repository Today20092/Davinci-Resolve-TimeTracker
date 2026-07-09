# Resolve Time Tracker

Resolve Time Tracker is an MIT-licensed, open-source time tracker for DaVinci Resolve Studio. It tracks billable editing time per Resolve project while avoiding the classic mistake: counting time after the editor has walked away.

## Install

Resolve Time Tracker installs as a DaVinci Resolve Scripts-menu tool. After install, open Resolve and run:

```text
Workspace > Scripts > ResolveTimeTrackerMenu
```

### Windows

From PowerShell in this checkout:

```powershell
.\install.ps1
```

If you do not have the checkout yet, clone or download this repository first.
The installer also builds the Electron companion UI, so Node.js/npm must be available.

### macOS

From Terminal in this checkout:

```sh
sh install.sh
```

### Linux

From Terminal in this checkout:

```sh
sh install.sh
```

For Linux activity detection, install `xprintidle` and `xdotool` with your distro package manager. Without them, the tracker can still run, but it falls back to always-active tracking.

### Update

From this checkout:

```sh
git pull
```

Then rerun the platform installer:

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
- Creates or reuses the project `.venv`.
- Installs and builds the Electron companion UI from `frontend/`.
- Installs `ResolveTimeTrackerMenu.py` into Resolve's Scripts/Utility folder.
- Verifies the Resolve menu script points at this checkout.

## Development

This project targets Python because DaVinci Resolve exposes Python scripting.

```powershell
uv sync
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
