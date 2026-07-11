# Windows-first packaged distribution

Resolve Time Tracker will add a prebuilt, per-user Windows package for regular users while retaining source installation for developers and macOS/Linux users. The package will bundle Electron, Python, and all runtime dependencies because a larger download is preferable to requiring Git, Node.js, Python, or `uv` on a user machine.

## Distribution and lifecycle

- Versioned installers will be downloaded manually from GitHub Releases; automatic updates are deferred.
- Start Menu and Resolve Scripts menu entry points will open the same single-instance application.
- Automatic startup will remain opt-in during installation and configurable later from the Electron UI.
- Upgrades will preserve data, settings, and startup preference, close and restore a running tracker cleanly, and roll back application and database changes on failure.
- Existing script installations will reuse their database and settings, replace installed launchers, and leave any source checkout untouched.
- Native uninstall will remove application and integration files while preserving data and settings by default. Permanent data deletion requires a separate explicit choice.

## Release constraints

The first target is Windows 10/11 on x64 with the latest tested DaVinci Resolve Studio release. Preview builds may be unsigned, but a production-ready installer requires code signing and published SHA-256 checksums. Normal operation remains offline with no telemetry or update checks; the UI may only open GitHub for voluntary issue reporting.

Exact Electron installer and Python bundling tools will be chosen through a runnable packaging spike. A production-ready release must pass the complete install, launch, tracking, upgrade, rollback, uninstall, data-preservation, reinstall, and offline-operation lifecycle on a clean Windows machine.
