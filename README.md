# Resolve Time Tracker

Resolve Time Tracker is an MIT-licensed, open-source time tracker for DaVinci Resolve Free. It is designed to track billable editing time per Resolve project while avoiding the classic mistake: counting time after the editor has walked away.

The project is inspired by Jamie Fenn's DaVinci Resolve time tracker concept and launch video:

- [I Built The Most POWERFUL Tool For Davinci Resolve](https://youtu.be/hPOm9HM6S_o)
- [Jamie Fenn Time Tracker](https://www.jamiefenn.com/p/time-tracker/)

This is an independent open-source implementation. It is not affiliated with, endorsed by, or a copy of Jamie Fenn's commercial product.

## Goals

- Work with DaVinci Resolve Free.
- Track active editing time by Resolve project.
- Pause tracking when the user is idle or Resolve is unfocused.
- Continue tracking during render/export.
- Store all data locally in SQLite.
- Export CSV for billing.
- Avoid screen capture, key logging, mouse-coordinate logging, or media inspection.
- Stay lightweight enough to run beside an editor all day.

## MVP Scope

Phase 0 proves what the official DaVinci Resolve scripting API can actually expose:

- Current Resolve project
- Project and timeline changes
- Current page, where supported
- Render/export state
- Playback state
- Windows idle detection strategy

Phase 1 builds the smallest useful tracker:

- Project tracking
- Configurable idle timeout
- Render tracking
- Session heartbeat and crash recovery
- SQLite storage
- CSV export
- Basic Resolve-launched UI or companion flow that works with Resolve Free

## Architecture

The code is organized around a Session Engine. Platform-specific pieces stay behind small interfaces so Windows can ship first without blocking future macOS or Linux support.

```text
src/resolve_time_tracker/
  resolve_bridge/      Resolve scripting API boundary
  activity_tracker/    Focus, idle, playback, and render activity signals
  session_engine/      Event-to-session state machine
  database/            SQLite schema and persistence
  exporter/            CSV export
  settings/            User settings
  ui/                  Resolve-launched UI or companion surface
```

Core events:

- `ProjectOpened`
- `ProjectChanged`
- `PageChanged`
- `RenderingStarted`
- `RenderingFinished`
- `IdleStarted`
- `IdleEnded`
- `ResolveClosed`

## Privacy

Resolve Time Tracker only tracks timing and activity state. It must never:

- Record keystrokes
- Record mouse coordinates
- Capture the screen
- Inspect footage
- Inspect media contents
- Send project data to a cloud service

## Current Status

This repository is at planning and feasibility stage. Current research notes:

```text
docs/research/resolve-scripting-feasibility.md
```

## Development

This project targets Python because DaVinci Resolve exposes Python scripting.

```powershell
uv sync
uv run scripts/ResolveTimeTracker.py
uv run -m unittest discover -s tests
```

No runtime dependencies are required yet.

## License

MIT. See [LICENSE](LICENSE).
