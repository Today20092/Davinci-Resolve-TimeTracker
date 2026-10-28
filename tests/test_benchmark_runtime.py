import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from scripts.benchmark_runtime import ProcessTree, SdkCalls


ROOT = Path(__file__).resolve().parents[1]


def test_sdk_measurement_counts_nested_calls_failures_and_latency_without_values():
    class Project:
        def GetName(self):
            return "Private project"

        def IsRenderingInProgress(self):
            raise RuntimeError("Private media path")

    class Resolve:
        def GetCurrentProject(self):
            return Project()

    calls = SdkCalls()
    project = calls.wrap(Resolve()).GetCurrentProject()
    assert project.GetName() == "Private project"
    with pytest.raises(RuntimeError):
        project.IsRenderingInProgress()
    report = calls.report()
    assert report["total"] == 3
    assert report["failures"] == 1
    assert report["inflight"] == 0
    assert report["methods"]["GetName"]["calls"] == 1
    assert report["seconds"] >= 0
    assert "Private" not in json.dumps(report)


def test_stop_request_ends_benchmark_worker_without_terminating_resolve_process():
    with tempfile.TemporaryDirectory(prefix="resolve-benchmark-") as tmp:
        db = Path(tmp) / "tracker.sqlite3"
        output = Path(tmp) / "worker.json"
        resolve = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        worker = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "scripts/benchmark_runtime.py"),
                "--worker",
                "--db",
                str(db),
                "--resolve-pid",
                str(resolve.pid),
                "--output",
                str(output),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 15
            while not db.with_suffix(".runtime.json").exists():
                assert worker.poll() is None
                assert time.monotonic() < deadline
                time.sleep(0.05)
            db.with_suffix(".stop").touch()
            worker.wait(timeout=5)
            assert worker.returncode == 0
            assert resolve.poll() is None
            assert json.loads(output.read_text())["observations"] >= 1
        finally:
            for process in (worker, resolve):
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)


def test_live_mode_rejects_a_non_resolve_pid_without_touching_it():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/benchmark_runtime.py"),
            "--live-resolve-pid",
            str(os.getpid()),
            "--seconds",
            "0.2",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 2
    assert "must identify a running Resolve executable" in result.stderr


def test_electron_workload_requires_a_built_frontend_before_starting_workers():
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/benchmark_runtime.py"),
                "--electron",
                "--frontend",
                tmp,
                "--seconds",
                "0.2",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    assert result.returncode == 2
    assert "Electron workload requires a built frontend" in result.stderr


def test_internal_worker_refuses_existing_history_path_before_opening_it():
    with tempfile.TemporaryDirectory() as tmp:
        history = Path(tmp) / "history.sqlite3"
        history.write_bytes(b"existing history must remain untouched")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/benchmark_runtime.py"),
                "--worker",
                "--db",
                str(history),
                "--resolve-pid",
                str(os.getpid()),
                "--output",
                str(Path(tmp) / "output.json"),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2
        assert "fresh temporary benchmark database" in result.stderr
        assert history.read_bytes() == b"existing history must remain untouched"


def test_synthetic_benchmark_labels_its_counters_and_observes_shutdown():
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "result.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "benchmark_runtime.py"),
                "--seconds",
                "0.2",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(output.read_text())
        assert report["resolve_sdk_calls"] is None
        assert report["observations"] >= 1
        assert report["sqlite_write_statements"] > 0
        assert report["sqlite_select_statements"] > 0
        assert report["application_processes_after_exit"] == 0
        assert report["application_process_count"] >= 1
        assert report["process_samples"] >= 2
        assert report["measurement_sources"]["application_process_count"].startswith(
            "OS process snapshots"
        )
        assert (
            report["measurement_sources"]["resolve_sdk_calls"]
            == "not measured: synthetic provider"
        )


def test_process_tree_counts_a_real_child_and_grandchild_then_their_exit():
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
            "print(p.pid,flush=True); time.sleep(30)",
        ],
        stdout=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert child.stdout is not None
    grandchild = int(child.stdout.readline())
    try:
        tree = ProcessTree([child.pid])
        tree.sample()
        assert tree.peak_processes >= 2
        assert tree.peak_working_set_bytes > 0
        assert {child.pid, grandchild} <= tree.seen_pids
    finally:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True
            )
        else:
            import os
            import signal

            os.kill(grandchild, signal.SIGTERM)
            child.terminate()
        child.wait(timeout=5)
    tree.sample()
    assert tree.live_process_count == 0


def test_dashboard_workload_counts_queries_beyond_session_history():
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "dashboard.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "benchmark_runtime.py"),
                "--seconds",
                "0.2",
                "--dashboard-reads",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(output.read_text())
        assert report["dashboard_requests"] >= 1
        assert report["dashboard_sql_select_statements"] > report["history_queries"]
        assert report["observations"] >= 1


@pytest.mark.parametrize("seconds", ["nan", "inf", "0", "-1"])
def test_benchmark_rejects_invalid_duration_before_starting_workers(seconds):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "benchmark_runtime.py"),
            "--seconds",
            seconds,
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert "finite and positive" in result.stderr
