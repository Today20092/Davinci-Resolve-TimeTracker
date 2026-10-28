# Roadmap

This document tracks product direction and project status. The README stays focused on installation and use.

## Current Focus

- Verify real Resolve editing performance and complete trustworthy process/resource measurements in [#52](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/52).
- Test a compact native Resolve UIManager utility on Windows in [#57](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/57). The agreed experiment keeps independent Electron reporting on demand and permits a lightweight worker if needed. A full UI rewrite depends on the prototype results.
- Preserve tracking accuracy, local history, settings and exports while changing launch or presentation behavior.

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

- Complete the native window/process/lifetime/scheduling feasibility checks before choosing its production architecture.
- Verify missing activity information pauses billing and that closing Resolve and the dashboard releases every application process.
- Confirm fresh macOS installation in [#54](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/54) when a Mac is available; live macOS/X11 runtime validation remains part of #52.

## Later

- Resolve Free compatibility investigation.
- Better session editing and review workflow.
- More explicit platform diagnostics inside the companion UI.

### Windows Packaged Release

Packaging remains deferred in [#20](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/20) until real editing validation and the hosting decision in #57. The distribution design is recorded in [ADR 0002](adr/0002-windows-packaged-distribution.md); it is not a statement that a packaged release exists.

- Run a packaging spike and select the Electron installer and Python bundler.
- Produce an unsigned Windows 10/11 x64 preview through GitHub Releases.
- Support explicit Start Menu and Resolve Scripts menu launchers and legacy script-install migration. Do not install a login watcher or tray startup.
- Prove rollback-safe upgrades and native uninstall with data preserved by default.
- Pass the clean-machine lifecycle test matrix.
- Add code signing and checksums before declaring the installer production-ready.
- Consider macOS packaging only after the Windows lifecycle is proven.
