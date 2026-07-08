# Page and Activity Breakdown Trust Boundary

Date: 2026-07-08

Resolves wayfinder ticket #24: "Judge trustworthy Page and activity breakdowns".

## Sources

- Official installed Resolve scripting README: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`, last updated 2026-05-26.
- Official installed Resolve Workflow Integrations README: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Workflow Integrations\README.txt`.
- Official installed Resolve scripting changelog: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\CHANGELOG.txt`.
- Existing runtime probe: `docs/research/resolve-runtime-probe-results.md`.
- Existing Windows idle research: `docs/research/windows-idle-detection-strategy.md`.

## Decision

For the Studio MVP, show and export these as trustworthy factual breakdowns:

- Resolve Project.
- Resolve Page bucket: `media`, `photo`, `cut`, `edit`, `fusion`, `color`, `fairlight`, `deliver`, or `Unknown`.
- Coarse activity category: `editing` and `rendering`.
- Idle/focus adjusted billable Session duration, but not as a Resolve-native activity signal.

Do not show finer sub-page labels such as "grading", "watching", "compositing", "audio mix", or "reviewing playback" as factual billing breakdowns in the MVP. Those labels are interpretations, not directly supported by the current reliable signal set.

Do not show Page bars as precision telemetry. If the dashboard includes Page bars, label them as Session time grouped by Resolve Page, and keep render time visibly separate because rendering can continue while the user is idle or Resolve is unfocused.

## Evidence

The installed Resolve scripting README documents `Resolve.GetCurrentPage()` and says the return can be one of `media`, `photo`, `cut`, `edit`, `fusion`, `color`, `fairlight`, `deliver`, or `None` (`README.txt:89-90`). This supports Page buckets as factual labels.

The README documents project and timeline access through `GetCurrentProject()`, `Project.GetName()`, `GetCurrentTimeline()`, `Timeline.GetName()`, and `Timeline.GetUniqueId()` (`README.txt:119`, `README.txt:154`, `README.txt:157`, `README.txt:353-359`). This supports project labels, and optional timeline labels if the data model later stores them.

The README documents render state and render job status through `Project.IsRenderingInProgress()`, `Project.GetRenderJobList()`, and `Project.GetRenderJobStatus(jobId)` (`README.txt:164`, `README.txt:172`, `README.txt:178`). Workflow Integrations also lists `RenderStart` and `RenderStop` events (`Workflow Integrations\README.txt:130-131`). This supports a separate rendering activity category.

The README documents `Timeline.GetCurrentTimecode()` only for Cut, Edit, Color, Fairlight, and Deliver pages (`README.txt:398`). Runtime probing matched that: timecode was `null` on Media and Fusion, and present on Cut, Edit, Color, Fairlight, and Deliver (`docs/research/resolve-runtime-probe-results.md`). Timecode is useful context but not enough to claim playback/review as a reliable MVP breakdown, especially because the external polling probe timed out during active playback.

The installed Resolve docs do not expose a Resolve-native API for main-window foreground status or user idle state. The current app uses Windows `GetLastInputInfo` and foreground-window title checks as platform helpers, not Resolve API facts. That is privacy-preserving enough for the MVP because it does not record key presses, mouse coordinates, screen contents, or media contents, but these values should be presented as billability gates rather than Resolve activity categories.

The Workflow Integrations README contains `HasFocus()` and `IsActiveWindow()` APIs (`Workflow Integrations\README.txt:236`, `Workflow Integrations\README.txt:239`), but those belong to integration UI window controls, not the Resolve main app. They should not be used to infer Resolve foreground state.

The scripting README includes `DisableBackgroundTasksForCurrentResolveSession()` (`README.txt:108`), but that is a control API. It is not a readable background-work signal and should not drive dashboard breakdowns.

## Product Guidance

Dashboard:

- Show live Project, Page, state, elapsed Session time, and render state.
- Show total Session time by Project and, if useful, by Page.
- If Page bars are added, title them "Time by Resolve Page" or equivalent. Avoid copy that implies exact creative task intent.
- Keep rendering visually distinct from Page time because it can be billable while idle or unfocused.

CSV export:

- Safe factual fields now: Project, Date, Start, End, Duration, Hours, Page, Activity.
- Page totals are safe if described as totals by recorded Page.
- Rendering totals are safe as a separate activity total.
- Do not add playback/review totals until a later ticket decides and validates a reliable signal.

Data model:

- The current `sessions.page` and `sessions.activity_category` model is acceptable for the MVP.
- Timeline name/id and timecode can remain runtime diagnostics for now. Store them only if a later feature needs timeline-level billing.

## Follow-up

This resolves the trust boundary for #26's dashboard prototype: include Page grouping as factual Page time, include rendering as a separate category, and omit playback/review bars from the first Studio dashboard.
