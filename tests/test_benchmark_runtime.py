import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from scripts.benchmark_runtime import ProcessTree


ROOT = Path(__file__).resolve().parents[1]


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
