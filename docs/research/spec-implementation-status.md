# Spec implementation status

Integration branch: `codex/implement-native-spec`, based on main `4b311cf`.
This records the completed Windows code slices and remaining acceptance gates;
it does not declare all open tickets complete.

## Ticket graph

| Ticket | Delivered in this branch | Remaining gate |
| --- | --- | --- |
| #52 | Process-tree/resource accounting, SQL/dashboard and actual SDK-call instrumentation, cached Resolve connection, CLI regression checks and coverage map. Corrected stale always-active Linux documentation. Actual cached headless Resolve measurement completed. | Cached Electron/Resolve comparison underway; installed-upgrade, representative editing/render workload and native platform checks remain. |
| #57 | Disposable UIManager probe, host-boundary tests, dedicated Scripts-menu worker, live hide/reopen/Stop/exit evidence, ten native callbacks and three bounded no-op periodic ticks. Periodic read-only project/Page/render probe implemented. | Live periodic read-only playback/render trial and native worker resource measurement pending. Prototype evidence does not implement production tracking. |
| #54 | Existing pnpm fix and Mac handoff preserved; no newly reproduced installer defect. | Fresh Mac installation and installed dashboard/menu launch on an available Mac. |
| #13 | Studio-first support boundary preserved. | Actual Resolve Free environment. Studio checks do not establish Free support. |
| #20 | Roadmap now accurately preserves source-preview packaging deferral and explicit startup. | Hosting decision and real editing validation before packaging work. |

#52 and #57 have independent code work, but neither can be closed on the evidence
in this branch. #20 depends on their outcomes. #54 and #13 need environments that
were unavailable during this implementation.

## Verification

- Earlier integrated Python suite: 122 tests passed, plus 16 subtests. Subsequent
  native worker slices passed 135 tests, one skipped and 16 subtests before the
  latest integration merge; a refreshed full integration run is underway.
- Full Ruff format and lint checks passed; focused ty evaluations passed for the
  new scripts. Existing Python constraints and quality gates were preserved.
- Existing frontend: 27 tests passed; lint and production build passed. The
  build retains its pre-existing large-bundle warning; frontend code is unchanged.
- Five-minute synthetic dashboard-HTTP benchmark: 0.681% of one CPU core,
  75.92 MB peak sampled aggregate memory, three observed application processes,
  and zero previously observed application processes after exit. No real Resolve
  SDK calls or Electron renderer were exercised by this benchmark.
- Windows native console probe: visible Resolve-owned child window, matching
  script/Resolve PID, Python 3.13.14, SQLite/ctypes available, and a successful
  one-shot project/Page/render read. Stop exited the event loop and hid the
  window; full console return did not recover during observation. The later
  normal application-close request eventually completed.
- Historical console/custom-event callback attempts remained at 0/10. The later
  dedicated menu worker delivered 10/10 native Button Clicked callbacks with
  0.024–0.058 second latency. Hide/reopen reused the original window/report;
  Stop returned from the full menu invocation and its worker exited.
- The bounded menu worker recorded no-op ticks at 5.000858, 10.001676 and
  15.002405 seconds, then returned and exited. Its same-thread exported
  `StepLoop(wait=False)` route proves bounded no-op scheduling. Periodic SDK
  read-only workload evidence remains pending; no production tracking is wired.
- Actual cached headless Resolve run: 301.26 seconds, 60 observations, 543 SDK
  calls, zero failures, one `scriptapp` call and 0.7958 seconds total SDK time.
  Sampled application tree used 0.588% of one CPU core, peaked at 79.54 MB and
  three processes, observed zero renderers and zero remaining processes after
  exit; startup was 1.076 seconds. Cached Electron comparison is underway.
- Pending final results: cached Electron comparison, native periodic read-only
  playback/render trial, native worker resources and refreshed integrated checks.

Detailed evidence: [measurement update](zero-idle-measurement-update.md) and
[native prototype](native-ui-prototype.md). Temporary tracker data was used;
production tracking, installation and history were not changed.

## Standards

Parallel review found no confirmed documented-standard violation or code defect.
The changes retain stdlib/platform boundaries and explicit measurement limits.

## Spec

Earlier parallel review found no confirmed defect in the delivered code slices
and no scope creep. Later review identified stale documentation conclusions;
this update distinguishes the successful menu-worker feasibility evidence from
the historical console failures. #52 still needs its Electron comparison and
workload/platform/upgrade evidence. #57 still needs read-only workload and
resource evidence. Both tickets remain open.

## Next frontier

Finish the bounded native worker's read-only trial during playback/rendering and
sample its CPU/memory, then record the minimum viable hosting decision. Complete
the cached real Resolve/Electron comparison. Keep production billing in the
existing runtime while the native probe remains a feasibility experiment. Carry
Mac/Free validation forward without inventing results or replacing the user's
Studio installation.
