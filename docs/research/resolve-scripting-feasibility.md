# DaVinci Resolve Scripting Feasibility

Date: 2026-07-08

This note preserves earlier GPT research and adds a local check against the installed DaVinci Resolve scripting README on this machine. It resolves the docs-backed part of wayfinder ticket `01-validate-resolve-scripting-feasibility`.

## Sources

- Prior research file: `C:\Users\User\Downloads\resolve_time_tracker_research.md`
- Local official scripting README: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`
- Blackmagic Fusion scripting documentation should still be checked before implementing UI behavior.
- Local bridge module: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules\DaVinciResolveScript.py`

## Locally Verified API Surface

The installed Resolve scripting README contains these relevant methods:

| Capability | API surface found | Status |
| --- | --- | --- |
| Current page | `Resolve.GetCurrentPage()` | Supported by docs |
| Current project | `Resolve.GetProjectManager()`, `ProjectManager.GetCurrentProject()`, `Project.GetName()` | Supported by docs |
| Current timeline | `Project.GetCurrentTimeline()`, `Timeline.GetName()`, `Timeline.GetUniqueId()` | Supported by docs |
| Render/export state | `Project.IsRenderingInProgress()`, `Project.GetRenderJobList()`, `Project.GetRenderJobStatus()` | Supported by docs |
| Playhead timecode | `Timeline.GetCurrentTimecode()` | Supported by docs |

The README also confirms:

- Lua and Python user scripts are supported.
- Resolve must be running for scripts to be invoked.
- Scripts can be invoked from the menu and Console.
- Resolve scans script folders at startup and lists scripts under `Workspace > Scripts`.
- Scripts under `Utility` are listed in all pages.
- The Windows script folders are `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Fusion\Scripts` and `%APPDATA%\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts`.
- The scripting APIs cover a common superset for Free and Studio, but calls can fail when a function is Studio-only, the system does not meet requirements, or required extras are missing.

## Feasibility Matrix

| Feature | Feasibility | MVP fallback |
| --- | --- | --- |
| Launch from Resolve Scripts menu | Supported by docs | Ship a `Utility` script entry point |
| Detect current project | Supported | Pause tracking when no project is available |
| Detect current timeline | Supported | Treat timeline as optional metadata; bill by project |
| Detect current page | Supported | Use `Unknown` when unavailable |
| Detect render/export | Supported | Count render time even if user is idle or Resolve is unfocused |
| Detect playback/review | Uncertain, prototype needed | Infer playback from `Timeline.GetCurrentTimecode()` movement |
| Detect unattended loop playback | Out of MVP | Revisit later only if a simple timecode-loop heuristic proves reliable |
| Detect user idle | Requires OS helper | Windows `GetLastInputInfo` behind an activity provider |
| Detect Resolve foreground window | Requires OS helper | Windows foreground-window check behind the same provider |
| Native Resolve-style UI | Uncertain, prototype needed | Use the smallest Resolve-launched companion flow that works in Free |

## Runtime Check

DaVinci Resolve was not running during this pass, so live API calls could not validate Resolve Free behavior. Importing the bridge with uv's default CPython 3.14 exited without diagnostics. Importing with CPython 3.13 succeeded and returned `connected=False`, which is expected when Resolve is closed.

Phase 0 runtime probes should use a standard installed 64-bit Python supported by Resolve, not uv's bleeding-edge interpreter by default.

## Phase 0 Probes

1. API connection probe: print Resolve version/product, current page, and current project while Resolve Free is open.
2. Project/page probe: poll project, timeline, timeline ID, and page while manually switching Resolve context.
3. Render probe: poll `Project.IsRenderingInProgress()` during a tiny render.
4. Playback probe: poll `Timeline.GetCurrentTimecode()` on Cut, Edit, Color, Fairlight, and Deliver.
5. Windows idle/focus probe: use Windows APIs to read last-input age and foreground process/window without recording keys, mouse coordinates, or screen contents.
6. UI probe: launch the smallest script-menu UI or companion surface and confirm it can stay alive while polling.

## Ticket 01 Decision

The MVP can depend on the official Resolve API for project, page, timeline, render/export, and timecode polling. It must not depend on a direct playback API, direct idle API, direct foreground-window API, or unattended-loop detection because those were not found in the official scripting README.

Playback review should be treated as a Phase 0 runtime/prototype decision using timecode movement. Idle and foreground state should be supplied by a Windows activity provider. Unattended loop playback should be omitted from MVP unless the runtime probe reveals a trivial reliable heuristic.

## Build Guidance

Do not build the full MVP until Phase 0 confirms playback inference, idle/focus detection, and the UI launch model in DaVinci Resolve Free. Use Resolve APIs for project/page/timeline/render/timecode. Use a platform activity provider for idle/focus.
