"""Own the background Tracking Observation cadence and published runtime state."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from resolve_time_tracker.tracking_engine import RuntimeSnapshot, TrackingEngine


Now = Callable[[], datetime]


class TrackingRuntime:
    def __init__(
        self,
        engine: TrackingEngine,
        *,
        now: Now | None = None,
        observation_interval_seconds: float = 5,
        lock: Any = None,
    ):
        self.engine = engine
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._observation_interval_seconds = observation_interval_seconds
        self._lock = lock or threading.RLock()
        self._observation_lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot = engine.previous_snapshot
        self._last_error: str | None = None
        self._observation_count = 0
        self._failure_count = 0

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def snapshot(self) -> RuntimeSnapshot | None:
        with self._lock:
            return self._snapshot

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    @property
    def observation_count(self) -> int:
        with self._lock:
            return self._observation_count

    def observe(self, observed_at: datetime | None = None) -> bool:
        """Take one complete observation; failed snapshots leave Session state alone."""
        with self._observation_lock:
            try:
                # Resolve scripting may block. Never hold the database lock across it.
                enabled = self.engine.tracking_enabled
                snapshot = (
                    self.engine.read_snapshot()
                    if enabled
                    else RuntimeSnapshot(None, None, False, None, False)
                )
                with self._lock:
                    if self._stopped.is_set():
                        return False
                    if not enabled and self.engine.tracking_enabled:
                        return True
                    self._snapshot = self.engine.poll(
                        observed_at or self._now(), snapshot
                    )
                    self._last_error = None
                    self._failure_count = 0
                    self._observation_count += 1
                return True
            except Exception as exc:
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    self._failure_count += 1
                return False

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stopped.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            # ponytail: a stuck SDK call can retain one daemon thread; isolate SDK if hangs persist.
            thread.join(timeout=1)

    def pause(self, observed_at: datetime | None = None) -> None:
        with self._lock:
            self.engine.pause(observed_at or self._now())

    def resume(self) -> None:
        with self._lock:
            self.engine.resume()

    def _run(self) -> None:
        while not self._stopped.is_set():
            succeeded = self.observe()
            delay = (
                self._observation_interval_seconds
                if succeeded
                else min(30, 5 * (2 ** min(3, self._failure_count - 1)))
            )
            self._stopped.wait(delay)
