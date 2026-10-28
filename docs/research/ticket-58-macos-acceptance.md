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

- Reuse #54's fresh installation and installed launch result, recording the
  actual Resolve Studio version and source/runtime identities.
- With a disposable project and separate database, verify native foreground and
  idle transitions through the installed tracker, including resumed activity.
- Exercise an actual denied privacy permission only through a user-controlled
  OS permission decision; no permission was changed for the probes above.
- Verify no platform commands are sampled while the real Resolve process is
  absent, including after Resolve exits.
- Verify repeated tracked launch reuses one runtime, dashboard launch is on
  demand, reports survive Resolve exit, and closing all owners releases runtime
  and SDK child.
- Measure real editing, playback, and rendering workloads and record any SDK
  freshness or billing limits.
- Run all documented Python/frontend checks on the combined changes.
- Run the required native X11 Linux checks on a real X11 host with Studio.

Use `scripts/ResolveTimeTracker.py --tracked-launch --db <test-directory>/tracker.sqlite3`
and `--companion --db <same-test-database>` for explicit data isolation. The
generated Resolve menu currently uses the default database, so its isolation
must be arranged before invoking it. Do not attach `.runtime.json` contents:
they contain a private lifecycle token.
