# macOS runtime acceptance: issue #58

Date: 2026-10-28. Source tested: `75e84869931d5dfec494f9c5eb59c98a551aa2d6`
(`0.1.2-alpha.1` release source). Host: macOS 27.0.1 (26A434), arm64,
Python 3.13.14, uv 0.12.19. This report contains staged evidence for
[#58](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/58).
The automatic follow-up below completes the local Mac checks with recorded
limits; native X11 remains unverified. Fresh installation is tracked separately
in #54. Later source revisions are identified in the follow-up sections.

## Native activity and disposable ownership results

| Check | Result | Evidence and boundary |
| --- | --- | --- |
| Native macOS idle and foreground commands | Pass | `MacActivityProbe` using `/usr/sbin/ioreg` and `/usr/bin/osascript` returned idle 39.898 seconds, Resolve foreground false, and no unavailable reason in 0.388 seconds. No unrelated application name was recorded. |
| Cached native activity sampling | Pass at probe boundary | Two native samples started 15.005 seconds apart. One hundred intervening `snapshot()` reads reused the immutable cached state without executing more commands. |
| No sampling when presence is false | Pass at probe boundary | No calls before `set_resolve_present(True)`; `set_resolve_present(False)` cleared the cached state and prevented subsequent calls. This controlled presence check does not replace testing real Resolve absence in the installed runtime. |
| Command failure | Pass | Using `/usr/bin/false` for both commands returned unavailable activity with both activity values unknown in 0.005 seconds. |
| Subprocess timeout | Pass at command boundary | `_run_text(["/bin/sleep", "3"])` returned `None` after 2.003 seconds, exercising the actual subprocess timeout. This does not establish an OS permission-denial result. |
| SDK parent crash during a GIL-holding read | Limit observed | Disposable parent PID 34220 was killed with SIGKILL while SDK child PID 34223 was inside the fixture's 30-second GIL-holding call. The child remained alive 1.2 seconds after parent exit. |
| Disposal of the crash probe | Pass | The exact owned child was killed after measurement; its existing `ProcessWatch` confirmed exit. No Resolve process was terminated by this probe. |

The ownership probe reused `tests/fixtures/isolated_sdk_parent.py` with a temporary
copy of `tests/fixtures/gil_holding_resolve_sdk.py`, waited for its diagnostic
report and `entered` marker, watched the reported child with `ProcessWatch`,
killed the disposable parent, and measured child liveness. Only the recorded
owned child was killed during cleanup. No real Resolve SDK or tracking database
was used in that probe.

On macOS, the SDK child checks its parent's identity between SDK calls. A blocked
SDK call cannot reach that check until it returns. Windows uses a kill-on-close
job object and has a separate Windows-only abrupt-exit acceptance test. The Mac
measurement establishes that immediate orphan cleanup is not equivalent; it
does not establish how long a real blocked Resolve SDK call will take to return.
Normal managed shutdown can terminate and, if needed, kill its owned child.

## Automated checks

Executed on this Mac:

```sh
uv run --python 3.13 -m pytest -q tests/test_activity_tracker.py tests/test_isolated_resolve_bridge.py tests/test_runtime_host.py tests/test_runtime_tracking.py
```

Result: **44 passed, 3 skipped, 24 subtests passed** in 9.04 seconds. The skips
are native Windows activity and Windows job ownership checks. Existing adapter
tests cover denied commands, malformed data, missing Linux tools/display,
Wayland unavailability, cache cadence, and SDK responsiveness/cleanup. Simulated
platform tests on a Mac do not establish native X11 behavior.

## Remaining acceptance after the manual phase

This list records the manual-phase boundary. The automatic follow-up below
supersedes the Mac idle and absent-process gaps.

- Verify inactivity-threshold pause/resume. The owner explicitly skipped this
  manual test after only 20–30 seconds without input; it remains unverified.
- Verify no platform commands are sampled while the real Resolve process is
  absent, including after Resolve exits.
- Run the required native X11 Linux checks on a real X11 host with Studio.
  The owner explicitly limited this session to Mac and asked to leave X11 open.

Use `scripts/ResolveTimeTracker.py --tracked-launch --db <test-directory>/tracker.sqlite3`
and `--companion --db <same-test-database>` for explicit data isolation. The
generated Resolve menu currently uses the default database, so its isolation
must be arranged before invoking it. Do not attach `.runtime.json` contents:
they contain a private lifecycle token.

## Installed Mac run

Reused the fresh exact-revision installation documented in
[the #54 results](ticket-54-macos-acceptance.md). The running API confirmed
DaVinci Resolve Studio 21.1.1.10. Resolve PID 45052, runtime PID 46085,
multiprocessing resource-tracker PID 46101, and SDK reader PID 46102 were
observed. The source and Python runtime were in the fresh acceptance clone.
The default database path was temporarily symlinked to a disposable database;
`run_managed` resolved it before opening SQLite and runtime metadata. No earlier
default database existed. The symlink was removed after all owners exited.

| Check | Result and boundary |
| --- | --- |
| Installed launch and repeated menu invocation | Pass: unmodified Resolve menu invoked twice; runtime and SDK reader PIDs were unchanged. No Electron dashboard started until explicitly requested. |
| Built dashboard | Pass: installed `--companion --db <test-db>` opened the built dashboard and connected to the same runtime; Vite was not used. |
| Background pause | Observed: native samples identified a non-Resolve foreground app and status remained paused/idle. True Resolve-foreground, inactivity-threshold, and resume transitions remain unverified. |
| Synthetic editing | Imported generated 1280x720, 24 fps ProRes media, created timelines, and appended nine clips to a disposable timeline. These scripting operations do not establish active-work billing under human editing. |
| Playback | Native Playback > Play Forward advanced the long timeline from `00:00:00:00` to `00:02:10:05` before native Stop. Across 50 diagnostic samples around playback, maximum API response was 0.014 seconds; SDK reader was pending in 14 samples. This confirms responsive reporting, not fresh SDK observations or foreground playback billing. |
| Rendering | Two 20-second-source UHD ProRes renders completed in 2158 and 1834 ms. A 200-second-source render completed in 10712 ms; status sampling observed rendering from sample time 3.56 to 13.17 seconds. Seventy API samples had maximum response 0.012 seconds. Final dashboard showed two rendering rows of 5 and 10 seconds, 15 seconds total. This synthetic run does not certify all workloads or exact billing accuracy. |
| Resource spot check | Runtime 0.0–0.1% CPU, RSS 80432 KiB; resource tracker 0.0%, 19984 KiB; SDK reader 0.0%, 33504 KiB. `ps` snapshots are not peaks or a sustained benchmark. |
| Resolve exit with dashboard open | Pass: API switched to reporting/resolve_closed, tracking disabled, SDK reader exited; dashboard retained render totals and rows. |
| Last dashboard owner closes | Pass: runtime, resource tracker, and SDK reader PIDs were all absent and runtime metadata was removed. |

No actual OS permission was revoked or granted during this run. The command
failure and timeout probes above must not be presented as permission-denial
acceptance. Real Resolve-absent command sampling was not traced; only controlled
presence suppression and real SDK-child cleanup were verified.

## Combined validation

- Python formatting and lint passed; complete suite: 152 passed, 4 skipped,
  32 subtests passed. The skips are platform-specific and do not establish native
  Linux acceptance.
- A Mac-specific privacy-test false positive was fixed at the existing saved
  probe-report interface: `/private/var` is a legitimate report path. The check
  now rejects the actual private fixture name and its HTML-escaped form after
  parsing JSON. Focused file: 15 passed.
- Frontend lint, typecheck, all 29 tests, and production build passed on the same
  runtime/frontend source revision. The integration changes only evidence,
  platform-status documentation, and the Python privacy assertion. The existing
  500 kB chunk warning remains documented in #54's report.

Issue #58 remains open for the listed native Mac gates and X11 checks. The
blocked SDK-child parent-crash limit remains an observed risk.

## Follow-up foreground failure and correction

The owner performed the foreground sequence and reported that the dashboard did
not update. The installed runtime stayed paused/idle, with a transient activity
error. A read-only System Events query for the actual Resolve process returned
the process name `Resolve`. The Mac probe previously required the substring
`DaVinci Resolve`, so the actual Mac process name could never be classified as
foreground. Earlier non-Resolve samples did not establish correct matching.

Source fix `3cd7c46` recognizes the exact native process name and the existing
`DaVinci Resolve` / `DaVinci Resolve Studio` names. The approved existing probe
test reproduced failure for `Resolve` before the fix; it now also verifies known
names, Finder, and an unrelated `Resolve Helper`. Focused activity/runtime tests:
25 passed, 1 skipped, 25 subtests. Complete Python checks: formatting/lint passed,
152 tests passed, 4 skipped, 37 subtests. Frontend code was unchanged.

After closing Resolve and releasing all test-runtime owners, the fix was
cherry-picked into the fresh installed acceptance clone as `67833c2`. Resolve and
the installed tracker/dashboard were restarted using the same disposable project
and database. Its idle timeout was temporarily reduced from 300 to 60 seconds
for the manual idle test. The original timeout must be restored after testing.
The corrected installed foreground sequence, idle/resume, and actual permission
denial/recovery are still pending; the regression test alone does not close them.

The first corrected human foreground run subsequently recorded editing from
04:51:58 to 04:52:53 UTC, with contiguous page rows: Edit 10 seconds, Cut 5,
Color 25, and Edit 15 (55 seconds total). The observer saw active/editing followed
by paused/idle at 04:52:55 UTC. This verifies native foreground recording and
page attribution on the corrected installation. A complete foreground return,
idle-threshold/resume, and permission-denial/recovery sequence still needs
the following manual checks.

During the next manual run, native observation confirmed Resolve foreground
with 9.5 seconds of idle time while status was active/editing, followed by
non-Resolve foreground and paused/idle. The owner reported only 20–30 seconds
without input and explicitly chose to skip the full idle test. That interval
does not reach the temporary 60-second threshold, so inactivity pause/resume
remains unverified. The test database timeout was restored to its original
300 seconds through the settings API before permission testing.

## Actual permission-denial check

The owner inspected macOS Automation settings and confirmed that both ChatGPT
and DaVinci Resolve had System Events enabled. For the chat-launched installed
test runtime, the owner disabled only ChatGPT > System Events and interacted
with Resolve for approximately 30 seconds, leaving Resolve's permission enabled.
At 04:57:54 UTC diagnostics changed to `activity probe failed`; by 04:58:00 UTC
status was error/paused with zero active elapsed time. The Resolve bridge stayed
connected, the test project remained detected, and SDK reader PID 15843 remained
alive. This establishes actual permission denial at the native activity boundary
and fail-closed tracking for this launch origin, not a Resolve scripting failure.
The owner then restored ChatGPT > System Events and interacted with Resolve.
At 05:00:41 UTC the activity error cleared; by 05:00:45 UTC status was
active/editing. The public dashboard API returned a new Edit session from
05:00:43.983 to 05:00:59.008 UTC (15 seconds), followed by idle/paused when the
owner returned to the chat. The test database setting was confirmed back at
300 seconds. Denial and recovery passed without restarting the runtime.

The manual foreground/page attribution and permission-denial/recovery gates
are now verified on installed source `67833c2` (base `75e8486` plus foreground
fix `3cd7c46`). Permission evidence applies to the chat-launched runtime's
ChatGPT Automation grant; Resolve's separate grant stayed enabled throughout.
The idle gate is intentionally unverified, native X11 remains outside this
session, and real absent-process command tracing remains open. Neither these
passes nor the regression fix remove the blocked SDK-child parent-crash limit.

## Automatic completion on combined development source

At the owner's request, the remaining Mac checks ran without further human
interaction on source `40d00d8a3097c7599f724346b8a5e57751ebd06e`. This combines
development `0c80e0d` with Mac acceptance `baf010d`, preserving the reorganized
README and one-command installation instructions. Runtime source includes the
foreground fix. A new disposable database and the saved acceptance project were
used; no personal history, projects, media, or privacy permissions were changed.

| Check | Result and evidence |
| --- | --- |
| Native idle pause | Pass: Resolve remained foreground. With a 60-second test threshold, status changed from active/editing to idle/paused at native idle 75.6 seconds (85.4 seconds into observation). The extra delay is consistent with 15-second cached activity sampling plus runtime polling. |
| Resume after idle | Pass: an automated Save input in the disposable project reset native idle; status returned to active/editing with Resolve still foreground and native idle 7.2 seconds. The idle threshold was restored to 300 seconds before playback. |
| Foreground playback measurement | Pass for this workload: the 20-second, 24 fps synthetic timeline played from `00:00:00:00` to `00:00:20:00`. Across a 51.027-second observation window around playback, the saved editing row was 51 seconds. All 50 native samples were foreground and below the idle threshold; the SDK reader was pending in 4 samples. Maximum latency for a pair of status/diagnostic requests was 0.007 seconds. This sample showed no measurable lost whole seconds; it does not certify all playback workloads. |
| Real Resolve absence | Pass at the actual command boundary: temporary PATH wrappers logged only command name and timestamp, then exec'd the unchanged native `ioreg`/`osascript` binaries. Before exit, each command ran 26 times. After real Resolve exit was confirmed by process lookup and reporting/resolve_closed status, both counts stayed exactly 26 for 45.02 seconds (three sample intervals): zero new activity commands. No wrapper replaced activity results. |
| Reporting and final owner shutdown | Pass: reports remained visible after Resolve exited. Closing Electron released runtime PID 65858 and SDK reader PID 65862 and removed runtime metadata. |
| Normal close during blocked SDK call | Pass: disposable parent PID 59321 / SDK child 59329; `bridge.close()` stopped the child in 0.001 seconds, confirmed through `ProcessWatch` and diagnostics. |
| Parent crash during blocked SDK call | Recorded limit: after disposable parent 59353 received SIGKILL, child 59355 survived the 1.2-second checkpoint and exited naturally 29.034 seconds after parent death, once the 30-second GIL-holding fixture returned. No cleanup kill was needed. An indefinitely blocked real SDK call still has no automatic cleanup deadline on Mac. |

The activity wrappers were confined to the disposable runtime's PATH. Observer
probes used the ordinary native binaries and were not included in the runtime's
command counts. The wrapper log contains no command output, app names, project
names, media paths, or runtime tokens. All temporary probe children were
confirmed exited; the new test database retains the normal 300-second setting.

Combined-source verification passed: Python formatting/lint, 152 Python tests
(4 platform skips, 37 subtests), frontend lint/typecheck, 29 frontend tests, and
production build. The existing 705.51 kB minified chunk warning remains. Focused
isolated SDK verification passed 4 tests, with 2 Windows-only skips.

**Final local status:** Mac smoke checks are good so far on this Apple Silicon
macOS 27.0.1 / Resolve Studio 21.1.1.10 configuration. Foreground/page tracking,
idle pause/resume, actual permission denial/recovery, the measured playback and
render workloads, command suppression after Resolve exit, and normal process
ownership have evidence. Native X11 remains open in #58. Broader exact billing
accuracy and indefinitely blocked SDK-child cleanup remain explicit limits;
these checks do not qualify a stable release or a new published artifact.
