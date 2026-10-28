import shutil
import os
import time
from pathlib import Path

import pytest

from resolve_time_tracker.activity_tracker import ActivityState
from resolve_time_tracker.api import ApiState
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.isolated_resolve_bridge import IsolatedResolveBridge
from resolve_time_tracker.runtime_host import RuntimeHost
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
        assert bridge.snapshot().project_name == "Test project"
        child_pid = bridge.diagnostics()["sdk_reader_pid"]
        (tmp_path / "block").touch()
        with pytest.raises(TimeoutError):
            bridge.snapshot()
        assert bridge.diagnostics()["sdk_reader_pending"]
        for _ in range(3):
            with pytest.raises(TimeoutError):
                bridge.snapshot()
            assert bridge.diagnostics()["sdk_reader_pid"] == child_pid
        (tmp_path / "block").unlink()
        time.sleep(2.2)
        with pytest.raises(TimeoutError, match="late"):
            bridge.snapshot()
        snapshot = bridge.snapshot()
        assert snapshot.project_name == "Test project"
        assert snapshot.resolve_is_foreground
        assert bridge.diagnostics()["sdk_reader_pid"] == child_pid
    finally:
        bridge.close()
