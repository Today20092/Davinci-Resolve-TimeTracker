# Studio Menu Launch Verification

Date: 2026-07-08

## Environment

- DaVinci Resolve Studio 21.0.2.4
- Open project: `family`
- Current page: `deliver`
- Python: CPython 3.13.5 through the Windows `py -3.13` launcher
- Installed menu script:
  `C:\Users\User\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\ResolveTimeTrackerMenu.py`

## Result

The Resolve menu path works:

```text
Workspace > Scripts > ResolveTimeTrackerMenu
```

The menu item launched the companion window. The Dashboard showed:

- Resolve: connected
- Project: `family`
- Page: `deliver`
- State: paused while the companion window had focus

After returning focus to Resolve and waiting one poll interval, the default SQLite database contained an active Session:

```text
db: C:\Users\User\AppData\Local\ResolveTimeTracker\tracker.sqlite3
project_name: family
page: deliver
activity_category: editing
last_heartbeat_at_utc: 2026-07-08T21:59:47.777495Z
```

After a forced stop from an earlier smoke run, the next startup recovered the previous active Session into a closed row. Closing the companion window normally then closed the fresh active Session:

```text
active: None
closed_sessions: 2
```

## Fixes Made During Verification

- Added `scripts/install_resolve_menu.py` so the Utility menu launcher is generated with this checkout's path.
- Fixed the companion UI to run the live runtime poller instead of acting as only a database viewer.
- Fixed the Dashboard/status strip to display the latest Resolve Project and Page even when tracking is paused because Resolve is unfocused.
- Adjusted the status-strip layout so the Refresh button is not clipped.
- Added companion startup recovery and graceful close handling for active Sessions.

## Release Decision

The Studio MVP should ship source-first for now: README usage instructions plus the Resolve menu install helper. A packaged Windows app is deferred until the Studio path has been used through more real editing sessions.
