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
        except Exception:
            connection.close()
            process.close()
            raise
        finally:
            child_connection.close()
        self._connection = connection
        self._process = process
        self._pid = process.pid

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
