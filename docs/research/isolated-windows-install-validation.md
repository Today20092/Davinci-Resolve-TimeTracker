# Isolated Windows installer validation

Follow-up to [#52](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/52),
2026-10-27. This is an opt-in integration check of the existing Python installer,
not a production installation, packaged release or clean-machine certification.

## Isolation boundary

The existing CLI can redirect the source checkout and Resolve Utility directory,
but Windows desktop discovery reads the owner's registry. Redirecting APPDATA
alone would still write to the real Desktop. The check therefore substitutes only
the public `windows_launcher_paths` and `windows_startup_dir` profile-path boundary.
It does not alter registry values or introduce a production installer option.

Before invoking the installer, the check resolves every source/menu/shortcut/
startup target beneath a newly created `resolve-install-check-*` temporary root.
APPDATA, LOCALAPPDATA, uv cache and pnpm store are directed into that root.
The check sets PNPM_HOME and verifies `pnpm store path` resolves beneath the root
before dependency installation; it does not assume an environment variable worked.
The disposable source copy excludes existing environments, builds and node_modules.
Any inherited uv project-environment override is removed for the check.

The test calls `install.main()` with its real CLI arguments and real stages:
pnpm frozen dependency installation, Electron version check, production build,
uv sync, Python menu-script installation and Windows WScript.Shell shortcut writes.
It never starts the dashboard, Resolve or tracking. A temporary SQLite database
contains a disposable project and saved executable setting; byte hashes verify
that installation does not modify it.

## Checks

1. Fresh local-source installation builds the frontend, creates Python's
   environment, installs both menu entries and writes all three real shortcuts.
   A second COM read verifies each shortcut's target, arguments and working
   directory, rather than accepting file existence alone.
2. A repeat installation removes a seeded legacy startup launcher while
   preserving the SQLite history/settings file.
3. A failed repeat installation rebuilds normally and writes the first two
   replacement shortcuts through COM. Only the third OS shortcut-write call is
   deliberately failed. The test verifies restoration of prior menu/shortcut/
   legacy-startup bytes, prior Python/build markers, and unchanged database bytes.

Dependency, build, menu and shortcut stages execute unchanged. The injected third
shortcut subprocess failure is a controlled rollback scenario, not an observed user defect.
Profile-path substitution means this is still not verification of the owner's
actual redirected Desktop, installed managed checkout or Start-menu discovery.

## Run

On Windows, from the repository root, with existing uv, Git, Node.js and pinned
pnpm prerequisites:

```powershell
$env:RESOLVE_RUN_INSTALL_INTEGRATION = '1'
uv run --python 3.13 -m pytest -q -s tests/test_windows_install_integration.py
Remove-Item Env:RESOLVE_RUN_INSTALL_INTEGRATION
```

It installs real dependencies and builds three times, so it is skipped in the
ordinary test suite and is not a timing-sensitive CI gate. The temporary root is
owned by this check and removed afterward. Logs identify that root, never the
owner's tracker database.

## Observed result

The final opt-in run passed on Windows 11 AMD64 with CPython 3.13.5, Node.js
26.3.0 and pnpm 11.21.0: **one integration test passed in 314.13 seconds**. It verified that the
actual pnpm store stayed under the temporary root, read the three native shortcut
records back through COM, completed fresh installation and repeat installation,
and restored prior artifacts/build/environment after the injected third-write
failure. Temporary-root removal also completed. This exercised the installer
flow from integration baseline `aee30b1`; no product installer changes were made.

After merging integration `78cfbbc`, the ordinary suite passed 132 tests and
16 subtests with this opt-in test skipped. Full Ruff formatting/lint and focused
ty checks on the integration test also passed.

## Remaining acceptance gates

This does not execute the PowerShell bootstrap wrapper, test a clean machine
without Resolve, migrate a real historical installed checkout, or launch the
installed application. Real Resolve behavior, macOS/X11 installation and activity,
Resolve Free compatibility and packaged-release lifecycle remain separate gates.

The subprocess API was checked against Python 3.13 documentation through Context7
`/python/cpython/v3.13.9`; command execution and Windows console flags use the
existing project patterns. [Python subprocess reference](https://docs.python.org/3.13/library/subprocess.html).
