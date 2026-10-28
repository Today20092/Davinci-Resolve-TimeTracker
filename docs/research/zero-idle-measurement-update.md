# Zero-idle measurement and coverage update

Implementation follow-up for [#52](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/52), based on main `4b311cf`, 2026-10-27. This changes the synthetic benchmark, not installed tracking behavior.

## What changed

`scripts/benchmark_runtime.py` now enumerates the managed worker's actual process tree instead of claiming one application process. Windows uses read-only `Win32_Process` accounting through the OS PowerShell/CIM tools; macOS/Linux use `ps`. These benchmark-only collectors are outside the measured application tree. No background monitor is installed in the product.

Process count, aggregate resident memory, cumulative CPU time and renderer command-line counts come from OS snapshots. Previously observed descendants are checked after runtime exit, even if their parent has already exited. PID start identity prevents an unrelated reused PID being counted as the old process. Missing command lines make the renderer result unavailable rather than silently zero.

SQLite counters distinguish all post-initialization SELECT statements, INSERT/UPDATE/DELETE/REPLACE statements, Session-history reads and heartbeat updates. An optional `--dashboard-reads` workload exercises the actual HTTP dashboard interface and separately counts all SELECT work during those calls. It does not open Electron and does not model the frontend's event-driven request pattern.

Synthetic snapshot observations are not Resolve scripting calls. The report returns `resolve_sdk_calls: null` with an explicit explanation. `frontend_builds` and `child_processes` are Python subprocess audit counts inside the managed worker, not counts of commands launched by another runtime. The JSON names its measurement sources.

## Run it

From the repository root:

```text
uv run --python 3.13 scripts/benchmark_runtime.py --seconds 300 --output benchmark-runtime.json
uv run --python 3.13 scripts/benchmark_runtime.py --seconds 300 --dashboard-reads --output benchmark-dashboard.json
```

Both commands use a temporary database and a sleeping process standing in for Resolve. Neither opens Resolve or uses production history. Nonpositive, infinite and NaN durations are rejected before workers start. An unavailable OS collector fails the benchmark instead of publishing invented counts.

## Deterministic coverage map

| Requirement | Existing public-boundary checks |
| --- | --- |
| Non-overlapping cadence, cached reads, retry and heartbeats | `tests/test_runtime_tracking.py`: wait-after-observation, published-state/rate-limit and failed-observation tests; `tests/test_runtime_host.py`: heartbeat limit with many readers; `tests/test_api.py`: readers do not observe and heartbeat events do not rebuild history. |
| Launch/attach, duplicate and failure cleanup | `tests/test_tracked_launch.py`: discovery/attach/launch/cancel/lock checks; `tests/test_runtime_host.py`: one owner, startup retry, failed launch and blocked-observation shutdown. |
| Dashboard-only, duplicate owner, detach and dashboard crash | Real subprocess tests in `tests/test_runtime_host.py`, including read-only reporting, endpoint removal and process exit. |
| Resolve exit while dashboard stays, then final shutdown | `RuntimeHostTest.test_single_owner_dashboard_survives_resolve_then_everything_stops`; its Resolve/process providers are controlled substitutes, not a live Resolve test. |
| Native shortcuts, upgrade preservation and attempt rollback | `tests/test_bootstrap_install.py` checks the requested shortcuts/startup removal and restoration after failed attempts. These are isolated tests, not an upgrade of the user's installed copy. |
| Activity cadence, cache and failure safety | `tests/test_activity_tracker.py`: immutable cached state, many reads without resampling, off-thread execution, absence/in-flight invalidation, shutdown and malformed/failed adapters. `tests/test_runtime_tracking.py` checks platform parsing; host tests check unavailable activity does not bill a prior project. |
| Desktop renderer/create/close and child cleanup | `frontend/test/desktop-lifecycle.test.mjs`, `sidecar-lifecycle.test.mjs` and startup tests. These primarily use controlled Electron/process boundaries; they do not prove real platform process counts. |
| Benchmark accounting and actual descendants | New `tests/test_benchmark_runtime.py` exercises the real CLI, dashboard HTTP reads, an actual child/grandchild process tree and post-exit census. It verifies counter provenance and invalid durations without hardware percentage gates. |

## Windows results

Development run on Windows 11 Pro 10.0.26200, AMD64, CPython 3.13.5, with `--seconds 300 --dashboard-reads`. This was a synthetic workload during development, not a clean-machine release certification. Final input/identity/encoding guards were then verified by the automated checks below.

| Measurement | Result |
| --- | ---: |
| Managed runtime duration | 301.41 seconds |
| Sampled application CPU, one core | 0.681% |
| Peak sampled aggregate resident memory | 75.92 MB |
| Peak observed application processes | 3 |
| Observed renderer processes | 0 |
| Synthetic observations | 61 |
| Heartbeat statements | 31 |
| Maximum heartbeats in a half-open 60-second window | 6 |
| Dashboard HTTP reads | 194 |
| SELECT statements during dashboard reads | 1,164 |
| All counted SELECT statements | 1,294 |
| Session-history SELECT statements | 194 |
| All counted data-write statements | 37 |
| Python-audited runtime child launches/builds | 0 / 0 |
| Startup to health endpoint | 1.535 seconds |
| OS process snapshots | 195 |
| Previously observed application processes after exit | 0 |

The OS census includes Windows Python launch-helper processes that the previous fixed value of one omitted. Observations/heartbeats include the initial observation and the final cadence boundary; the per-minute heartbeat cap remained six. No real Resolve SDK calls were made, and the result explicitly reports that metric as unavailable.

Checks on the final code:

- `uv run --python 3.13 -m pytest -q`: 112 passed and 16 subtests passed.
- `uv run --python 3.13 ruff format --check .` and `ruff check .`: passed.
- `uvx ty check scripts/benchmark_runtime.py tests/test_benchmark_runtime.py --python .venv/Scripts/python.exe`: passed. This focused evaluation does not adopt ty as a new project gate.
- Frontend code was unchanged; no new native frontend or live renderer test was performed in this worktree.

## Limits still owned by #52

OS sampling can miss processes that start and exit between snapshots, and final CPU consumed after a process's last sample. Resource results are sampled lower bounds, not exact execution tracing. The monitor has its own CPU cost and can perturb a workload even though its cost is excluded. Resident memory is a sampled peak, not unique/proportional memory. Percentages over very short runs are dominated by startup and are not release thresholds.

This does not measure a real Resolve SDK workload, actual Electron rendering, a managed-install upgrade, macOS/X11 permission/tool behavior, or real editing/playback/render/crash recovery. A renderer count of zero in this synthetic HTTP-only scenario is not evidence that a real dashboard uses no renderer. Full application-tree measurement with the actual dashboard remains a live validation task. Keep #52 open for those checks.

## Live Resolve and Electron continuation

The benchmark now supports an explicit live attachment. It validates that the
given PID belongs to a running Resolve executable, starts one measured runtime
against a fresh temporary database, and counts SDK method calls through a
benchmark-only proxy around the real Resolve bridge. Per-method totals, failures,
elapsed call time and unresolved in-flight calls are reported without storing
arguments, return values, project names or media paths. Snapshot observations
remain a separate counter. The proxy measures method boundaries, not individual
transport messages or Resolve's internal work.

```text
uv run --python 3.13 scripts/benchmark_runtime.py --seconds 300 --live-resolve-pid <PID> --output benchmark-live.json
uv run --python 3.13 scripts/benchmark_runtime.py --seconds 300 --live-resolve-pid <PID> --electron --frontend <built-frontend-directory> --output benchmark-live-dashboard.json
```

Start Resolve separately and use a disposable project. The benchmark does not
launch, close or terminate the attached Resolve process. At the end it signals
only its own temporary runtime to stop tracking. The internal worker rejects
pre-existing databases and paths outside its fresh temporary benchmark directory.
Production history and existing installations are not selected.

`--electron` requires the installed Electron executable and prebuilt frontend
assets under the chosen frontend directory. It launches the actual dashboard
against the same temporary database, with a separate temporary Electron profile.
The opt-in `--benchmark-seconds` desktop argument uses normal `app.quit()` and
runtime detachment after the measurement interval. It requires an explicit
database and validates the timer range; ordinary desktop launches are unchanged.
The OS process census aggregates both runtime and dashboard roots and descendants,
excluding actual Resolve and the benchmark monitor. A dashboard that exits early
fails the run rather than being counted as a completed renderer workload.

The parent performed a 15-second live SDK-only attach on Windows, Resolve Studio
21.1.1.10, using the saved disposable project. The runtime lasted 17.06 seconds,
made 42 SDK method calls over four observations, reported zero failed/in-flight
SDK calls, counted eight data-write statements, and observed three application
processes with zero remaining after exit. Peak sampled aggregate memory was
79.21 MB. Its 6.276% one-core CPU result is dominated by startup and a short
measurement interval; it is not a five-minute performance certification.

The actual Electron workload, sustained editing/playback/rendering, native
macOS/X11 behavior and installed upgrade remain separate live acceptance checks
until their results are recorded. Earlier synthetic results above must not be
relabeled as live evidence.

### Live-mode automated checks

The SDK-boundary test checks nested calls, failures, elapsed time and omission of
private values. A real worker/process test proves stopping the benchmark leaves
the attached process alive. CLI checks reject a non-Resolve PID, missing Electron
assets and existing-history worker paths before work starts. Desktop lifecycle
checks verify timed quit uses normal detach and temporary profile selection.

Before integration with the concurrent native-menu slice, the full Python suite
passed 127 tests and 16 subtests; all 29 frontend tests, Ruff and focused ty checks
passed. These tests do not substitute for live Electron or editing evidence.

### API references

- [Python subprocess](https://docs.python.org/3.13/library/subprocess.html), including bounded child commands and Windows console flags. Current docs also fetched through Context7 `/python/cpython/v3.13.9`.
- [Microsoft Win32_Process](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-process), for parent PID, start identity, command line, CPU times and resident bytes.
- Local `ps` output is the POSIX adapter boundary; native macOS/Linux execution remains unverified in this Windows session.
