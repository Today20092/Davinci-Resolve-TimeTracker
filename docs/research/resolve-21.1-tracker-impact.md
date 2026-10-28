# Resolve 21.1 impact on the time tracker

Reviewed 2026-09-08 against the current working tree and the connected native Resolve MCP server.

The current Studio tracker does not need an MCP rewrite. Its existing Resolve queries remain available in 21.1. MCP immediately helps us inspect Resolve and diagnose integration problems, but adding the connector to the assistant does not change the tracker's runtime or billing rules.

| Change | Effect on this tracker |
| --- | --- |
| Advanced scripting requires Studio | Fits the existing Studio-only product scope. Do not promise support for Resolve Free 21.1. |
| Built-in Python; Python 2 removed | We already use Python 3. The package supports 3.10 through 3.13. The MCP sandbox advertises Python 3.14, so it is not a drop-in runtime for this application. |
| Native MCP server | Enables live, read-only diagnostics from the assistant. The application still uses `DaVinciResolveScript` directly and needs its own runtime. |
| New editing, audio, transcription and preset APIs | Useful for editing automation, but do not directly improve elapsed-time measurement or prove human activity. |
| AI can operate Resolve | Existing billing rules apply regardless of who initiated the operation. Automated renders can accrue render time, including while idle or unfocused. Automated edits are not separately identified as AI work. |

## What was verified

The connected server reported Resolve Studio `21.1.0.14`. A read-only `run_script` probe called the same Resolve getters used by our bridge. Project and timeline names were readable, the timeline ID was present, render state was false, and current timecode was returned. Names and IDs were deliberately omitted from the recorded results.

`GetCurrentPage()` returned null. This demonstrates that the existing missing-page handling remains necessary even though the new API stub describes a string return. The engine retains the last page for the same project when appropriate, otherwise uses Unknown, and can backfill an active Unknown session when the page becomes available.

This validates the getters through MCP, not the external application's connection or complete launch sequence. No playback, rendering, project switching, or GUI changes were triggered. No compatibility claim is made for every runtime state.

The native API search still documents `GetCurrentProject`, `GetCurrentPage`, `IsRenderingInProgress`, `GetCurrentTimecode`, and timeline `GetUniqueId`. A scoped search of the main Resolve API stub for playback, idle, callbacks and subscriptions did not reveal a new reliable human-activity or playback-state signal. This is a bounded search result, not proof that every Resolve integration lacks events.

## What stays the same

`ResolveBridge.snapshot()` combines Resolve project/page/render/timeline data with operating-system idle and foreground checks. `TrackingEngine.poll()` assigns project/page sessions; `_is_billable()` counts rendering regardless of idle/focus and otherwise requires foreground Resolve and no idle timeout. Timecode is collected but does not currently exempt playback from idle detection.

Consequently MCP does not fix unattended playback detection, identify actual grading versus merely being on the Color page, or distinguish AI work from human work. If Resolve is foreground and the user is below the idle threshold, an AI edit can fall inside an editing session. If Resolve is unfocused or idle, ordinary AI edits do not independently make that time billable. An AI-started render does qualify under the existing rendering rule.

The MCP execution sandbox blocks filesystem, network and process access. The tracker needs SQLite storage, an application server and operating-system activity checks, so moving the whole application into that sandbox would require a different architecture without a demonstrated tracking benefit.

## Recommended next work

Keep the existing bridge. Before declaring full 21.1 support, smoke-test the actual external tracker and Scripts-menu launcher against 21.1, including project/page switching, idle/focus transitions, playback, render start/stop, and reconnect behavior. The launcher already checks that an interpreter is below Python 3.14 before selecting it for sidecar dependencies; verify its fallback with the new embedded runtime instead of loosening the package version cap blindly.

Decide whether automated render time should be billable if you plan to use MCP for unattended jobs. Change that policy only if wanted; the current behavior follows the existing rendering rule.

No application code was changed in this review.

## Sources

- User-provided Blackmagic release announcement: `C:/Users/User/.codex/attachments/d71c4603-2d5d-416f-8e78-e06a987a9ada/pasted-text.txt`, Scripting API, General Improvements and Notes sections.
- Connected Blackmagic MCP tools: `get_resolve_status`, `search_scripting_api` for the main Resolve stub, and read-only `run_script`, queried 2026-09-08. The server's `get_whats_new` response stopped at 21.0.4, so it was not used as evidence for the 21.1 announcement.
- [Resolve bridge](../../src/resolve_time_tracker/resolve_bridge.py), especially `snapshot` and `resolve`.
- [Tracking engine](../../src/resolve_time_tracker/tracking_engine.py), especially `poll` and `_is_billable`.
- [OS activity probes](../../src/resolve_time_tracker/activity_tracker.py).
- [Application wiring](../../src/resolve_time_tracker/api.py), `create_default_app` constructs the direct bridge.
- [Python requirements](../../pyproject.toml) and [menu launcher](../../scripts/ResolveTimeTracker.py).
- [Existing page/activity trust boundary](page-activity-breakdown-trust-boundary.md).

Code graph discovery was attempted but its transport was closed. Direct source inspection and caller searches were used instead.
