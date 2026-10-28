import os
import subprocess
import threading
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import Mock, patch

from resolve_time_tracker.activity_tracker import (
    ActivityState,
    CachedActivityProbe,
    LinuxActivityProbe,
    MacActivityProbe,
    WindowsActivityProbe,
    _run_text,
    default_activity_probe,
)


class ActivityProbeTest(unittest.TestCase):
    def test_failed_thread_start_can_retry_or_close(self):
        for retry in (False, True):
            with self.subTest(retry=retry):
                sampled = threading.Event()

                class Probe:
                    def sample(self):
                        sampled.set()
                        return ActivityState(0, True)

                probe = CachedActivityProbe(Probe())
                try:
                    with patch.object(
                        threading.Thread,
                        "start",
                        side_effect=RuntimeError("unavailable"),
                    ):
                        with self.assertRaisesRegex(RuntimeError, "unavailable"):
                            probe.set_resolve_present(True)
                    if retry:
                        probe.set_resolve_present(True)
                        self.assertTrue(sampled.wait(2))
                finally:
                    probe.close()

    def test_background_sampling_presence_cadence_and_shutdown(self):
        now = [0.0]
        calls = []

        class Probe:
            def sample(self):
                calls.append(threading.get_ident())
                return ActivityState(2.5, True)

        probe = CachedActivityProbe(Probe(), clock=lambda: now[0])
        try:
            self.assertIsNone(probe.idle_seconds())
            self.assertEqual([], calls)
            probe.set_resolve_present(True)
            with probe._condition:
                self.assertTrue(
                    probe._condition.wait_for(
                        lambda: probe.snapshot().unavailable_reason is None, timeout=2
                    )
                )
            state = probe.snapshot()
            with self.assertRaises(FrozenInstanceError):
                state.idle_seconds = 9
            for _ in range(100):
                self.assertEqual(2.5, probe.idle_seconds())
                self.assertTrue(probe.resolve_is_foreground())
            self.assertEqual(1, len(calls))
            self.assertNotEqual(threading.get_ident(), calls[0])
            probe.set_resolve_present(False)
            now[0] = 15
            self.assertIsNone(probe.snapshot().idle_seconds)
            self.assertEqual(1, len(calls))
            probe.set_resolve_present(True)
            with probe._condition:
                self.assertTrue(
                    probe._condition.wait_for(lambda: len(calls) == 2, timeout=2)
                )
        finally:
            probe.close()
        self.assertFalse(probe._thread.is_alive())

    def test_disable_discards_inflight_sample_and_close_joins(self):
        started = threading.Event()
        release = threading.Event()

        class Probe:
            def sample(self):
                started.set()
                release.wait(2)
                return ActivityState(0, True)

        probe = CachedActivityProbe(Probe())
        try:
            probe.set_resolve_present(True)
            self.assertTrue(started.wait(2))
            probe.set_resolve_present(False)
            self.assertIsNone(probe.idle_seconds())
        finally:
            release.set()
            probe.close()
        self.assertIsNone(probe.idle_seconds())
        self.assertFalse(probe._thread.is_alive())

    def test_background_error_is_unavailable(self):
        class Probe:
            def sample(self):
                raise OSError("permission denied")

        probe = CachedActivityProbe(Probe())
        try:
            probe.set_resolve_present(True)
            with probe._condition:
                self.assertTrue(
                    probe._condition.wait_for(
                        lambda: probe.unavailable_reason == "activity probe failed",
                        timeout=2,
                    )
                )
            self.assertIsNone(probe.resolve_is_foreground())
        finally:
            probe.close()

    def test_malformed_or_failed_platform_reads_are_unavailable(self):
        for output in (None, "", "garbage", "-1"):
            with self.subTest(output=output):
                linux = LinuxActivityProbe(run_text=lambda _command: output)
                mac = MacActivityProbe(run_text=lambda _command: output)
                self.assertIsNotNone(linux.sample().unavailable_reason)
                self.assertIsNotNone(mac.sample().unavailable_reason)

    def test_platform_command_failures_are_unavailable_and_bounded(self):
        failures = (
            FileNotFoundError("missing utility"),
            PermissionError("denied"),
            subprocess.CalledProcessError(1, ["probe"]),
            subprocess.TimeoutExpired(["probe"], 2),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with patch(
                    "resolve_time_tracker.activity_tracker.subprocess.check_output",
                    side_effect=failure,
                ) as command:
                    self.assertIsNone(_run_text(["probe"]))
                self.assertEqual(2, command.call_args.kwargs["timeout"])

    def test_missing_tools_display_and_wayland_are_unavailable(self):
        cases = (
            ("Darwin", {}, "macOS activity utilities are unavailable"),
            ("Linux", {}, "X11 activity detection is unavailable"),
            ("Linux", {"DISPLAY": ":0"}, "X11 activity detection is unavailable"),
            (
                "Linux",
                {"DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"},
                "Wayland activity detection is unsupported",
            ),
        )
        for system, environment, reason in cases:
            with (
                self.subTest(system=system, environment=environment),
                patch("resolve_time_tracker.activity_tracker.os.name", "posix"),
                patch(
                    "resolve_time_tracker.activity_tracker.platform.system",
                    return_value=system,
                ),
                patch.dict(os.environ, environment, clear=True),
                patch(
                    "resolve_time_tracker.activity_tracker._command_path",
                    return_value=None,
                ),
                patch(
                    "resolve_time_tracker.activity_tracker.shutil.which",
                    return_value=None,
                ),
            ):
                probe = default_activity_probe()
                self.assertEqual(reason, probe.unavailable_reason)
                self.assertIsNone(probe.idle_seconds())
                self.assertIsNone(probe.resolve_is_foreground())

    def test_platform_commands_only_run_on_the_background_sampling_cadence(self):
        for platform_probe, idle_output in (
            (MacActivityProbe, '"HIDIdleTime" = 2500000000'),
            (LinuxActivityProbe, "2500"),
        ):
            with self.subTest(platform=platform_probe.__name__):
                now, calls = [0.0], []

                def run_text(command):
                    calls.append(threading.get_ident())
                    return idle_output if len(calls) % 2 else "DaVinci Resolve"

                probe = CachedActivityProbe(
                    platform_probe(run_text=run_text),
                    interval_seconds=1,
                    clock=lambda: now[0],
                )
                try:
                    self.assertEqual([], calls)
                    probe.set_resolve_present(True)
                    with probe._condition:
                        self.assertTrue(
                            probe._condition.wait_for(
                                lambda: probe.snapshot().unavailable_reason is None,
                                timeout=2,
                            )
                        )
                    for _ in range(100):
                        self.assertEqual(2.5, probe.idle_seconds())
                        self.assertTrue(probe.resolve_is_foreground())
                    self.assertEqual(2, len(calls))
                    self.assertNotIn(threading.get_ident(), calls)
                    with probe._condition:
                        now[0] = 14
                        probe._condition.notify_all()
                        self.assertFalse(
                            probe._condition.wait_for(
                                lambda: len(calls) > 2, timeout=0.1
                            )
                        )
                        now[0] = 15
                        probe._condition.notify_all()
                        self.assertTrue(
                            probe._condition.wait_for(
                                lambda: len(calls) == 4, timeout=2
                            )
                        )
                    probe.set_resolve_present(False)
                    self.assertIsNone(probe.idle_seconds())
                finally:
                    probe.close()
                assert probe._thread is not None
                self.assertFalse(probe._thread.is_alive())

    @unittest.skipUnless(os.name == "nt", "requires native Win32 activity APIs")
    def test_windows_native_activity_and_failure_states(self):
        probe = WindowsActivityProbe()
        state = probe.snapshot()
        self.assertIsNone(state.unavailable_reason)
        assert state.idle_seconds is not None
        self.assertGreaterEqual(state.idle_seconds, 0)
        self.assertIsInstance(state.resolve_is_foreground, bool)
        for result in (None, OSError("unavailable")):
            with self.subTest(result=result):
                replacement = (
                    Mock(side_effect=result)
                    if isinstance(result, OSError)
                    else Mock(return_value=result)
                )
                with patch.object(probe, "idle_seconds", replacement):
                    state = probe.snapshot()
                self.assertIsNotNone(state.unavailable_reason)
                self.assertIsNone(state.resolve_is_foreground)
