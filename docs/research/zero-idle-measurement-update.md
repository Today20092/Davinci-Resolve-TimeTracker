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

Checks at the synthetic-measurement milestone (superseded counts below):

- `uv run --python 3.13 -m pytest -q`: 112 passed and 16 subtests passed.
- `uv run --python 3.13 ruff format --check .` and `ruff check .`: passed.
- `uvx ty check scripts/benchmark_runtime.py tests/test_benchmark_runtime.py --python .venv/Scripts/python.exe`: passed. This focused evaluation does not adopt ty as a new project gate.
- Frontend code was unchanged; no new native frontend or live renderer test was performed in this worktree.

## Limits still owned by #52

OS sampling can miss processes that start and exit between snapshots, and final CPU consumed after a process's last sample. Resource results are sampled lower bounds, not exact execution tracing. The monitor has its own CPU cost and can perturb a workload even though its cost is excluded. Resident memory is a sampled peak, not unique/proportional memory. Percentages over very short runs are dominated by startup and are not release thresholds.

The synthetic scenario does not measure a real Resolve SDK workload, actual Electron rendering, a managed-install upgrade, macOS/X11 permission/tool behavior, or real editing/playback/render/crash recovery. A renderer count of zero in this synthetic HTTP-only scenario is not evidence that a real dashboard uses no renderer. The live continuation below records the separate application-tree measurement. Keep #52 open for outstanding acceptance checks.

## Live Resolve and Electron continuation

The benchmark now supports an explicit live attachment. It validates that the
given PID belongs to a running Resolve executable, starts one measured runtime
against a fresh temporary database, and counts SDK method calls through a
benchmark-only proxy around the real Resolve bridge. Per-method totals, failures,
elapsed call time and unresolved in-flight calls are reported without storing
arguments, return values, project names or media paths. Snapshot observations
remain a separate counter. The proxy measures method boundaries, not individual
transport messages or Resolve's internal work.

This CLI's live mode measures a direct SDK bridge in its benchmark worker. It is
a diagnostic baseline; it does not measure an isolated SDK-reader architecture
or its IPC/process overhead. Do not reuse these results as evidence for a later
production bridge without measuring that actual path separately.

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

### Five-minute live dashboard baseline and connection fix

The Windows live run in `resolve-live-electron-300.json` used the actual Electron
dashboard and Resolve Studio 21.1.1.10 with a disposable five-second solid-color
timeline. The operator observed looping playback at 30 fps and an advancing
timecode, with playback-stop and unfocused phases. A short H.264 render was
started near the end, but its overlap with measurement is not established; this
run does not validate render billing.

| Measured baseline | Result |
| --- | ---: |
| Duration | 303.87 seconds |
| Actual SDK calls / observations | 482 / 48 |
| Failed SDK calls / in-flight at finish | 0 / 0 |
| Total measured SDK time | 65.990 seconds |
| `scriptapp` calls / measured time | 48 / 65.574 seconds |
| Aggregate application CPU, one core | 5.963% |
| Peak sampled aggregate resident memory | 458.48 MB |
| Application processes / renderers | 7 / 1 |
| Heartbeat statements / maximum in 60 seconds | 17 / 6 |
| Previously observed application processes after exit | 0 |

Both the 1% CPU and 150 MB aggregate memory budgets **failed** in this real
dashboard workload. The aggregate includes the actual dashboard, its children
and the temporary runtime; it excludes Resolve and the sampler. It cannot be
compared directly with the headless synthetic result as a dashboard-free budget.

The SDK proxy identified repeated connection acquisition as the latency source:
`scriptapp("Resolve")` took over 99% of measured SDK time. Other snapshot getters
together took about 0.416 seconds. The shared bridge now retains a successfully
acquired Resolve object for its tracked-process session. A failed mandatory SDK
snapshot read discards that automatic cache so the next observation can
reconnect. Host-injected Resolve objects are retained, and optional metadata
reads keep their existing tolerant behavior. The serialized observation cadence
is unchanged. Tests prove connection reuse and recovery at the public snapshot
and SDK boundary; subsequent live measurements are recorded below.

After this fix, the integrated Python suite passed 135 tests and 20 subtests,
with one installed-profile test skipped. Ruff passed on the changed Python
files, and focused ty checking passed on the bridge. Checking the existing test
file with ty still reports seven pre-existing Optional-narrowing diagnostics in
unrelated runtime tests; this change does not adopt ty as a project-wide gate.

### Cached headless live result

The post-fix headless run (`resolve-live-cached-headless-300.json`) used the real
Resolve SDK and temporary tracker storage for 301.26 seconds. It completed 60
observations and 543 SDK calls without a failure or an in-flight call at finish.
`scriptapp` ran once; total SDK time was 0.7958 seconds. Aggregate sampled tracker
CPU was 0.588% of one core and peak resident memory was 79.54 MB, passing the
headless 1% / 150 MB budgets. Startup was 1.076 seconds. Three application
processes and zero renderers were observed, with zero remaining after exit.

This is a live SDK measurement while the synthetic test project was idle. It
does not establish representative editing or render performance, and it is not
a directly comparable replacement for the earlier dashboard-open workload.

### Cached Electron comparison and playback blocking

An additional controlled getter-only reproduction on the same Windows/Studio
version connected while idle, then timed `GetProjectManager` and `GetCurrentPage`
once per second without retaining their results. Idle calls took approximately
0.4–2.3 ms. After loop playback started, iteration 16 entered
`GetProjectManager` at 16.028 seconds and returned 33.3578 seconds later,
immediately after playback stopped. The next `GetCurrentPage` took 0.5 ms and
subsequent idle reads returned in 0.4–0.8 ms. The UI remained at approximately
29.97 fps while the SDK caller waited. This isolates a blocking getter without
Electron, tracking, database writes or native UI probe code in the caller.
It does not prove that every getter or every playback workload behaves alike.

The post-fix dashboard-open run (`resolve-live-cached-electron-300.json`) lasted
303.53 seconds with the actual Electron dashboard and temporary storage. It
included the same disposable solid-color timeline, idle phases, looping playback
and playback stop. These phases were operated manually; their exact durations
were not instrumented, so the pre/post comparison is not a controlled benchmark.

| Measured post-fix dashboard workload | Result |
| --- | ---: |
| Actual SDK calls / observations / failures | 390 / 43 / 0 |
| `scriptapp` calls / measured time | 1 / 0.01685 seconds |
| Total measured SDK time | 89.468 seconds |
| `GetProjectManager` / `GetCurrentPage` measured time | 43.477 / 45.618 seconds |
| Aggregate application CPU, one core | 3.711% |
| Peak sampled aggregate resident memory | 478.79 MB |
| Application processes / renderers / remaining after exit | 7 / 1 / 0 |
| Startup | 1.672 seconds |
| Heartbeat statements / maximum in 60 seconds | 20 / 6 |

The cache eliminates repeated connection acquisition, but does not solve SDK
getter blocking during playback. No call reported a failure or remained in flight
at finish; that does not make the 89 seconds of SDK waiting acceptable or prove
five-second observations throughout playback. This run again fails the aggregate
1% / 150 MB budgets with Electron open. The observed resource reduction cannot
be attributed solely to connection caching because the manually operated phases
and system load differed. Keep dashboard-open cost distinct from headless cost.

Native macOS/X11 behavior, sustained representative media workloads, render
billing, crash recovery and installed upgrade remain separate acceptance checks.
Earlier synthetic results above must not be relabeled as live evidence.

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
