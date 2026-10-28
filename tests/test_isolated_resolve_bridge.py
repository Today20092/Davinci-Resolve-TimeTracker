import shutil
import os
import json
import multiprocessing
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from resolve_time_tracker.activity_tracker import ActivityState
from resolve_time_tracker.api import ApiState
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.isolated_resolve_bridge import IsolatedResolveBridge
from resolve_time_tracker.runtime_host import RuntimeHost
from resolve_time_tracker.tracked_launch import ProcessWatch
from resolve_time_tracker.tracking_engine import TrackingEngine
from resolve_time_tracker.tracking_runtime import TrackingRuntime


class Active:
    def snapshot(self):
        return ActivityState(0, True)


def sdk_file(tmp_path):
    module = tmp_path / "sdk.py"
    shutil.copyfile(
        Path(__file__).parent / "fixtures/gil_holding_resolve_sdk.py", module
    )
    return module


def ready_snapshot(bridge):
    deadline = time.monotonic() + 10
    while True:
        try:
            return bridge.snapshot()
        except TimeoutError:
            assert time.monotonic() < deadline
            time.sleep(0.05)


@pytest.mark.skipif(os.name != "nt", reason="Windows job ownership acceptance")
def test_hard_parent_exit_kills_its_gil_blocked_sdk_child(tmp_path):
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    report = tmp_path / "parent.json"
    parent = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures/isolated_sdk_parent.py"),
            str(sdk_file(tmp_path)),
            str(report),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    watch = None
    handle = None
    try:
        deadline = time.monotonic() + 15
        while not report.exists():
            assert parent.poll() is None, parent.communicate(timeout=1)[1]
            assert time.monotonic() < deadline
            time.sleep(0.01)
        child_pid = json.loads(report.read_text())["sdk_reader_pid"]
        watch = ProcessWatch(child_pid)
        handle = kernel.OpenProcess(0x00100001, False, child_pid)
        assert handle and watch.alive()
        assert (tmp_path / "entered").exists()
        parent.terminate()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 1
        while watch.alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not watch.alive()
    finally:
        if parent.poll() is None:
            parent.terminate()
        parent.wait(timeout=5)
        if handle:
            if watch is not None and watch.alive():
                kernel.TerminateProcess(handle, 1)
            kernel.CloseHandle(handle)
        if watch is not None:
            watch.close()
        if parent.stderr is not None:
            parent.stderr.close()


def test_dead_sdk_child_is_reaped_before_a_replacement_can_recover(tmp_path):
    bridge = IsolatedResolveBridge(sdk_file(tmp_path), Active(), timeout_seconds=1)
    try:
        assert ready_snapshot(bridge).project_name == "Test project"
        child_pid = bridge.diagnostics()["sdk_reader_pid"]
        child = next(p for p in multiprocessing.active_children() if p.pid == child_pid)
        child.terminate()
        child.join(timeout=5)
        with pytest.raises(RuntimeError, match="exited"):
            bridge.snapshot()
        assert ready_snapshot(bridge).project_name == "Test project"
        assert bridge.diagnostics()["sdk_reader_pid"] != child_pid
    finally:
        bridge.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows job ownership acceptance")
def test_job_setup_failure_stops_child_before_any_sdk_request(tmp_path):
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    bridge = IsolatedResolveBridge(sdk_file(tmp_path), Active(), timeout_seconds=1)
    (tmp_path / "block").touch()
    try:
        with (
            patch("ctypes.WinDLL", return_value=kernel),
            patch.object(kernel, "SetInformationJobObject", return_value=False),
            pytest.raises(OSError),
        ):
            bridge.snapshot()
        assert not bridge.diagnostics()["sdk_reader_alive"]
        assert not (tmp_path / "entered").exists()
    finally:
        bridge.close()


def test_managed_runtime_uses_an_owned_sdk_child_by_default(tmp_path, monkeypatch):
    modules = tmp_path / "Modules"
    modules.mkdir()
    shutil.copyfile(sdk_file(tmp_path), modules / "DaVinciResolveScript.py")
    monkeypatch.setenv("RESOLVE_SCRIPT_API", str(tmp_path))
    with SQLiteStore(tmp_path / "db", check_same_thread=False) as store:
        api = ApiState(store)
        host = RuntimeHost(api, alive=lambda _: True, launch=lambda _: os.getpid())
        try:
            host.track()
            deadline = time.monotonic() + 5
            while not api.diagnostics().get("sdk_reader_pid"):
                assert time.monotonic() < deadline
                time.sleep(0.01)
            assert api.diagnostics()["sdk_reader_pid"] != os.getpid()
        finally:
            host.stop_tracking()


def test_gil_holding_sdk_child_cannot_stall_status_pause_or_stop(tmp_path):
    bridge = IsolatedResolveBridge(sdk_file(tmp_path), Active(), timeout_seconds=1)
    with SQLiteStore(tmp_path / "db", check_same_thread=False) as store:
        runtime = TrackingRuntime(TrackingEngine(store, snapshot_provider=bridge))
        api = ApiState(store, tracking_engine=runtime.engine, tracking_runtime=runtime)
        try:
            assert ready_snapshot(bridge).project_name == "Test project"
            assert runtime.observe()
            (tmp_path / "block").touch()
            runtime.start()
            deadline = time.monotonic() + 5
            while not (tmp_path / "entered").exists():
                assert time.monotonic() < deadline
                time.sleep(0.01)
            started = time.monotonic()
            assert api.status()["project"] == "Test project"
            assert api.pause()["tracking_status"] == "paused"
            assert time.monotonic() - started < 0.5
            child_pid = bridge.diagnostics()["sdk_reader_pid"]
            assert child_pid is not None
            started = time.monotonic()
            runtime.stop()
            bridge.close()
            assert time.monotonic() - started < 2.5
            assert not bridge.diagnostics()["sdk_reader_alive"]
        finally:
            runtime.stop()
            bridge.close()


def test_pending_sdk_call_reuses_one_child_and_discards_its_late_reply(tmp_path):
    bridge = IsolatedResolveBridge(sdk_file(tmp_path), Active(), timeout_seconds=1)
    try:
        assert ready_snapshot(bridge).project_name == "Test project"
        child_pid = bridge.diagnostics()["sdk_reader_pid"]
        (tmp_path / "block").touch()
        with pytest.raises(TimeoutError):
            bridge.snapshot()
        assert bridge.diagnostics()["sdk_reader_pending"]
        late_seen = False
        for _ in range(3):
            with pytest.raises(TimeoutError) as failure:
                bridge.snapshot()
            assert bridge.diagnostics()["sdk_reader_pid"] == child_pid
            late_seen = "late" in str(failure.value)
            if late_seen:
                break
        (tmp_path / "block").unlink()
        deadline = time.monotonic() + 5
        while not late_seen:
            with pytest.raises(TimeoutError) as failure:
                bridge.snapshot()
            late_seen = "late" in str(failure.value)
            assert time.monotonic() < deadline
            time.sleep(0.05)
        snapshot = ready_snapshot(bridge)
        assert snapshot.project_name == "Test project"
        assert snapshot.resolve_is_foreground
        assert bridge.diagnostics()["sdk_reader_pid"] == child_pid
    finally:
        bridge.close()
