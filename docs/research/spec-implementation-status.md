# Spec implementation status

Integration branch: `development` (formerly `codex/implement-native-spec`), based on main `4b311cf`.
This records the completed Windows code slices and remaining acceptance gates;
it does not declare all open tickets complete.

Latest acceptance: [Ticket 52 Windows update](ticket-52-acceptance.md). Added concurrent-reader, heartbeat-rate and platform failure coverage passes, and the real isolated Windows installer check passed again. Live Resolve 21.1.1 playback still blocks fresh SDK observations; rendering and normal cleanup were exercised. The combined Electron workload exceeded resource targets. macOS/X11 checks moved to [#58](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/58) with the owner's approval; #52 remains open for its Windows gates.

## Ticket graph

| Ticket | Delivered in this branch | Remaining gate |
| --- | --- | --- |
| #52 | SDK process isolation keeps HTTP controls responsive during playback; stale-gap billing, Page-change freshness, dead-reader recovery and Windows parent-crash ownership fixed. Five-minute production CLI measurement and corrected normal-exit/reporting cleanup verified. Earlier isolated Windows install/upgrade/rollback evidence retained. | Representative media/render billing, actual managed-profile upgrades, Mac/X11 and release dogfooding. Electron-open aggregate budgets still fail in the earlier measurement. |
| #57 | Bounded native prototype and timed bootstrap evidence completed. Launch during playback waits before instrumented entry; even a pre-launched window delays its Stop callback until playback stops. | Native production tracking is not approved. Keep the shared runtime with an isolated SDK reader and on-demand Electron while any alternative host integration is evaluated. |
| #54 | Existing pnpm fix and Mac handoff preserved; no newly reproduced installer defect. | Fresh Mac installation and installed dashboard/menu launch on an available Mac. |
| #13 | Studio-first support boundary preserved. | Actual Resolve Free environment. Studio checks do not establish Free support. |
| #20 | Roadmap now accurately preserves source-preview packaging deferral and explicit startup. | Hosting decision and real editing validation before packaging work. |

#52 and #57 have independent code work, but neither can be closed on the evidence
in this branch. #20 depends on their outcomes. #54 and #13 need environments that
were unavailable during this implementation.

## Verification

- Final integrated Python suite: 151 tests passed, 22 subtests passed and one
  opt-in installed-profile test skipped. The real isolated Windows installer
  check separately passed in 314.13 seconds; see
  [its scope and substituted path discovery](isolated-windows-install-validation.md).
- Full Ruff format and lint checks passed; focused ty evaluations passed for the
  new scripts. Existing Python constraints and quality gates were preserved.
- Frontend: 29 tests passed for the live-mode slice. The Electron benchmark hook
  uses a temporary profile and normal timed quit; the dashboard UI is unchanged.
  Earlier lint/build passed, retaining the existing large-bundle warning.
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
  read-only idle evidence is recorded below; playback/render safety remains
  unproven and no production tracking is wired.
- Actual cached headless Resolve run: 301.26 seconds, 60 observations, 543 SDK
  calls, zero failures, one `scriptapp` call and 0.7958 seconds total SDK time.
  Sampled application tree used 0.588% of one CPU core, peaked at 79.54 MB and
  three processes, observed zero renderers and zero remaining processes after
  exit; startup was 1.076 seconds. The cached Electron result follows.
- Native idle periodic reads passed on Deliver and Edit pages and returned
  cleanly. A menu launch during looping playback delayed window/report creation
  until playback stopped. A subsequent 21-second sampled worker interval used
  0.446% of one core and 28.27 MB peak memory with clean identity-aware exit;
  startup and the playback delay were excluded. See the native evidence for
  limits. Production native tracking and render responsiveness remain unproven.
- Cached Electron comparison: 303.53 seconds, 43 observations, 390 SDK calls,
  zero failures and one connection. Total SDK time was 89.468 seconds, dominated
  by GetProjectManager/GetCurrentPage waits during the playback experiment.
  Aggregate tracker/dashboard cost was 3.711% of one core and 478.79 MB peak,
  with seven processes/one renderer and zero remaining after exit. Dashboard-open
  budgets failed. Manual phase timing prevents a controlled pre/post comparison.
- Current isolated production CLI/HTTP path: 302.281 seconds, 0.765% of one
  CPU core, 106.31 MB aggregate peak, four processes and zero renderers. One SDK
  reader throughout; HTTP status latency at most 60.32 ms. Pause/Resume returned
  in 27.73/24.12 ms while its SDK call remained pending. A corrected final-code
  lifecycle check verified reporting after Resolve exit, final detach and zero
  remaining processes. See the report for the original harness endpoint error,
  tested commit split, sampling limits and Windows crash-ownership tests.

Detailed current evidence: [isolated SDK live validation](isolated-sdk-live-validation.md).
Earlier evidence: [measurement update](zero-idle-measurement-update.md) and
[native prototype](native-ui-prototype.md). Temporary tracker data was used;
production tracking, installation and history were not changed.

## Standards

Parallel review found no confirmed documented-standard violation or code defect.
The changes retain stdlib/platform boundaries and explicit measurement limits.

## Spec

Earlier parallel review found no confirmed defect in the delivered code slices
and no scope creep. Later review identified stale documentation conclusions;
this update distinguishes the successful menu-worker feasibility evidence from
the historical console failures. Later review found Session freshness and
dead-reader recovery defects; both were corrected and re-reviewed. Final
standards and spec review have zero outstanding findings. #52 retains the named
workload/platform/managed-upgrade gates, and #57 retains its native-host limitation.

## Next frontier

Validate representative media, render billing, recovery and installed upgrades
using the isolated runtime before release packaging. Native UIManager hosting
has not met playback responsiveness requirements; retain on-demand Electron.
Carry Mac/Free validation forward without inventing results or replacing the
user's Studio installation.
