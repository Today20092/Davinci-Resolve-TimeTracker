# DaVinci Resolve Scripting Feasibility

Date: 2026-07-08

This note preserves earlier GPT research and adds a quick local check against the installed DaVinci Resolve scripting README on this machine.

## Sources

- Prior research file: `C:\Users\User\Downloads\resolve_time_tracker_research.md`
- Local official scripting README: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`
- Blackmagic Fusion scripting documentation should still be checked before implementing UI behavior.

## Locally Verified API Surface

The installed Resolve scripting README contains these relevant methods:

| Capability | API surface found | Status |
| --- | --- | --- |
| Current page | `Resolve.GetCurrentPage()` | Supported by docs |
| Current project | `Resolve.GetProjectManager()`, `ProjectManager.GetCurrentProject()`, `Project.GetName()` | Supported by docs |
| Current timeline | `Project.GetCurrentTimeline()`, `Timeline.GetName()`, `Timeline.GetUniqueId()` | Supported by docs |
| Render/export state | `Project.IsRenderingInProgress()`, `Project.GetRenderJobList()`, `Project.GetRenderJobStatus()` | Supported by docs |
| Playhead timecode | `Timeline.GetCurrentTimecode()` | Supported by docs |

## Feasibility Matrix

| Feature | Feasibility | MVP fallback |
| --- | --- | --- |
| Launch from Resolve Scripts menu | Likely supported | Ship a Utility script entry point |
| Detect current project | Supported | Pause tracking when no project is available |
| Detect current timeline | Supported | Treat timeline as optional metadata; bill by project |
| Detect current page | Supported | Use `Unknown` when unavailable |
| Detect render/export | Supported | Count render time even if user is idle or Resolve is unfocused |
| Detect playback/review | Prototype needed | Infer playback from `Timeline.GetCurrentTimecode()` movement |
| Detect unattended loop playback | Risky | Omit from MVP unless a simple reliable heuristic appears |
| Detect user idle | Requires OS helper | Windows `GetLastInputInfo` behind an activity provider |
| Detect Resolve foreground window | Requires OS helper | Windows foreground-window check behind the same provider |
| Native Resolve-style UI | Prototype needed | Use the smallest Resolve-launched companion flow that works in Free |

## Phase 0 Probes

1. API connection probe: print Resolve version/product, current page, and current project.
2. Project/page probe: poll project, timeline, timeline ID, and page while manually switching Resolve context.
3. Render probe: poll `Project.IsRenderingInProgress()` during a tiny render.
4. Playback probe: poll `Timeline.GetCurrentTimecode()` on Cut, Edit, Color, Fairlight, and Deliver.
5. Windows idle/focus probe: use Windows APIs to read last-input age and foreground process/window without recording keys, mouse coordinates, or screen contents.
6. UI probe: launch the smallest script-menu UI or companion surface and confirm it can stay alive while polling.

## Build Guidance

Do not build the full MVP until Phase 0 confirms playback inference, idle/focus detection, and the UI launch model in DaVinci Resolve Free. Use Resolve APIs for project/page/timeline/render/timecode. Use a platform activity provider for idle/focus.
