"""Five-minute synthetic Active Work benchmark; never opens Resolve or user data."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def process_snapshot():
    """Read OS process accounting; the sampler process is not part of the app tree."""
    if os.name == "nt":
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                "[Console]::OutputEncoding = [Text.UTF8Encoding]::new(); "
                "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,"
                "WorkingSetSize,KernelModeTime,UserModeTime,CommandLine,CreationDate | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            encoding="utf-8",
            check=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        rows = json.loads(result.stdout)
        return {
            int(row["ProcessId"]): {
                "parent": int(row["ParentProcessId"]),
                "memory": int(row["WorkingSetSize"])
                if row["WorkingSetSize"] is not None
                else None,
                "cpu": (int(row["KernelModeTime"]) + int(row["UserModeTime"]))
                / 10_000_000
                if row["KernelModeTime"] is not None and row["UserModeTime"] is not None
                else None,
                "command": row["CommandLine"],
                "identity": row["CreationDate"],
            }
            for row in (rows if isinstance(rows, list) else [rows])
        }
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,rss=,time=,stat=,lstart=,args="],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    processes = {}
    for line in result.stdout.splitlines():
        fields = line.split(None, 10)
        if len(fields) != 11 or fields[4].startswith("Z"):
            continue
        elapsed = fields[3].split("-")
        days = int(elapsed[0]) if len(elapsed) == 2 else 0
        seconds = 0.0
        for part in elapsed[-1].split(":"):
            seconds = seconds * 60 + float(part)
        processes[int(fields[0])] = {
            "parent": int(fields[1]),
            "memory": int(fields[2]) * 1024,
            "cpu": days * 86400 + seconds,
            "command": fields[10],
            "identity": " ".join(fields[5:10]),
        }
    return processes


class ProcessTree:
    def __init__(self, roots):
        self.roots = set(roots)
        self.seen_pids = set()
        self.cpu_seconds = {}
        self.identities = {}
        self.peak_processes = 0
        self.peak_working_set_bytes = 0
        self.peak_renderers = 0
        self.renderer_commands_available = True
        self.live_process_count = 0
        self.samples = 0

    def sample(self):
        snapshot = process_snapshot()
        owned = {
            pid
            for pid in (self.roots | self.seen_pids) & snapshot.keys()
            if pid not in self.identities
            or self.identities[pid] == snapshot[pid]["identity"]
        }
        while True:
            children = {pid for pid, row in snapshot.items() if row["parent"] in owned}
            if children <= owned:
                break
            owned |= children
        self.seen_pids |= owned
        if any(
            snapshot[pid][field] is None for pid in owned for field in ("memory", "cpu")
        ):
            raise RuntimeError(
                "OS resource accounting is unavailable for an application process"
            )
        self.live_process_count = len(owned)
        self.peak_processes = max(self.peak_processes, len(owned))
        self.peak_working_set_bytes = max(
            self.peak_working_set_bytes, sum(snapshot[pid]["memory"] for pid in owned)
        )
        self.renderer_commands_available &= all(
            snapshot[pid]["command"] is not None for pid in owned
        )
        self.peak_renderers = max(
            self.peak_renderers,
            sum("--type=renderer" in (snapshot[pid]["command"] or "") for pid in owned),
        )
        for pid in owned:
            self.identities[pid] = snapshot[pid]["identity"]
            identity = (pid, snapshot[pid]["identity"])
            self.cpu_seconds[identity] = max(
                self.cpu_seconds.get(identity, 0), snapshot[pid]["cpu"]
            )
        self.samples += 1


def worker(db, resolve_pid, output):
    from resolve_time_tracker import api, runtime_host
    from resolve_time_tracker.database import SQLiteStore
    from resolve_time_tracker.tracking_engine import RuntimeSnapshot

    counts = {
        "observations": 0,
        "heartbeat_writes": 0,
        "history_queries": 0,
        "child_processes": 0,
        "sqlite_select_statements": 0,
        "sqlite_write_statements": 0,
        "frontend_builds": 0,
        "dashboard_requests": 0,
        "dashboard_sql_select_statements": 0,
    }
    query_context = threading.local()
    heartbeat_times = []
    started = time.perf_counter()

    def audit(event, args):
        if event == "subprocess.Popen":
            counts["child_processes"] += 1
            command = args[1]
            if not isinstance(command, str):
                command = " ".join(str(arg) for arg in command)
            command = command.lower()
            if "build" in command and any(tool in command for tool in ("npm", "vite")):
                counts["frontend_builds"] += 1

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
            if normalized.startswith("SELECT"):
                counts["sqlite_select_statements"] += 1
                if getattr(query_context, "dashboard", False):
                    counts["dashboard_sql_select_statements"] += 1
            if normalized.startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
                counts["sqlite_write_statements"] += 1

    class SyntheticResolve:
        def snapshot(self):
            counts["observations"] += 1
            return RuntimeSnapshot("Benchmark", "edit", False, 0, True)

    class MeasuredApiState(api.ApiState):
        def dashboard(self):
            counts["dashboard_requests"] += 1
            query_context.dashboard = True
            try:
                return super().dashboard()
            finally:
                query_context.dashboard = False

    original_host = runtime_host.RuntimeHost
    with (
        patch.object(api, "ApiState", MeasuredApiState),
        patch.object(runtime_host, "SQLiteStore", MeasuredStore),
        patch.object(
            runtime_host,
            "RuntimeHost",
            lambda state: original_host(
                state,
                launch=lambda _: resolve_pid,
                bridge_factory=SyntheticResolve,
            ),
        ),
    ):
        runtime_host.run_managed(db, tracked=True)
    elapsed = time.perf_counter() - started
    result = {
        "scenario": "synthetic Active Work; one real managed runtime, no real Resolve scripting",
        "duration_seconds": round(elapsed, 2),
        "resolve_sdk_calls": None,
        "sampling_limitations": "OS snapshots can miss short-lived children and their final CPU time; resident memory is a sampled peak. Benchmark monitoring overhead is excluded from the application tree.",
        "measurement_sources": {
            "resolve_sdk_calls": "not measured: synthetic provider",
            "observations": "synthetic snapshot provider invocations",
            "sqlite_select_statements": "SQLite trace after connection initialization",
            "sqlite_write_statements": "SQLite INSERT/UPDATE/DELETE/REPLACE statements after connection initialization",
            "history_queries": "SQLite SELECT statements containing FROM SESSIONS",
            "child_processes": "Python subprocess audit events in managed runtime",
            "frontend_builds": "Python subprocess audit events containing npm/pnpm/vite build; excludes descendants launched by Node",
            "dashboard_requests": "calls to the public dashboard read interface",
            "dashboard_sql_select_statements": "all SQLite SELECT statements executed during dashboard reads",
        },
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
    parser.add_argument(
        "--dashboard-reads",
        action="store_true",
        help="Exercise HTTP dashboard queries without launching Electron; not renderer profiling",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--resolve-pid", type=int)
    args = parser.parse_args()
    if args.worker:
        worker(args.db, args.resolve_pid, args.output)
        return
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be finite and positive")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryDirectory(prefix="resolve-benchmark-") as tmp:
        db = Path(tmp) / "tracker.sqlite3"
        worker_output = Path(tmp) / "worker.json"
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
                str(worker_output),
            ],
            creationflags=flags,
        )
        tree = ProcessTree([child.pid])
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
            tree.sample()
            if args.dashboard_reads:
                with urlopen(
                    f"http://127.0.0.1:{info['port']}/dashboard", timeout=5
                ) as response:
                    response.read()
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                time.sleep(min(1, max(0, deadline - time.monotonic())))
                tree.sample()
                if args.dashboard_reads:
                    with urlopen(
                        f"http://127.0.0.1:{info['port']}/dashboard", timeout=5
                    ) as response:
                        response.read()
            resolve.terminate()
            resolve.wait(timeout=5)
            child.wait(timeout=10)
            if child.returncode:
                raise RuntimeError(f"Benchmark exited {child.returncode}")
            result = json.loads(worker_output.read_text())
            tree.sample()
            elapsed = time.perf_counter() - started
            cpu = sum(tree.cpu_seconds.values()) / elapsed * 100
            peak_mb = tree.peak_working_set_bytes / 1024**2
            result.update(
                startup_seconds=round(startup, 3),
                cpu_percent_one_core=round(cpu, 3),
                peak_sampled_working_set_mb=round(peak_mb, 2),
                cpu_under_1_percent=cpu < 1,
                working_set_under_150_mb=peak_mb < 150,
                application_process_count=tree.peak_processes,
                renderer_count=tree.peak_renderers
                if tree.renderer_commands_available
                else None,
                application_processes_after_exit=tree.live_process_count,
                process_samples=tree.samples,
                dashboard_workload="HTTP reads only, no renderer"
                if args.dashboard_reads
                else "none",
            )
            result["measurement_sources"].update(
                application_process_count="OS process snapshots: peak managed worker and observed descendants; excludes benchmark sampler and Resolve stand-in",
                renderer_count="OS command lines containing --type=renderer; null if unavailable",
                cpu_percent_one_core="sum of sampled cumulative CPU times for observed application processes divided by wall time",
                peak_sampled_working_set_mb="peak sum of OS resident bytes for observed application processes",
                application_processes_after_exit="OS snapshot of all previously observed application PIDs after runtime shutdown",
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
