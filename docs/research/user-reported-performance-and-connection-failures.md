# User-reported performance and connection failures

## Reports

1. The background Python process makes the laptop severely sluggish.
2. The tracker shows `Not connected`, `No Resolve project detected`, `Failed to fetch`, and `Waiting for the sidecar API` even after switching Resolve Projects.

## Conclusion

These reports overlap, but they are not proven to have one cause.

- The performance task (`codex://threads/01a0068e-898a-7f43-99dc-c858332f8dd7`) already covers report 1. It found that hidden startup still creates the Electron renderer and that tray status, server-sent events, and dashboard reloads independently trigger Resolve polling. The measured result was three full polls every five seconds (36 per minute), plus hidden React/chart work.
- Report 2 needs separate work. Reducing duplicate polling may prevent API starvation, but it does not fix a sidecar that exits, a Resolve scripting bridge that cannot connect, or a renderer connected to the wrong local API instance.

## Evidence

The current UI collapses different failures into the same presentation:

- Any `EventSource` error becomes `Waiting for the sidecar API`.
- A failed dashboard fetch is displayed as the browser's generic `Failed to fetch`.
- `No Resolve project detected` is the default when the last successful dashboard payload has `project: "none"`; it does not prove that the sidecar or Resolve bridge is healthy.
- `/health` only returns `{ "ok": true }`. It deliberately does not poll Resolve, so Electron can accept a live Python API whose Resolve bridge is broken.
- Runtime bridge exceptions are exposed indirectly through dashboard status, but the UI does not distinguish them from transport failures.

Local checks on 2026-08-15:

```text
node --experimental-strip-types --test frontend/test/sidecar-client.test.mjs frontend/test/sidecar-lifecycle.test.mjs
8 passed

uv run --python 3.13 pytest -q tests/test_api.py -k "health or status_poll or dashboard"
3 passed

uv run --python 3.13 python -c "from resolve_time_tracker.resolve_bridge import ResolveBridge; print(ResolveBridge().snapshot())"
RuntimeError: DaVinci Resolve scripting bridge is not connected
```

The live probe is red-capable for the bridge symptom, but the field report cannot be fully reproduced without the affected user's logs and environment. The probe also fails normally when Resolve is closed, so this result alone does not identify the field cause.

## Follow-up solution

Do the performance consolidation first, then make connection state observable at one boundary:

1. Extend health/status diagnostics to report these states separately: Python API reachable, Resolve scripting module loaded, Resolve application connected, and current Resolve Project detected. Keep `/health` cheap; add a dedicated diagnostic response or cached bridge state rather than polling Resolve from health checks.
2. Preserve the last concrete sidecar exit/spawn error and bridge exception. Show that message instead of replacing every event-stream failure with `Waiting for the sidecar API`.
3. Add one packaged-runtime integration check that starts the same Python command Electron uses, verifies `/health`, then verifies a diagnostic status against an open Resolve Studio project. This is the missing test seam; mocked API and UI tests currently all pass while a real bridge can still fail.
4. Capture the affected user's operating system, Resolve version/edition, tracker installation method/version, terminal or sidecar stderr, selected localhost port, and whether Resolve external scripting is enabled. Do not claim a final root cause until this artifact makes the integration check fail in the same way.

## Acceptance criteria

- A user can tell whether the failure is the Python sidecar, the Resolve scripting bridge, or simply no open project.
- Sidecar spawn/exit and bridge errors survive long enough to be copied into a bug report.
- The packaged-runtime integration check fails on the reported condition and passes with an open supported Resolve Studio project.
- After the performance change, API/dashboard latency remains bounded while tracking runs; if it does, lock starvation is ruled out as the connection cause.

## Deliberately deferred

Do not add telemetry, a new supervisor, or a second polling loop. The existing Electron lifecycle and cached API state are sufficient once they expose the real failure boundary.
