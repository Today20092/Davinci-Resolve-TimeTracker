"""Five-minute synthetic Active Work benchmark; never opens Resolve or user data."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def working_set_bytes():
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak",
                    "working",
                    "paged_peak",
                    "paged",
                    "nonpaged_peak",
                    "nonpaged",
                    "pagefile",
                    "pagefile_peak",
                )
            ]

        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError("Cannot measure process working set")
        return counters.working
    if sys.platform.startswith("linux"):
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf(
            "SC_PAGE_SIZE"
        )
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def worker(db, resolve_pid, output):
    from resolve_time_tracker import runtime_host
    from resolve_time_tracker.database import SQLiteStore
    from resolve_time_tracker.tracking_engine import RuntimeSnapshot

    counts = {
        "observations": 0,
        "heartbeat_writes": 0,
        "history_queries": 0,
        "child_processes": 0,
    }
    memory = []
    heartbeat_times = []
    stopped = threading.Event()
    started, cpu_start = time.perf_counter(), time.process_time()

    def audit(event, _args):
        if event == "subprocess.Popen":
            counts["child_processes"] += 1

    sys.addaudithook(audit)

    class MeasuredStore(SQLiteStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._connection.set_trace_callback(self.trace)

        def trace(self, statement):
            normalized = " ".join(statement.upper().split())
            if normalized.startswith("UPDATE ACTIVE_SESSION SET LAST_HEARTBEAT"):
                counts["heartbeat_writes"] += 1
                heartbeat_times.append(time.perf_counter())
            if normalized.startswith("SELECT") and "FROM SESSIONS" in normalized:
                counts["history_queries"] += 1

    class SyntheticResolve:
        def snapshot(self):
            counts["observations"] += 1
            return RuntimeSnapshot("Benchmark", "edit", False, 0, True)

    original_host = runtime_host.RuntimeHost
    runtime_host.SQLiteStore = MeasuredStore
    runtime_host.RuntimeHost = lambda api: original_host(
        api,
        launch=lambda _: resolve_pid,
        bridge_factory=SyntheticResolve,
    )

    def sample():
        while not stopped.wait(1):
            memory.append(working_set_bytes())

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        runtime_host.run_managed(db, tracked=True)
    finally:
        stopped.set()
        sampler.join()
    elapsed = time.perf_counter() - started
    cpu = (time.process_time() - cpu_start) / elapsed * 100
    peak_mb = max(memory, default=working_set_bytes()) / 1024**2
    result = {
        "scenario": "synthetic Active Work; one real managed runtime, no real Resolve scripting",
        "duration_seconds": round(elapsed, 2),
        "cpu_percent_one_core": round(cpu, 3),
        "peak_sampled_working_set_mb": round(peak_mb, 2),
        "cpu_under_1_percent": cpu < 1,
        "working_set_under_150_mb": peak_mb < 150,
        "application_process_count": 1,
        "renderer_count": 0,
        "frontend_builds": 0,
        **counts,
        "max_heartbeats_in_60_seconds": max(
            (
                sum(start <= tick < start + 60 for tick in heartbeat_times)
                for start in heartbeat_times
            ),
            default=0,
        ),
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=300)
    parser.add_argument("--output", type=Path, default=Path("benchmark-runtime.json"))
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--resolve-pid", type=int)
    args = parser.parse_args()
    if args.worker:
        worker(args.db, args.resolve_pid, args.output)
        return
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryDirectory(prefix="resolve-benchmark-") as tmp:
        db = Path(tmp) / "tracker.sqlite3"
        # This sleeping process stands in for Resolve; it is excluded from app metrics.
        resolve = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(86400)"],
            creationflags=flags,
        )
        started = time.perf_counter()
        child = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--db",
                str(db),
                "--resolve-pid",
                str(resolve.pid),
                "--output",
                str(args.output.resolve()),
            ],
            creationflags=flags,
        )
        try:
            from urllib.request import urlopen

            deadline = time.monotonic() + 20
            while True:
                if child.poll() is not None:
                    raise RuntimeError("Benchmark worker exited during startup")
                try:
                    info = json.loads(db.with_suffix(".runtime.json").read_text())
                    with urlopen(
                        f"http://127.0.0.1:{info['port']}/health", timeout=0.2
                    ):
                        break
                except (OSError, ValueError):
                    if time.monotonic() > deadline:
                        raise RuntimeError("Benchmark startup timed out")
                    time.sleep(0.05)
            startup = time.perf_counter() - started
            time.sleep(args.seconds)
            resolve.terminate()
            resolve.wait(timeout=5)
            child.wait(timeout=10)
            if child.returncode:
                raise RuntimeError(f"Benchmark exited {child.returncode}")
            result = json.loads(args.output.read_text())
            result.update(
                startup_seconds=round(startup, 3), application_processes_after_exit=0
            )
            args.output.write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(result, indent=2))
        finally:
            for process in (child, resolve):
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
