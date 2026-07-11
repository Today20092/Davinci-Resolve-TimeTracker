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

## Later

- Resolve Free compatibility investigation.
- Better session editing and review workflow.
- More explicit platform diagnostics inside the companion UI.

### Windows Packaged Release

Build a zero-prerequisite, per-user Windows installer for regular users. The accepted design is recorded in [ADR 0002](adr/0002-windows-packaged-distribution.md).

- Run a packaging spike and select the Electron installer and Python bundler.
- Produce an unsigned Windows 10/11 x64 preview through GitHub Releases.
- Support Start Menu, Resolve Scripts menu, tray startup, and legacy script-install migration.
- Prove rollback-safe upgrades and native uninstall with data preserved by default.
- Pass the clean-machine lifecycle test matrix.
- Add code signing and checksums before declaring the installer production-ready.
- Consider macOS packaging only after the Windows lifecycle is proven.
