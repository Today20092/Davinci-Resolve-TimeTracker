# Platform Support

Resolve Time Tracker is intended to run on Windows, macOS, and Linux where DaVinci Resolve Studio supports scripting.

## Windows

Status: verified locally with DaVinci Resolve Studio 21.

Install:

```powershell
.\install.ps1
```

Activity detection:

- Idle time: Win32 `GetLastInputInfo`.
- Foreground app: Win32 foreground-window title.

## macOS

Status: supported in code, needs real-machine smoke testing.

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

Install those tools with your distro package manager for accurate idle/focus tracking. If either tool is missing, the tracker falls back to always-active tracking.

## Resolve Scripting API Paths

Default scripting paths:

```text
Windows: C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting
macOS: /Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting
Linux: /opt/resolve/Developer/Scripting
```

Override with `RESOLVE_SCRIPT_API` if Resolve is installed somewhere else.
