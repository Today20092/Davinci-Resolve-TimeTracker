# Roadmap

This document tracks product direction and project status. The README stays focused on installation and use.

## Current Focus

- Make the installer reliable across Windows, macOS, and Linux.
- Keep tracking accurate by counting active Resolve work and render/export time, not unattended time.
- Keep all data local and exportable.

## Done

- Resolve Scripts-menu launcher.
- Companion window.
- SQLite session storage.
- CSV export.
- Idle/focus-aware tracking on Windows.
- macOS activity probe using `ioreg` and `osascript`.
- Linux activity probe using `xprintidle` and `xdotool`.
- Manual Pause/Resume Tracking.
- Cross-platform installer wrappers.

## Next

- Smoke-test macOS with a real Resolve Studio install.
- Smoke-test Linux with a real Resolve Studio install.
- Show a clear UI warning when Linux activity tools are missing.
- Make duplicate launches focus the existing tracker window instead of failing invisibly.
- Improve packaged release story for non-developer users.

## Later

- Resolve Free compatibility investigation.
- Better session editing and review workflow.
- Optional packaged app builds.
- More explicit platform diagnostics inside the companion UI.
