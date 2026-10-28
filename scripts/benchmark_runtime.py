"""Temporary-data runtime benchmark; optionally attach to an already-running Resolve."""

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


class SdkCalls:
    """Benchmark-only SDK boundary accounting; never retains arguments or results."""

    def __init__(self):
        self.lock = threading.Lock()
        self.methods = {}
        self.inflight = 0

    def wrap(self, value):
        if value is None or isinstance(value, (str, bytes, bool, int, float)):
            return value
        if isinstance(value, (list, tuple)):
            return type(value)(self.wrap(item) for item in value)
        if isinstance(value, dict):
            return {key: self.wrap(item) for key, item in value.items()}
        counter = self

        class MeasuredObject:
            def __getattr__(self, name):
                member = getattr(value, name)
                if not callable(member):
                    return counter.wrap(member)

                def call(*args, **kwargs):
                    started = time.perf_counter()
                    failed = False
                    with counter.lock:
                        counter.inflight += 1
                    try:
                        return counter.wrap(member(*args, **kwargs))
                    except BaseException:
                        failed = True
                        raise
                    finally:
                        with counter.lock:
                            counter.inflight -= 1
                            metric = counter.methods.setdefault(
                                name, {"calls": 0, "failures": 0, "seconds": 0.0}
                            )
                            metric["calls"] += 1
                            metric["failures"] += int(failed)
                            metric["seconds"] += time.perf_counter() - started

                return call

        return MeasuredObject()

    def report(self):
        with self.lock:
            methods = {name: values.copy() for name, values in self.methods.items()}
            return {
                "total": sum(metric["calls"] for metric in methods.values()),
                "failures": sum(metric["failures"] for metric in methods.values()),
                "seconds": sum(metric["seconds"] for metric in methods.values()),
                "inflight": self.inflight,
                "methods": methods,
            }


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
                "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,"
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
                "executable_name": row["Name"],
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
            "executable_name": Path(fields[10].split()[0]).name,
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


def worker(db, resolve_pid, output, *, live=False):
    from resolve_time_tracker import api, runtime_host
    from resolve_time_tracker.database import SQLiteStore
    from resolve_time_tracker.tracking_engine import RuntimeSnapshot

    counts = {
        "observations": 0,
        "observation_failures": 0,
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
    sdk_calls = SdkCalls()

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

    from resolve_time_tracker.resolve_bridge import ResolveBridge

    class MeasuredResolve(ResolveBridge):
        def _load_module(self):
            return sdk_calls.wrap(super()._load_module())

        def snapshot(self):
            counts["observations"] += 1
            try:
                return super().snapshot()
            except Exception:
                counts["observation_failures"] += 1
                raise

    class MeasuredApiState(api.ApiState):
        def dashboard(self):
            counts["dashboard_requests"] += 1
            query_context.dashboard = True
            try:
                return super().dashboard()
            finally:
                query_context.dashboard = False

    class BenchmarkHost(runtime_host.RuntimeHost):
        def alive(self, pid):
            if pid == resolve_pid and db.with_suffix(".stop").exists():
                return False
            return super().alive(pid)

    with (
        patch.object(api, "ApiState", MeasuredApiState),
        patch.object(runtime_host, "SQLiteStore", MeasuredStore),
        patch.object(
            runtime_host,
            "RuntimeHost",
            lambda state: BenchmarkHost(
                state,
                launch=lambda _: resolve_pid,
                bridge_factory=MeasuredResolve if live else SyntheticResolve,
            ),
        ),
    ):
        runtime_host.run_managed(db, tracked=True)
    elapsed = time.perf_counter() - started
    result = {
        "scenario": "live Resolve SDK; temporary tracking database"
        if live
        else "synthetic Active Work; one real managed runtime, no real Resolve scripting",
        "duration_seconds": round(elapsed, 2),
        "resolve_sdk_calls": sdk_calls.report()["total"] if live else None,
        "resolve_sdk_metrics": sdk_calls.report() if live else None,
        "sampling_limitations": "OS snapshots can miss short-lived children and their final CPU time; resident memory is a sampled peak. Benchmark monitoring overhead is excluded from the application tree.",
        "measurement_sources": {
            "resolve_sdk_calls": "actual SDK method boundary calls; no arguments/results retained"
            if live
            else "not measured: synthetic provider",
            "observations": "ResolveBridge snapshot invocations"
            if live
            else "synthetic snapshot provider invocations",
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
    parser.add_argument(
        "--electron",
        action="store_true",
        help="Open the built dashboard against temporary data and quit it after measurement",
    )
    parser.add_argument("--frontend", type=Path, default=ROOT / "frontend")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--resolve-pid", type=int)
    parser.add_argument(
        "--live-resolve-pid",
        type=int,
        help="Attach a running Resolve; never launch or terminate it. Uses temporary history.",
    )
    args = parser.parse_args()
    if args.worker:
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if (
            args.db is None
            or args.resolve_pid is None
            or args.db.resolve().parent.parent != temporary_root
            or not args.db.parent.name.startswith("resolve-benchmark-")
            or args.db.name != "tracker.sqlite3"
            or args.db.exists()
            or args.output.resolve().parent != args.db.resolve().parent
        ):
            parser.error(
                "Internal worker requires a fresh temporary benchmark database"
            )
        worker(
            args.db,
            args.resolve_pid,
            args.output,
            live=args.live_resolve_pid is not None,
        )
        return
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be finite and positive")
    if args.live_resolve_pid is not None:
        candidate = process_snapshot().get(args.live_resolve_pid, {})
        if candidate.get("executable_name", "").lower() not in (
            "resolve",
            "resolve.exe",
        ):
            parser.error(
                "--live-resolve-pid must identify a running Resolve executable"
            )
    electron = args.frontend / "node_modules" / "electron" / "dist"
    electron = electron / (
        "electron.exe"
        if os.name == "nt"
        else "Electron.app/Contents/MacOS/Electron"
        if sys.platform == "darwin"
        else "electron"
    )
    if args.electron:
        if (
            not electron.is_file()
            or not (args.frontend / "dist" / "index.html").is_file()
        ):
            parser.error(
                "Electron workload requires a built frontend and installed Electron"
            )
        if (args.seconds + 2) * 1000 > 2147483647:
            parser.error("--seconds exceeds Electron's timer limit")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryDirectory(prefix="resolve-benchmark-") as tmp:
        db = Path(tmp) / "tracker.sqlite3"
        worker_output = Path(tmp) / "worker.json"
        dashboard = None
        # This sleeping process stands in for Resolve; it is excluded from app metrics.
        resolve = (
            None
            if args.live_resolve_pid is not None
            else subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(86400)"],
                creationflags=flags,
            )
        )
        resolve_pid = resolve.pid if resolve is not None else args.live_resolve_pid
        started = time.perf_counter()
        child = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--db",
                str(db),
                "--resolve-pid",
                str(resolve_pid),
                "--output",
                str(worker_output),
                *(
                    ["--live-resolve-pid", str(args.live_resolve_pid)]
                    if args.live_resolve_pid is not None
                    else []
                ),
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
            if args.electron:
                environment = os.environ.copy()
                environment.pop("ELECTRON_RUN_AS_NODE", None)
                dashboard = subprocess.Popen(
                    [
                        str(electron),
                        str(args.frontend.resolve()),
                        "--db",
                        str(db),
                        "--python",
                        sys.executable,
                        "--benchmark-seconds",
                        str(args.seconds + 2),
                    ],
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
                tree.roots.add(dashboard.pid)
            tree.sample()
            if args.dashboard_reads:
                with urlopen(
                    f"http://127.0.0.1:{info['port']}/dashboard", timeout=5
                ) as response:
                    response.read()
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                if dashboard is not None and dashboard.poll() is not None:
                    raise RuntimeError(
                        "Benchmark dashboard exited before measurement completed"
                    )
                time.sleep(min(1, max(0, deadline - time.monotonic())))
                tree.sample()
                if args.dashboard_reads:
                    with urlopen(
                        f"http://127.0.0.1:{info['port']}/dashboard", timeout=5
                    ) as response:
                        response.read()
            if dashboard is not None:
                dashboard.wait(timeout=15)
                if dashboard.returncode:
                    raise RuntimeError(
                        f"Benchmark dashboard exited {dashboard.returncode}"
                    )
            db.with_suffix(".stop").touch()
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
                dashboard_workload="real Electron dashboard against temporary tracking data"
                if args.electron
                else "HTTP reads only, no renderer"
                if args.dashboard_reads
                else "none",
            )
            result["measurement_sources"].update(
                application_process_count="OS process snapshots: peak managed worker, requested Electron and observed descendants; excludes sampler and actual/simulated Resolve",
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
            db.with_suffix(".stop").touch()
            for process in (dashboard, child, resolve):
                if process is None:
                    continue
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
