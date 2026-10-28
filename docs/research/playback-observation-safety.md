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

While an observation is blocked, stale status and report totals stop at the last
persisted Heartbeat. Pause remains available; if observations are stale, it ends
the Session at that Heartbeat. Pause/resume invalidate already-started reads, so
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
