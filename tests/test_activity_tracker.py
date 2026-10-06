import threading
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from resolve_time_tracker.activity_tracker import (
    ActivityState,
    CachedActivityProbe,
    LinuxActivityProbe,
    MacActivityProbe,
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
