"""Keep a GIL-holding Resolve SDK call outside the tracking interpreter."""

from __future__ import annotations

import multiprocessing
import os
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from resolve_time_tracker.activity_tracker import ActivityState, default_activity_probe
from resolve_time_tracker.resolve_bridge import ResolveBridge
from resolve_time_tracker.tracking_runtime import STALE_HEARTBEAT_SECONDS


class _WindowsJob:
    def __init__(self, process_handle):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_longlong),
                ("job_time", ctypes.c_longlong),
                ("flags", wintypes.DWORD),
                ("minimum_working_set", ctypes.c_size_t),
                ("maximum_working_set", ctypes.c_size_t),
                ("active_processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimits),
                ("io_counters", ctypes.c_ulonglong * 6),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t),
                ("peak_job_memory", ctypes.c_size_t),
            ]

        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self._kernel.SetInformationJobObject.restype = wintypes.BOOL
        self._kernel.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        self._kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self._kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self._handle = self._kernel.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self._kernel.SetInformationJobObject(
                self._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ) or not self._kernel.AssignProcessToJobObject(
                self._handle, process_handle
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.close()
            raise

    def close(self):
        if self._handle:
            self._kernel.CloseHandle(self._handle)
            self._handle = None


class _NoActivity:
    def snapshot(self):
        return ActivityState(None, None)


def _read_sdk(connection, module_path, parent_pid):
    from resolve_time_tracker.tracked_launch import ProcessWatch

    parent = ProcessWatch(parent_pid)
    bridge = ResolveBridge(module_path, activity_probe=_NoActivity())
    try:
        while parent.alive():
            if not connection.poll(1):
                continue
            if connection.recv() is None:
                break
            try:
                result = bridge.snapshot()
                error = None
            except Exception as exc:
                result = None
                error = type(exc).__name__
            connection.send((result, error, bridge.diagnostics()))
    except (EOFError, OSError):
        pass
    finally:
        bridge.close()
        parent.close()
        connection.close()


class IsolatedResolveBridge:
    def __init__(
        self,
        module_path: str | Path | None = None,
        activity_probe: Any | None = None,
        *,
        timeout_seconds: float = STALE_HEARTBEAT_SECONDS,
    ):
        self.module_path = module_path
        self.activity_probe = activity_probe or default_activity_probe()
        self._timeout = timeout_seconds
        self._requests = threading.Lock()
        self._lifecycle = threading.RLock()
        self._closed = threading.Event()
        self._process = None
        self._connection = None
        self._pending = False
        self._diagnostics: dict[str, Any] = {}
        self._pid = None
        self._job = None

    def _start(self):
        with self._lifecycle:
            if self._closed.is_set():
                raise RuntimeError("Resolve SDK reader is closed")
            self._start_reader()

    def _start_reader(self):
        context = multiprocessing.get_context("spawn")
        connection, child_connection = context.Pipe()
        process = context.Process(
            target=_read_sdk,
            args=(child_connection, self.module_path, os.getpid()),
            daemon=True,
            name="Resolve SDK reader",
        )
        try:
            process.start()
            self._process = process
            self._connection = connection
            self._pid = process.pid
            if os.name == "nt":
                self._job = _WindowsJob(process.sentinel)
        except Exception:
            if self._process is not None:
                self._pending = True
                self._close_reader()
            else:
                connection.close()
                process.close()
            raise
        finally:
            child_connection.close()

    def snapshot(self):
        with self._requests:
            if self._closed.is_set():
                raise RuntimeError("Resolve SDK reader is closed")
            if self._process is None:
                self._start()
            connection = self._connection
            assert connection is not None
            try:
                if self._pending:
                    if not connection.poll(0):
                        raise TimeoutError("Resolve SDK observation is still pending")
                    _, _, self._diagnostics = connection.recv()
                    self._pending = False
                    raise TimeoutError("Discarded a late Resolve SDK observation")
                connection.send("snapshot")
                self._pending = True
                if not connection.poll(self._timeout):
                    raise TimeoutError(
                        "Resolve SDK observation exceeded freshness limit"
                    )
                snapshot, error, self._diagnostics = connection.recv()
                self._pending = False
            except TimeoutError:
                raise
            except (EOFError, OSError) as exc:
                with self._lifecycle:
                    self._close_reader()
                raise RuntimeError("Resolve SDK reader exited") from exc
            if self._closed.is_set():
                raise RuntimeError("Resolve SDK reader is closed")
            if error:
                self._set_present(False)
                raise RuntimeError(f"Resolve SDK read failed ({error})")
            self._set_present(True)
            activity_snapshot = getattr(self.activity_probe, "snapshot", None)
            activity = (
                activity_snapshot()
                if callable(activity_snapshot)
                else ActivityState(
                    self.activity_probe.idle_seconds(),
                    self.activity_probe.resolve_is_foreground(),
                    getattr(self.activity_probe, "unavailable_reason", None),
                )
            )
            return replace(
                snapshot,
                idle_seconds=activity.idle_seconds,
                resolve_is_foreground=activity.resolve_is_foreground,
                activity_unavailable_reason=activity.unavailable_reason,
            )

    def _set_present(self, present):
        setter = getattr(self.activity_probe, "set_resolve_present", None)
        if callable(setter):
            setter(present)

    def diagnostics(self):
        process = self._process
        try:
            alive = process is not None and process.is_alive()
        except ValueError:
            alive = False
        return {
            **self._diagnostics,
            "sdk_reader_pid": self._pid,
            "sdk_reader_pending": self._pending,
            "sdk_reader_alive": alive,
            "activity_unavailable_reason": getattr(
                self.activity_probe, "unavailable_reason", None
            ),
        }

    def close(self):
        if self._closed.is_set():
            return
        self._closed.set()
        with self._lifecycle:
            self._close_reader()
        self._set_present(False)
        close = getattr(self.activity_probe, "close", None)
        if callable(close):
            close()

    def _close_reader(self):
        process, connection = self._process, self._connection
        if process is not None:
            if not self._pending and connection is not None:
                try:
                    connection.send(None)
                except (EOFError, OSError):
                    pass
                process.join(timeout=0.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            if process.is_alive():
                raise RuntimeError("Could not stop the owned Resolve SDK reader")
            process.close()
            self._process = None
        if connection is not None:
            connection.close()
        self._connection = None
        self._pending = False
        if self._job is not None:
            self._job.close()
            self._job = None
