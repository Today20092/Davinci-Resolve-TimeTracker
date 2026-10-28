# macOS runtime acceptance: issue #58

Date: 2026-10-28. Source tested: `75e84869931d5dfec494f9c5eb59c98a551aa2d6`
(`0.1.2-alpha.1` release source). Host: macOS 27.0.1 (26A434), arm64,
Python 3.13.14, uv 0.12.19. This is partial evidence for
[#58](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/58),
not native Mac/X11 acceptance. Fresh installation is tracked separately in #54.

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

## Remaining live acceptance

- With a disposable project and separate database, verify native foreground and
  idle transitions through the installed tracker, including resumed activity.
  Automation operated Resolve while the native probe still identified Electron
  or ChatGPT as foreground; this does not prove foreground editing billing.
- Exercise an actual denied privacy permission only through a user-controlled
  OS permission decision; no permission was changed for the probes above.
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
