"""One database owner, alive only for Resolve or a user-opened dashboard."""

from __future__ import annotations

import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

from resolve_time_tracker.api import create_app
from resolve_time_tracker.database import SQLiteStore
from resolve_time_tracker.tracked_launch import (
    LaunchError,
    ProcessWatch,
    _runtime_lock,
    start_resolve,
)
from resolve_time_tracker.tracking_engine import TrackingEngine
from resolve_time_tracker.tracking_runtime import TrackingRuntime


class DashboardOwner(BaseModel):
    pid: int = Field(gt=0)


class RuntimeHost:
    def __init__(self, api, *, alive=None, launch=start_resolve, bridge_factory=None):
        self.api = api
        self._alive_override = alive
        self._processes: dict[int, ProcessWatch] = {}
        self.launch = launch
        self.bridge_factory = bridge_factory
        self.resolve_pid = None
        self.dashboards: set[int] = set()
        self.bridge = None
        self.lock = threading.RLock()
        self.closing = False

    def alive(self, pid):
        if self._alive_override is not None:
            return self._alive_override(pid)
        if pid not in self._processes:
            self._processes[pid] = ProcessWatch(pid)
        return self._processes[pid].alive()

    def _release_process(self, pid):
        watch = self._processes.pop(pid, None)
        if watch is not None:
            watch.close()

    def track(self):
        with self.lock:
            if self.closing:
                raise LaunchError("Tracker is closing. Launch again.")
            if self.resolve_pid is not None and self.alive(self.resolve_pid):
                return
            self.stop_tracking()
            with self.api.lock:
                pid = self.launch(self.api.store)
                if not self.alive(pid):
                    self._release_process(pid)
                    raise LaunchError("DaVinci Resolve closed before tracking started.")
                self.resolve_pid = pid
                try:
                    if self.bridge_factory is None:
                        from resolve_time_tracker.resolve_bridge import ResolveBridge

                        self.bridge_factory = ResolveBridge
                    self.bridge = self.bridge_factory()
                    engine = TrackingEngine(
                        self.api.store, snapshot_provider=self.bridge
                    )
                    runtime = TrackingRuntime(engine, lock=self.api.lock)
                    self.api.tracking_engine = engine
                    self.api.tracking_runtime = runtime
                    self.api.read_only = False
                    runtime.start()
                except Exception as exc:
                    self.stop_tracking()
                    raise LaunchError(
                        f"Could not start tracking: {exc}. Run Tracked Launch again."
                    ) from exc

    def attach(self, pid):
        with self.lock:
            if self.closing or not self.alive(pid):
                self._release_process(pid)
                raise LaunchError("Dashboard has already closed. Open it again.")
            self.dashboards.add(pid)

    def detach(self, pid):
        with self.lock:
            self.dashboards.discard(pid)
            self._release_process(pid)

    def stop_tracking(self):
        runtime = self.api.tracking_runtime
        if runtime is not None:
            runtime.stop()
        if self.bridge is not None:
            close = getattr(self.bridge, "close", None)
            if close:
                close()
        with self.api.lock:
            # An exit cannot provide a trustworthy final observation.
            self.api.store.recover_active_session()
            self.api.tracking_runtime = None
            self.api.tracking_engine = None
            self.api.read_only = True
            self._release_process(self.resolve_pid)
            self.resolve_pid = None
            self.bridge = None

    def tick(self):
        with self.lock:
            if self.resolve_pid is not None and not self.alive(self.resolve_pid):
                self.stop_tracking()
            for pid in self.dashboards.copy():
                if not self.alive(pid):
                    self.detach(pid)
            self.closing = self.resolve_pid is None and not self.dashboards
            return self.closing


def runtime_request(db_path: Path, route: str, payload=None, *, timeout=120):
    info = json.loads(db_path.with_suffix(".runtime.json").read_text(encoding="utf-8"))
    port = int(info["port"])
    if not 0 < port < 65536:
        raise LaunchError("Invalid runtime port")
    request = Request(
        f"http://127.0.0.1:{port}{route}",
        data=json.dumps(payload or {}).encode(),
        headers={"Content-Type": "application/json", "X-Runtime-Token": info["token"]},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def run_managed(db_path: Path, *, tracked=False, dashboard_pid=None, port=0):
    import uvicorn

    db_path = Path(db_path).resolve()
    route = "/runtime/track" if tracked else "/runtime/attach"
    if not tracked and dashboard_pid is None:
        raise LaunchError("Open the dashboard or use the Tracked Launch shortcut.")
    # A simultaneous launch may be publishing its endpoint. Retry only during launch.
    for attempt in range(100):
        with _runtime_lock(db_path) as owned:
            if not owned:
                try:
                    runtime_request(db_path, route, {"pid": dashboard_pid})
                    return
                except HTTPError as exc:
                    try:
                        detail = json.load(exc).get(
                            "detail", "Existing runtime rejected the launch"
                        )
                    except ValueError:
                        detail = "Existing runtime rejected the launch"
                    raise LaunchError(str(detail)) from exc
                except (OSError, ValueError, KeyError):
                    if attempt == 99:
                        raise LaunchError(
                            "Existing tracker did not respond. Close it and launch again."
                        )
                    time.sleep(0.1)
                    continue
            _serve(
                db_path,
                tracked=tracked,
                dashboard_pid=dashboard_pid,
                port=port,
                uvicorn=uvicorn,
            )
            return


def _serve(db_path, *, tracked, dashboard_pid, port, uvicorn):
    info_path = db_path.with_suffix(".runtime.json")
    stopped = threading.Event()
    monitor = None
    token = secrets.token_urlsafe(32)
    with (
        SQLiteStore(db_path, check_same_thread=False) as store,
        socket.socket() as listener,
    ):
        store.recover_active_session()
        app = create_app(store)
        app.state.api.read_only = True
        owner = RuntimeHost(app.state.api)
        app.state.owner = owner

        def authorize(value):
            if not secrets.compare_digest(value or "", token):
                raise HTTPException(403, "Invalid runtime token")

        @app.post("/runtime/track")
        def track(x_runtime_token: str = Header(default="")):
            authorize(x_runtime_token)
            try:
                owner.track()
            except LaunchError as exc:
                raise HTTPException(409, str(exc)) from exc
            return {"ok": True}

        @app.post("/runtime/attach")
        def attach(body: DashboardOwner, x_runtime_token: str = Header(default="")):
            authorize(x_runtime_token)
            try:
                owner.attach(body.pid)
            except LaunchError as exc:
                raise HTTPException(409, str(exc)) from exc
            return {"ok": True}

        @app.post("/runtime/detach")
        def detach(body: DashboardOwner, x_runtime_token: str = Header(default="")):
            authorize(x_runtime_token)
            owner.detach(body.pid)
            return {"ok": True}

        try:
            if tracked:
                owner.track()
            if dashboard_pid is not None:
                owner.attach(dashboard_pid)
            listener.bind(("127.0.0.1", port))
            server = uvicorn.Server(
                uvicorn.Config(
                    app,
                    log_level="warning",
                    access_log=False,
                    timeout_graceful_shutdown=2,
                )
            )
            info = {
                "port": listener.getsockname()[1],
                "pid": os.getpid(),
                "token": token,
            }
            info_path.write_text(json.dumps(info), encoding="utf-8")
            if os.name != "nt":
                info_path.chmod(0o600)

            def watch_lifetime():
                while not stopped.wait(0.5):
                    if owner.tick():
                        server.should_exit = True
                        return

            monitor = threading.Thread(target=watch_lifetime, daemon=True)
            monitor.start()
            server.run(sockets=[listener])
        finally:
            stopped.set()
            if monitor:
                monitor.join()
            owner.stop_tracking()
            for pid in owner.dashboards.copy():
                owner.detach(pid)
            info_path.unlink(missing_ok=True)
