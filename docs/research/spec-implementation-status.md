# Spec implementation status

Integration branch: `codex/implement-native-spec`, based on main `4b311cf`.
This records the completed Windows code slices and remaining acceptance gates;
it does not declare all open tickets complete.

## Ticket graph

| Ticket | Delivered in this branch | Remaining gate |
| --- | --- | --- |
| #52 | Observed process-tree/resource accounting, truthful counter provenance, SQL/dashboard counters, CLI regression checks and coverage map. Corrected stale always-active Linux documentation. | Actual Electron/Resolve workload measurements, SDK-call instrumentation, installed-upgrade and native platform checks. |
| #57 | Disposable UIManager probe, capability/phase reports, bounded callbacks, host-boundary tests and Windows console observations. | Scripts-menu route, hide/reopen/controller lifetime, safe periodic scheduling and editing/playback/render validation. |
| #54 | Existing pnpm fix and Mac handoff preserved; no newly reproduced installer defect. | Fresh Mac installation and installed dashboard/menu launch on an available Mac. |
| #13 | Studio-first support boundary preserved. | Actual Resolve Free environment. Studio checks do not establish Free support. |
| #20 | Roadmap now accurately preserves source-preview packaging deferral and explicit startup. | Hosting decision and real editing validation before packaging work. |

#52 and #57 have independent code work, but neither can be closed on the evidence
in this branch. #20 depends on their outcomes. #54 and #13 need environments that
were unavailable during this implementation.

## Verification

- Final integrated Python suite: 122 tests passed, plus 16 subtests.
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
- The initial callback probe remained at 0/10. A payload-independent bounded
  callback fix passed its regression tests but has not had a fresh live trial.

Detailed evidence: [measurement update](zero-idle-measurement-update.md) and
[native prototype](native-ui-prototype.md). Temporary tracker data was used;
production tracking, installation and history were not changed.

## Standards

Parallel review found no confirmed documented-standard violation or code defect.
The changes retain stdlib/platform boundaries and explicit measurement limits.

## Spec

Parallel review found no confirmed defect in the delivered code slices and no
scope creep. It identified two completion gaps: #52 still needs real workload,
renderer/platform/upgrade evidence, and #57 still needs menu/controller lifetime
and scheduling evidence. These remain open requirements, not passed checks.

## Next frontier

Test a dedicated, opt-in Scripts-menu or lightweight-worker native-window route
using the disposable project. Do not connect production billing to the console
probe until lifecycle and scheduling are reliable. Run real Resolve/Electron
measurements using the improved instrumentation, and carry Mac/Free validation
forward without inventing results or replacing the user's Studio installation.
