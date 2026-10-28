# Ticket 52 acceptance update

Windows validation on 2026-10-27, using production source `bfd5012` plus test-only changes. [#52](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/52) remains open: playback billing failed the live check. macOS/X11 acceptance moved to [#58](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/58) with the owner's explicit approval; fresh Mac installation stays in #54.

## Deterministic checks

- Corrected the heartbeat test's five-minute timestamp jumps to twelve five-second observations in a half-open sixty-second interval; exactly six heartbeat writes are required.
- Added forty concurrent status/dashboard reads across eight reader threads; they must not consume another Resolve observation.
- Added native Win32 activity reads, command-not-found/permission/error/timeout handling, missing tools/display and Wayland unavailable states, and cached Mac/X11 commands running only on the background sampling thread. A requested one-second sampling interval must still wait fifteen seconds.
- The isolated Windows installer fixture now excludes scratch media and local attachment artifacts from its disposable source copy.

Checks: full Python suite **155 passed, 34 subtests passed, one opt-in installer test skipped**; Ruff format/lint passed. Focused checks after the final test edits are recorded with the completion commit. Frontend lint, typecheck, 29 tests and production build passed, with the existing large-chunk warning. These frontend checks were against unchanged frontend source.

An exploratory `ty` check of the four touched test files still reports twelve diagnostics in existing test code (test doubles, deliberate frozen-field mutation and optional-value narrowing); it is not a configured repository gate. The new test sections have no remaining diagnostics. No type-checker dependency or suppression was added.

## Live Resolve run

Environment: Windows 11 build 26200, CPython 3.13.5, Resolve Studio **21.1.1.10**. Resolve was initially closed. A disposable acceptance project used a generated 120-second 1920x1080 H.264 test pattern, a separate tracker database, the production `--tracked-launch` CLI and its real loopback API. The normal tracker database, installed menu entries and user settings were not modified.

The sampler reused the existing benchmark's identity-aware OS process census. It retained an explicit reporting owner, exercised a duplicate tracked launch, sampled status/diagnostics, opened one timed Electron dashboard with a separate profile, requested a normal Resolve quit, read the reporting dashboard, detached, and checked the previously observed process identities.

| Observation | Result |
| --- | --- |
| Duplicate tracked launch | Reused the same runtime PID |
| SDK reader identities | One reader throughout |
| Playback | Status became stale, then SDK-pending/error; uncertain playback time was excluded |
| Pause/Resume while pending | Both HTTP requests completed; disabled/enabled state changed |
| Cached-handle workaround | GetName, IsRenderingInProgress, GetCurrentTimecode and GetCurrentPage each waited about 73.57 seconds, returning only after playback stopped |
| Render | H.264 job completed in 10.48 seconds; a 5.03-second rendering Session was persisted |
| Dashboard lifetime | One renderer appeared on demand and disappeared after normal timed quit |
| Resolve exit | Dashboard remained readable with connection=reporting and tracking_status=resolve_closed |
| Final detach | Runtime exited normally; zero previously observed application processes remained |

The short render demonstrated real render classification, not long-render billing accuracy. Start/end observation cadence limits precision; the measured render Session is not a claim of frame-accurate billing. Tests were automated, not representative human editing/dogfooding.

## Resource measurements and limits

| Measurement | Result |
| --- | ---: |
| Total run, including startup/shutdown | 352.721 seconds |
| OS process samples | 214 |
| Sampled aggregate application CPU, one core | 1.236% |
| Peak sampled aggregate resident memory | 428.11 MB |
| Peak application processes / renderers | 8 / 1 |
| Previously observed processes after exit | 0 |

This combined workload includes Electron, playback, rendering, recovery, and concurrent development checks. It exceeds the 1%/150 MB targets and is not a controlled headless comparison. The sampler and Resolve are excluded from the application tree. The extra cached-getter probes were separate diagnostic processes, also excluded; their system load can still perturb results. OS sampling can miss short-lived processes and final CPU usage. The recorded per-sample timing includes OS enumeration as well as HTTP, so it must not be cited as HTTP response latency. SDK call and SQLite-write counts were not instrumented in this live harness.

Local raw evidence is retained under `.scratch/ticket52-live/`; it contains disposable test data and is intentionally excluded from Git. The prior five-minute headless measurement remains in [isolated SDK live validation](isolated-sdk-live-validation.md); this combined run does not replace it.

## Installer result

The opt-in real Windows install/reinstall/failed-shortcut rollback test passed again: **one test in 218.51 seconds**. It built real dependencies, wrote/read native shortcuts in a temporary profile-path boundary, removed a seeded legacy startup item, preserved seeded history/settings, and restored prior artifacts after an injected shortcut-write failure. See [the isolation boundary](isolated-windows-install-validation.md).

This machine has no managed source installation to upgrade. This test still substitutes profile discovery and does not prove a historical managed-install upgrade, real Desktop redirection, a clean machine without Resolve, or multiple editing sessions. Those remain named Windows acceptance gaps.

## Remaining decision and work

Keep #52 open for playback-observation correctness, dashboard resource costs, actual installed-profile/clean-machine acceptance, representative editing and long-render billing, and recovery/dogfooding. Moving Mac/X11 checks to #58 does not waive these Windows criteria.

Process isolation solves application responsiveness, not access to fresh Resolve state. Reusing cached handles did not restore reads during playback. A production solution needs a demonstrably responsive observation source or an explicitly revised tracking contract; extending stale billing from cached state would guess project/Page ownership and was not implemented. Native UIManager's separate playback limitations remain in #57.
