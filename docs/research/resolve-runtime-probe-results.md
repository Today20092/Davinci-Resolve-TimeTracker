# Resolve Runtime Probe Results

Date: 2026-07-08

## Environment

- App launched: DaVinci Resolve Studio
- Version: 21.0.2.4
- Opened project: `family`
- Python that worked: CPython 3.13.14 via `uv run --python 3.13.14`
- Python that failed: CPython 3.14.0 via default `uv run`
- Bridge module: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules\DaVinciResolveScript.py`

## Results

- External scripting bridge connects while Resolve is running.
- `Resolve.GetProductName()` returns `DaVinci Resolve Studio`.
- `Resolve.GetVersionString()` returns `21.0.2.4`.
- `Resolve.GetCurrentPage()` returned `media` and later `cut`.
- `ProjectManager.GetCurrentProject()` returned the open project `family`.
- `Project.GetCurrentTimeline()` returned `Timeline 1`.
- `Timeline.GetUniqueId()` returned `a3bbe4dd-9f98-4ed7-aecc-a056419d2719`.
- `Timeline.GetCurrentTimecode()` returned `null` on the Media and Fusion pages.
- `Timeline.GetCurrentTimecode()` returned real timecode on Cut, Edit, Color, Fairlight, and Deliver.
- `Project.IsRenderingInProgress()` returned `false` while no render was running.
- During a tiny local render job, `Project.IsRenderingInProgress()` returned `true`, then returned `false` after completion.
- `Project.GetRenderJobStatus(jobId)` returned `Rendering` during the render and `Complete` with `CompletionPercentage: 100` afterward.
- Windows idle detection via `GetLastInputInfo` returned elapsed idle seconds.
- Windows foreground-window detection found Resolve's HWND, PID, and title.
- Resolve discovered a newly copied `Utility` script under the Scripts menu without restarting.
- The Resolve menu script launched a separate Python 3.13 companion process, and that process successfully polled Resolve three times.

## Page Matrix

| Page | `OpenPage()` | `GetCurrentPage()` | `GetCurrentTimecode()` |
| --- | --- | --- | --- |
| media | true | media | null |
| cut | true | cut | `00:00:00:00` |
| edit | true | edit | `00:00:00:00` |
| fusion | true | fusion | null |
| color | true | color | `00:00:00:00` |
| fairlight | true | fairlight | `00:00:00:00` |
| deliver | true | deliver | `00:00:00:00` |

## Playback Finding

Playback visibly advanced the open timeline from about `00:01:43:20` to `00:02:31:00`.

However, running the external polling script while playback was active timed out twice, including a short two-sample probe. After stopping playback, the same script connected and returned data normally. Treat external bridge polling during active playback as unsafe for the MVP.

## Still Untested

- DaVinci Resolve Free specifically; deferred until after the Studio MVP path works.

## Decision Impact

The Studio-first MVP can rely on external scripting for project, page, timeline identity, page-specific current timecode, render transition state, Windows idle seconds, and Resolve foreground detection in this installed Studio environment.

Do not poll the external Resolve bridge during active playback in the MVP. Use page/project/render/idle/focus signals first; revisit playback classification only if a safer in-process or event-driven approach appears.

Use a Resolve `Utility` menu script as the launch point for a companion process. A full native Resolve UI is not required to start the MVP.
