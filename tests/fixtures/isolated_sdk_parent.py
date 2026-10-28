"""Disposable parent for abrupt-exit ownership acceptance checks."""

import json
import sys
import time
from pathlib import Path

from resolve_time_tracker.activity_tracker import AlwaysActiveProbe
from resolve_time_tracker.isolated_resolve_bridge import IsolatedResolveBridge


def main():
    module, report = map(Path, sys.argv[1:])
    bridge = IsolatedResolveBridge(module, AlwaysActiveProbe(), timeout_seconds=1)
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                bridge.snapshot()
                break
            except TimeoutError:
                assert time.monotonic() < deadline
                time.sleep(0.05)
        (module.parent / "block").write_text("30000")
        try:
            bridge.snapshot()
        except TimeoutError:
            pass
        pending = report.with_suffix(".tmp")
        pending.write_text(json.dumps(bridge.diagnostics()))
        pending.replace(report)
        time.sleep(60)
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
