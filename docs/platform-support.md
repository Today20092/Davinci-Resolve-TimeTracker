# Platform Support

Resolve Time Tracker is intended to run on Windows, macOS, and Linux where DaVinci Resolve Studio supports scripting.

## Windows

Status: locally exercised with DaVinci Resolve Studio 21.1.1.10. Playback can block SDK observations and undercount time; see the [acceptance results](research/ticket-52-acceptance.md). This is source-preview evidence, not complete billing or clean-machine certification.

Install:

```powershell
.\install.ps1
```

Activity detection:

- Idle time: Win32 `GetLastInputInfo`.
- Foreground app: Win32 foreground-window title.

## macOS

Status: local smoke tests passed on Apple Silicon macOS 27.0.1 with Resolve
Studio 21.1.1.10. Current development includes the Mac foreground process-name
fix; published `v0.1.2-alpha.1` predates it. Fresh installation, installed launch,
foreground/page tracking, idle pause/resume, permission denial/recovery, rendering,
and normal process ownership have live evidence. See the
[installation results](research/ticket-54-macos-acceptance.md) and
[Mac runtime results](research/ticket-58-macos-acceptance.md).

These results cover one Mac configuration. A controlled foreground playback run
recorded 51 seconds during a 51.027-second measurement window; broader exact
billing accuracy remains unqualified. After a parent crash, a blocked SDK child
can survive until its SDK call returns. Normal shutdown stops the owned child.

Install:

```sh
sh install.sh
```

Activity detection:

- Idle time: `ioreg`.
- Foreground app: `osascript` asking System Events for the frontmost process.

macOS may request permission to automate System Events for foreground detection.
Check **System Settings > Privacy & Security > Automation** under the application
that launched the tracker. Denying that permission pauses billable tracking.

## Linux

Status: supported in code, needs real-machine smoke testing.

Install:

```sh
sh install.sh
```

Activity detection:

- Idle time: `xprintidle`.
- Foreground app: `xdotool getactivewindow getwindowname`.

Install those tools with your distro package manager for X11 idle/focus tracking. If either tool is missing or activity cannot be read, billable tracking pauses. Wayland activity detection is unavailable.

## Resolve Scripting API Paths

Default scripting paths:

```text
Windows: C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting
macOS: /Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting
Linux: /opt/resolve/Developer/Scripting
```

Override with `RESOLVE_SCRIPT_API` if Resolve is installed somewhere else.
