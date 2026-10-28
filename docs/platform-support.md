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

Status: fresh installation, installed dashboard, and repeated Resolve menu launch
verified on Apple Silicon macOS 27.0.1 with Resolve Studio 21.1.1.10; see the
[installation results](research/ticket-54-macos-acceptance.md). Broader runtime
acceptance remains partial; see the [Mac runtime results](research/ticket-58-macos-acceptance.md),
including the blocked SDK child limit after a parent crash.

Install:

```sh
sh install.sh
```

Activity detection:

- Idle time: `ioreg`.
- Foreground app: `osascript` asking System Events for the frontmost process.

macOS may require Accessibility permission for foreground-app detection. If tracking does not pause when switching apps, check macOS privacy permissions.

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
