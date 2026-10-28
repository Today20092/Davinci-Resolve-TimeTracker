# Playback observation safety (#52)

The controlled Windows Studio 21.1.1.10 reproduction entered GetProjectManager
during loop playback and waited 33.3578 seconds, returning after playback stopped.
The application remained responsive at 29.97 fps. This does not identify a
supported way to cancel an SDK getter or remove its wait.

The runtime now uses the existing 15-second Heartbeat freshness boundary to
prevent those waits from becoming billable time. A read exceeding that limit is
discarded after it returns and reported as an error. Slow exceptions also recover
the previous Session at its persisted Heartbeat. A subsequent fresh observation
starts new tracking without backfilling the stale interval, including gaps caused
by repeated quick errors and retries. No extra SDK thread or worker is created.

Stale status and report totals stop at the active Session's persisted Heartbeat,
or its start until a first Heartbeat exists. Pause uses that same recovery boundary;
the global Heartbeat rate limiter cannot establish a new Session's freshness.
Pause/resume invalidate already-started reads, so
their results cannot overwrite control changes or reopen pre-pause tracking.
The existing bounded Stop behavior remains covered.

Deterministic regressions exercise public runtime and API interfaces with
temporary SQLite data and controlled SDK/time boundaries. They cover late and
failed reads, stale elapsed totals, pause during staleness, pause/resume during
an in-flight observation, and fresh recovery after a stale gap. The original
assertions were observed failing before implementation. The shared threshold
matches the existing stale UI contract rather than adding a new timeout setting.

This deliberately excludes uncertain time instead of guessing that the same
project/Page stayed active. It does not prove playback/render tracking accuracy,
interrupt SDK calls, or replace real project-switch/render/crash validation.

## Interpreter isolation

The first safety iteration's Event-based tests released the interpreter GIL.
They therefore did not establish responsive controls during the real SDK call.
A subsequent live test stopped producing parent-thread status output between
elapsed 24.0 and 88.7 seconds, until playback stopped. Billing recovery worked
after release, but parent Pause/Stop could not execute during the wait.

The production managed runtime and legacy API entry point now use
`IsolatedResolveBridge`. One spawn-context child owns SDK access and its cached
connection; activity sampling, the database and all billing remain in the parent.
There is one serialized in-flight request. After the existing 15-second limit,
the parent reports an error without spawning replacement readers or queuing
additional SDK calls. A late response is discarded, then a later fresh request
can use the same child. Diagnostics read cached metadata without calling the SDK.

Normal close/Resolve exit closes or boundedly terminates and joins that owned
child. The child also watches parent lifetime while idle. A native SDK call can
prevent the child's Python lifetime check from running; hard parent-crash orphan
cleanup during such a call is not guaranteed by multiprocessing's daemon flag.
No crash-safety claim is made without an OS ownership test. Native Mac/X11
behavior remains unverified. Process/resource measurements must include this
additional child and any platform multiprocessing helpers.

The deterministic reproduction holds the calling interpreter's GIL with
`ctypes.PyDLL(...).Sleep`: the original parent resumed after 2.005 seconds instead
of the requested 0.05 seconds. The isolated fake-SDK tests verify parent status
and Pause within 0.5 seconds during a three-second child GIL hold, bounded Stop,
one child across repeated timeouts and rejection of its late response. These
tests do not replace a post-isolation live Resolve playback check.

References fetched through Context7: Python 3.13
[multiprocessing Process/Pipe lifecycle](https://docs.python.org/3.13/library/multiprocessing.html).
The official [ctypes PyDLL reference](https://docs.python.org/3.13/library/ctypes.html#ctypes.PyDLL)
documents that those foreign calls retain the GIL. Context7's ctypes lookup hit
its quota; that fact was checked in the official reference instead.
