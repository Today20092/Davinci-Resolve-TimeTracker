# Zero-idle verification

Verified on Windows on 2026-09-08. Implementation is committed and merged into local main; it has not been published or installed into the user's managed application directory.

## Result

Tracking starts through the explicit **DaVinci Resolve + Time Tracker** launch. It attaches to an existing Resolve process or launches the saved executable. The tracker stops when that Resolve process exits. The dashboard opens separately for reports and closing its last window exits Electron. The Python owner survives only while Resolve tracking or a dashboard client needs it; it exits when both are gone. There is no login watcher, tray lifetime, or automatic restart. The legacy `--background` startup command exits without launching anything, and installation removes the old startup launcher.

Observations run serially on a five-second cadence, heartbeat writes are limited to one per ten seconds, and dashboard reads do not trigger tracking observations. Platform activity probes run separately with cached snapshots and bounded subprocess calls. Missing activity information ends the current session at its last heartbeat instead of assuming activity. Reporting without Resolve is read-only.

## Checks

- Python: `uv run --python 3.13 -m pytest -q` — 102 tests and 12 subtests passed.
- Python formatting and lint: Ruff format check and Ruff check passed.
- Frontend: `pnpm test` — 27 tests passed; `pnpm lint` and `pnpm build` passed, including TypeScript compilation.
- Native Electron smoke launch returned `ok: true` and exited successfully.
- Native Windows shortcut creation produced the three expected shortcuts in temporary test locations.
- Tests cover duplicate launches, exclusive database ownership, parent crashes, dashboard detach, Resolve exit, bounded shutdown with a blocked SDK call, pause/resume races, unavailable activity, heartbeat limits, installer rollback, and read-only reporting.

## Five-minute runtime measurement

Run `uv run --python 3.13 python scripts/benchmark_runtime.py` to reproduce the synthetic benchmark. It runs the real managed Python runtime with a synthetic activity provider and a child process standing in for Resolve. Measurements exclude that stand-in process. This measures runtime overhead, not Resolve's scripting SDK or a real editing workload.

| Measurement | Result |
| --- | ---: |
| Duration | 300.64 seconds |
| CPU usage, one core | 0.27% |
| Peak sampled working set | 60.91 MB |
| Application processes during tracking | 1 |
| Renderer processes | 0 |
| Frontend builds | 0 |
| Observations | 60 |
| Heartbeat writes | 30 |
| Maximum heartbeats in any half-open 60-second window | 6 |
| History queries | 0 |
| Runtime child processes | 0 |
| Startup to health endpoint | 1.461 seconds |
| Application processes after simulated Resolve exit | 0 |

## Limits

Real Resolve SDK performance and live editing behavior still require a Resolve session. macOS and Linux native integration were not exercised on this Windows machine. A stuck SDK call can retain one daemon thread until process exit; it cannot continue writing after tracking stops. A separate SDK process is deferred unless real hangs justify it.

The optional `ty` evaluation is not clean: existing API/export typing and test-double diagnostics remain. It is not a configured project gate. The frontend build retains its existing large-bundle warning; the dashboard bundle is loaded only on demand.
