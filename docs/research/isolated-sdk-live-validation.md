# Isolated SDK reader: Windows live validation (#52)

Tested on Windows 11, Resolve Studio 21.1.1.10 and Python 3.13.5. The disposable
project contained a five-second solid-color timeline. Production tracker data
and the installed application were not selected. The temporary native probe menu
entry was removed after testing.

## Why process isolation was necessary

A direct SDK getter waited 33.3578 seconds during looping playback and returned
when playback stopped. A subsequent runtime/API harness printed status every two
seconds until elapsed 24.0 seconds, then printed nothing until 88.7 seconds, when
playback stopped. The SDK call prevented the other Python thread from running.
Avoiding the database lock was insufficient to keep controls responsive.

The stale-billing correction discarded that late result, capped stale elapsed
time at the persisted Heartbeat and resumed a fresh Session without filling the
gap. However, its original same-interpreter control-responsiveness claim failed
the live test. The production runtime now isolates SDK calls in one owned child.
Activity sampling, billing, SQLite storage and reporting remain in the parent.
One pending request is retained after a timeout; no extra reader or queued call
is created. Late replies are discarded. An exited reader is reaped before a
later retry creates one replacement.

## Five-minute production CLI and HTTP run

The run exercised `ResolveTimeTracker.py --api --tracked-launch` against a fresh
temporary database, using the default isolated bridge and actual Windows activity
sampling. A separate harness made HTTP status/diagnostic requests and sampled
the runtime process tree. It excluded itself, Resolve and Electron from the
resource totals. It used no synthetic SDK or activity provider.

| Measurement | Result |
| --- | ---: |
| Total measured interval, including startup | 302.281 seconds |
| Runtime startup | 1.110 seconds |
| Aggregate sampled application CPU, one core | 0.765% |
| Peak sampled aggregate resident memory | 106.31 MB |
| Peak application processes / renderers | 4 / 0 |
| Distinct SDK reader PIDs | 1 |
| Maximum sampled HTTP status latency | 60.32 ms |
| Pause during pending SDK call | 27.73 ms |
| Resume during pending SDK call | 24.12 ms |
| Actual SDK-call count | Unavailable in this isolated-path harness |

Both the headless 1% CPU and 150 MB memory targets passed for this workload.
This is a development-machine measurement with concurrent checks, not a
controlled before/after performance comparison. OS sampling can miss short-lived
processes and final CPU time; resident memory is a sampled aggregate peak.

The workload included idle phases, looping playback, Pause/Resume while the SDK
request remained pending, playback stop and fresh tracking recovery. The same
reader PID was retained throughout. HTTP requests kept completing while the
reader waited. Initial activity was Idle; after playback stopped, the pending
reply was discarded and a later fresh observation resumed Active Work. This
does not prove complete playback classification or render billability.

The resource run used `6f7255a` (SDK implementation `7522367`). Windows job
ownership and dead-reader recovery were added afterward in `9b0b546`; their
setup/cleanup changes were checked separately, without repeating five minutes.
The older `benchmark_runtime.py --live-resolve-pid` mode remains a direct SDK
diagnostic baseline and must not be presented as measuring this isolated path.

## Lifecycle, crash ownership and recovery

The first resource harness used a nonexistent `/sessions` endpoint in its final
reporting assertion. Its measurement completed, but that final harness check
failed and was corrected to `/dashboard`. Do not describe that original harness
as a completely passing end-to-end run. Afterward, reopening its temporary
database through the reporting API confirmed one persisted Session, 210 seconds,
a readable dashboard and one CSV data row.

A separate corrected CLI/HTTP check on final code `f25c1f8` verified normal
Resolve exit, transition to reporting-only status, a readable `/dashboard`,
final reporting-owner detach and runtime exit code zero. The identity-aware OS
sampler then found **zero remaining application processes**. Its 32-second
resource readings are startup-dominated and are not a five-minute budget result.

Windows assigns the SDK child to an unnamed, non-inherited kill-on-close job
before sending requests. A real test abruptly terminated only a disposable
tracker parent while its SDK fixture held the GIL for thirty seconds: the child
exited within one second. Other regressions verify setup failure cleans up before
any SDK request, a dead reader can recover, timeouts retain one live reader, and
normal Stop remains bounded. These are owned test processes, not a forced crash
of the user's Resolve installation.

## Automated checks and limits

Final integration: **151 Python tests and 22 subtests passed; one opt-in installed
profile test skipped**. Ruff format/lint and focused ty checks passed. Both
parallel review axes have no outstanding findings after the Session-freshness
and dead-reader fixes. Existing API ty Row/dict diagnostics remain outside the
focused passing gate.

Windows playback controls and normal process cleanup are now supported by live
evidence. Mac/X11 execution and equivalent hard-parent-exit ownership, Resolve
Free, representative media/render billing, real managed-profile upgrades and
broader release dogfooding remain unverified. The native UI probe still delays
launch and Stop during playback; it is not the production tracking interface.
