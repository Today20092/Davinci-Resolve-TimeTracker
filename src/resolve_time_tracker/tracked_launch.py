"""Start one headless tracker for a user-initiated Resolve session."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from resolve_time_tracker.database import SQLiteStore


DEFAULT_RESOLVE_EXECUTABLE = Path(
    r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
)


class LaunchError(RuntimeError):
    pass


@dataclass(frozen=True)
class LaunchResult:
    attached: bool = False
    reused_runtime: bool = False


def valid_resolve_executable(candidate: Path | None) -> bool:
    return bool(
        candidate
        and candidate.is_file()
        and candidate.name == "Resolve.exe"
    )


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
                            path if path.name.lower() == "resolve.exe" else path / "Resolve.exe"
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
    for candidate in [store.resolve_executable(), conventional, *registry_candidates()]:
        if valid_resolve_executable(candidate):
            return candidate
    return None


def select_resolve_executable() -> Path | None:
    try:
        from tkinter import Tk, filedialog

        root = Tk()
        root.withdraw()
        selected = filedialog.askopenfilename(
            title="Select DaVinci Resolve",
            filetypes=[("DaVinci Resolve", "Resolve.exe")],
        )
        root.destroy()
    except Exception as exc:
        raise LaunchError(
            "DaVinci Resolve was not found. Select Resolve.exe in the dashboard settings."
        ) from exc
    return Path(selected) if selected else None


def find_running_resolve() -> int | None:
    if os.name != "nt":
        return None
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Resolve.exe", "/FO", "CSV", "/NH"],
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    for row in csv.reader(output.splitlines()):
        if len(row) > 1 and row[0].lower() == "resolve.exe":
            try:
                return int(row[1])
            except ValueError:
                continue
    return None


def wait_for_resolve_exit(process_id: int) -> None:
    if os.name != "nt":
        return
    import ctypes

    synchronize = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, process_id)
    if not handle:
        raise LaunchError("DaVinci Resolve closed before tracking could start.")
    try:
        ctypes.windll.kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


@contextmanager
def _runtime_lock(db_path: Path) -> Iterator[bool]:
    lock_path = db_path.with_suffix(".runtime.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            owner = int(lock_path.read_text(encoding="utf-8"))
            os.kill(owner, 0)
        except (OSError, ValueError):
            try:
                lock_path.unlink()
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                yield False
                return
        else:
            yield False
            return
    try:
        os.write(descriptor, str(os.getpid()).encode())
        yield True
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _tracker_command(db_path: Path) -> list[str]:
    script = Path(__file__).resolve().parents[2] / "scripts" / "ResolveTimeTracker.py"
    return [str(Path(sys.executable)), str(script), "--tracker", "--db", str(db_path)]


def _stop_tracker(process: subprocess.Popen[object]) -> None:
    if getattr(process, "poll", lambda: None)() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def launch_tracking(
    db_path: Path,
    *,
    conventional: Path = DEFAULT_RESOLVE_EXECUTABLE,
    registry_candidates: Callable[[], list[Path]] = registry_resolve_candidates,
    select_executable: Callable[[], Path | None] = select_resolve_executable,
    find_running: Callable[[], int | None] = find_running_resolve,
    start_process: Callable[[list[str]], subprocess.Popen[object]] = subprocess.Popen,
    wait_for_exit: Callable[[int], None] = wait_for_resolve_exit,
) -> LaunchResult:
    """Run tracking until the selected Resolve process exits."""
    db_path = Path(db_path)
    with _runtime_lock(db_path) as owns_runtime:
        if not owns_runtime:
            return LaunchResult(reused_runtime=True)

        running_process = find_running()
        attached = running_process is not None
        tracker: subprocess.Popen[object] | None = None
        try:
            with SQLiteStore(db_path) as store:
                executable = discover_resolve_executable(
                    store,
                    conventional=conventional,
                    registry_candidates=registry_candidates,
                )
                if executable is None and not attached:
                    executable = select_executable()
                    if not valid_resolve_executable(executable):
                        raise LaunchError(
                            "DaVinci Resolve was not found. Select the Resolve.exe executable."
                        )
                    store.set_resolve_executable(executable)

            if attached:
                process_id = running_process
            else:
                assert executable is not None
                process_id = start_process([str(executable)]).pid
            tracker = start_process(_tracker_command(db_path))
            wait_for_exit(process_id)
            return LaunchResult(attached=attached)
        except (LaunchError, OSError, subprocess.SubprocessError) as exc:
            raise LaunchError(f"Unable to start Resolve Time Tracker: {exc}") from exc
        finally:
            if tracker is not None:
                _stop_tracker(tracker)
            # A forced Resolve exit cannot report a final observation. The heartbeat is
            # the last trustworthy billable instant for both normal and unexpected exits.
            with SQLiteStore(db_path) as store:
                store.recover_active_session()
