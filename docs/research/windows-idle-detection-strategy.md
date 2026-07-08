# Windows Idle Detection Strategy

Date: 2026-07-08

## Decision

Use direct Win32 idle detection from the Resolve-launched Python companion via `ctypes`:

- Call `user32.GetLastInputInfo` to read the tick count for the current Windows session's last input event.
- Compare it with the current tick count using unsigned 32-bit subtraction, because `LASTINPUTINFO.dwTime` is a `DWORD`.
- Keep the idle timeout outside the platform helper; the helper should only return elapsed idle seconds or an unavailable/error result.

Do not add a helper process for the MVP. Add one only if Resolve's embedded Python cannot call `ctypes`/`user32.dll` reliably in the Phase 1 runtime.

## API Boundary

Keep the cross-platform boundary this small:

```python
class IdleProbe(Protocol):
    def idle_seconds(self) -> float | None:
        ...
```

`None` means the platform probe is unavailable or failed. The Session Engine can then avoid silently treating unknown idle state as active work.

Windows implementation name: `WindowsIdleProbe`.

Future macOS/Linux implementations should satisfy the same boundary. They do not need to match the Windows mechanism.

## Privacy

This strategy collects only a duration: milliseconds since the last input event in the current Windows session. It must never collect:

- keystrokes
- mouse coordinates
- window text
- screen contents
- media metadata
- raw input event history

No keyboard hooks, mouse hooks, `GetAsyncKeyState`, or screen/UI scraping are needed for idle detection.

## Notes

Microsoft documents `GetLastInputInfo` as useful for idle detection and as session-specific, not system-wide across all running sessions. That scope is acceptable for the MVP because Resolve Time Tracker runs in the editor's interactive session.

`LASTINPUTINFO.dwTime` is a `DWORD`, so the implementation should handle 32-bit wraparound with unsigned subtraction. For MVP idle thresholds measured in minutes, this is enough; there is no need for a higher-resolution timer or persistent input monitor.

## Sources

- Microsoft Learn: [`GetLastInputInfo`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlastinputinfo)
- Microsoft Learn: [`LASTINPUTINFO`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-lastinputinfo)
- Microsoft Learn: [`GetTickCount`](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-gettickcount)
