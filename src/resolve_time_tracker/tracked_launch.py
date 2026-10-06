"""Start one headless tracker for a user-initiated Resolve session."""

from __future__ import annotations

import csv
import os
import subprocess
import ctypes
import select
import platform
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from resolve_time_tracker.database import SQLiteStore


DEFAULT_RESOLVE_EXECUTABLE = Path(
    r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
    if os.name == "nt"
    else "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve"
    if platform.system() == "Darwin"
    else "/opt/resolve/bin/resolve"
)


class LaunchError(RuntimeError):
    pass


def valid_resolve_executable(candidate: Path | None) -> bool:
    names = (
        {"Resolve.exe"} if os.name == "nt" else {"Resolve", "resolve", "Resolve.exe"}
    )
    return bool(candidate and candidate.is_file() and candidate.name in names)


def registry_resolve_candidates() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    candidates: list[Path] = []
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key_name in (
            r"SOFTWARE\Blackmagic Design\DaVinci Resolve",
            r"SOFTWARE\WOW6432Node\Blackmagic Design\DaVinci Resolve",
        ):
            try:
                with winreg.OpenKey(root, key_name) as key:
                    for value_name in ("InstallPath", "InstallDir", "Path"):
                        try:
                            value, _ = winreg.QueryValueEx(key, value_name)
                        except OSError:
                            continue
                        path = Path(str(value))
                        candidates.append(
                            path
                            if path.name.lower() == "resolve.exe"
                            else path / "Resolve.exe"
                        )
            except OSError:
                continue
    return candidates


def discover_resolve_executable(
    store: SQLiteStore,
    *,
    conventional: Path = DEFAULT_RESOLVE_EXECUTABLE,
    registry_candidates: Callable[[], list[Path]] = registry_resolve_candidates,
) -> Path | None:
    for candidate in (store.resolve_executable(), conventional):
        if valid_resolve_executable(candidate):
            return candidate
    for candidate in registry_candidates():
        if valid_resolve_executable(candidate):
            return candidate
    return None


def select_resolve_executable() -> Path | None:
    try:
        if os.name == "nt":
            # Native Windows picker also works with uv Python builds without Tk.
            selected = subprocess.check_output(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-STA",
                    "-Command",
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$picker = New-Object System.Windows.Forms.OpenFileDialog; "
                    "$picker.Title = 'Select DaVinci Resolve'; "
                    "$picker.Filter = 'DaVinci Resolve|Resolve.exe'; "
                    "try { if ($picker.ShowDialog() -eq 'OK') { $picker.FileName } } finally { $picker.Dispose() }",
                ],
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).strip()
            return Path(selected) if selected else None
        from tkinter import Tk, filedialog

        root = Tk()
        root.withdraw()
        selected = filedialog.askopenfilename(
            title="Select DaVinci Resolve",
            filetypes=[
                (
                    "DaVinci Resolve",
                    "Resolve.exe" if os.name == "nt" else "Resolve resolve",
                )
            ],
        )
        root.destroy()
    except Exception as exc:
        raise LaunchError(
            "DaVinci Resolve was not found and the file picker is unavailable. "
            + (
                "Check that Windows PowerShell is available, then run Tracked Launch again."
                if os.name == "nt"
                else "Install Python with Tk support, then run Tracked Launch again."
            )
        ) from exc
    return Path(selected) if selected else None


def find_running_resolve() -> int | None:
    if os.name != "nt":
        try:
            output = subprocess.check_output(
                [
                    "pgrep",
                    "-x",
                    "Resolve" if platform.system() == "Darwin" else "resolve",
                ],
                text=True,
                timeout=2,
            )
            return int(output.splitlines()[0]) if output.strip() else None
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Resolve.exe", "/FO", "CSV", "/NH"],
            text=True,
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for row in csv.reader(output.splitlines()):
        if len(row) > 1 and row[0].lower() == "resolve.exe":
            try:
                return int(row[1])
            except ValueError:
                continue
    return None


def process_alive(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if os.name == "nt":
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, process_id)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(process_id, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class ProcessWatch:
    """Keep an OS process identity so PID reuse cannot extend a session."""

    def __init__(self, pid: int):
        self._handle = None
        self._pidfd = None
        self._queue = None
        if pid <= 0:
            return
        try:
            if os.name == "nt":
                from ctypes import wintypes

                self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                self._kernel.OpenProcess.argtypes = [
                    wintypes.DWORD,
                    wintypes.BOOL,
                    wintypes.DWORD,
                ]
                self._kernel.OpenProcess.restype = wintypes.HANDLE
                self._kernel.WaitForSingleObject.argtypes = [
                    wintypes.HANDLE,
                    wintypes.DWORD,
                ]
                self._kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                self._handle = self._kernel.OpenProcess(0x00100000, False, pid)
            elif hasattr(os, "pidfd_open"):
                self._pidfd = os.pidfd_open(pid)
            elif hasattr(select, "kqueue"):
                self._queue = select.kqueue()
                event = select.kevent(
                    pid,
                    filter=select.KQ_FILTER_PROC,
                    flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                    fflags=select.KQ_NOTE_EXIT,
                )
                self._queue.control([event], 0, 0)
        except OSError:
            self.close()

    def alive(self) -> bool:
        if self._handle:
            return self._kernel.WaitForSingleObject(self._handle, 0) == 258
        if self._pidfd is not None:
            return not select.select([self._pidfd], [], [], 0)[0]
        if self._queue is not None:
            if not self._queue.control(None, 1, 0):
                return True
            self.close()
        return False

    def close(self) -> None:
        if self._handle:
            self._kernel.CloseHandle(self._handle)
            self._handle = None
        if self._pidfd is not None:
            os.close(self._pidfd)
            self._pidfd = None
        if self._queue is not None:
            self._queue.close()
            self._queue = None


@contextmanager
def _runtime_lock(db_path: Path) -> Iterator[bool]:
    lock_path = db_path.with_suffix(".runtime.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # OS locks release on crashes. Never unlink a lock another launcher can open.
    with lock_path.open("a+b") as lock:
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True


def start_resolve(
    store: SQLiteStore,
    *,
    conventional: Path = DEFAULT_RESOLVE_EXECUTABLE,
    registry_candidates: Callable[[], list[Path]] = registry_resolve_candidates,
    select_executable: Callable[[], Path | None] = select_resolve_executable,
    find_running: Callable[[], int | None] = find_running_resolve,
    start_process: Callable[[list[str]], subprocess.Popen] = subprocess.Popen,
) -> int:
    """Find or start Resolve; the caller owns tracking in this same process."""
    running = find_running()
    if running is not None:
        return running
    executable = discover_resolve_executable(
        store, conventional=conventional, registry_candidates=registry_candidates
    )
    if executable is None:
        executable = select_executable()
    if not valid_resolve_executable(executable):
        raise LaunchError(
            "DaVinci Resolve was not found. Select the Resolve.exe executable."
        )
    assert executable is not None
    store.set_resolve_executable(executable)
    try:
        return start_process([str(executable)]).pid
    except OSError as exc:
        raise LaunchError(f"Could not launch DaVinci Resolve: {exc}") from exc


def launch_tracking(db_path: Path) -> None:
    from resolve_time_tracker.runtime_host import run_managed

    run_managed(db_path, tracked=True)
