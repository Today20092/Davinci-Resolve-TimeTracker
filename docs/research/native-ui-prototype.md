# Native UIManager feasibility prototype

This opt-in experiment implements the first host/window/event-dispatch checks for
[#57](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/57). The
current scope permits a lightweight worker, keeps independent on-demand Electron
reporting, and measures editing impact. A zero-process requirement from earlier
research is superseded.

## What the prototype does

`scripts/native_ui_probe.py` uses only Python standard-library modules and the
Resolve-provided `resolve`, `fusion` and `bmd` objects. It does not import the
tracker package, start Electron/HTTP/a worker, install anything, or connect to the
production database. Capability checks use an in-memory SQLite database; JSON
evidence goes to a new `resolve-native-probe-*` directory in the OS temporary
directory. The window displays the report path.

- Reports script PID/parent PID, interpreter/platform, and SQLite/ctypes
  availability in the actual script context.
- Uses a stable window ID. A second invocation shows/raises an existing window
  before creating a dispatcher or writing another report.
- Close and Hide call `Hide`, leaving the event loop active. Stop probe calls
  `ExitLoop`, including when evidence can no longer be written.
- An explicit button queues ten bounded no-op callbacks and records callback
  latency. These callbacks are **not a periodic scheduler**. No UI calls are made
  from a background Python thread and no timer API is guessed.
- Another explicit button reads project/Page/rendering state once. It displays the
  project name locally but omits it from the JSON report. Read failures are
  explicit; no observation creates a billable Session.

This is not yet the native tracking interface. Pause/resume, history and CSV remain
in the existing application. Safe periodic scheduling and real tracking
integration require a separate successful host/lifetime test.

## Safe launch

Save existing work first and use a disposable project. Close any other instance of
this probe. Do not run the first-party sample's project-creation button. Running
the probe from a shell intentionally fails with a context error; it never starts
or externally connects to Resolve.

For an initial **console-context** check, open Resolve's Python console. Confirm
the host supplies `resolve`, `fusion` and `bmd`; do not substitute a new external
scripting connection. Then run this, adapting the checkout path:

```python
import runpy
_ = runpy.run_path(
    r"C:\path\to\checkout\scripts\native_ui_probe.py",
    init_globals={"resolve": resolve, "fusion": fusion, "bmd": bmd},
    run_name="__main__",
)
```

Some host contexts name the Fusion object `fu`; use that existing object as the
`fusion` value if appropriate. The console is occupied until Stop probe returns
from `RunLoop`. This launch does **not** prove Scripts-menu execution or that the
menu invocation returns while the controller survives.

To test actual menu execution, place a copy of this self-contained file under a
new, clearly named temporary Utility entry, following the installed SDK's script
locations. Do not overwrite `ResolveTimeTrackerMenu.py` or change the production
installer. Refresh/restart Resolve only after saving the disposable project. The
temporary entry must execute this script directly with the host globals, not
spawn the existing companion launcher. Remove only that temporary entry after
the experiment.

## Live evidence checklist

- [ ] Record Windows build, Resolve edition/version, repository commit, shipped
  SDK revision, probe PID/parent and the application process tree. Compare script
  PID with Resolve PID instead of inferring hosting from a native-looking window.
- [ ] Show the window from the Scripts menu. Repeat activation; confirm there is
  one window and one event loop.
- [ ] Run ten callbacks, verify the count/latencies in JSON, and repeat during
  playback and a short render while watching Resolve responsiveness. No-op
  dispatch responsiveness alone does not establish safe periodic SDK calls.
- [ ] While Resolve is idle, request one read. Verify project/Page/render state.
  The SDK call itself has no proven host-side timeout, so do not intentionally
  call it during a known blocking operation.
- [ ] Close/Hide, reactivate from the menu, and verify the original PID/report and
  window identity. Confirm Stop returns from the event loop. Check whether a
  stopped window remains registered and record that behavior before permitting
  production reuse. Fake-host tests do not establish Qt object lifetime.
- [ ] Close Resolve and inspect for leftover script/worker processes. Do not
  crash an unsaved project or terminate a production tracking runtime.
- [ ] Confirm the existing independently launched reporting dashboard still works
  and is absent when not requested, using #52's lifecycle checks.
- [ ] Establish an actually supported periodic scheduler, or recommend a measured
  existing-worker adaptation. Do not report the queued-event test as that proof.

No live check is marked passed by this document. The automated test is against a
fake SDK/GUI boundary; it verifies our handler behavior, report/privacy rules,
bounded callback count, reuse and stop cleanup, not the native host.

## Automated checks

```text
uv run --python 3.13 -m pytest -q tests/test_native_ui_probe.py
uv run --python 3.13 ruff format --check scripts/native_ui_probe.py tests/test_native_ui_probe.py
uv run --python 3.13 ruff check scripts/native_ui_probe.py tests/test_native_ui_probe.py
uvx ty check scripts/native_ui_probe.py --python .venv/Scripts/python.exe
```

The first capability, lifecycle, callback and read tests were observed failing
before their implementation and passing afterward. No dependency or supported
Python-version declaration changed. The standalone prototype can be evaluated
under Resolve's interpreter without installing this Python package.

## Primary sources

- Installed `Support/Developer/Workflow Integrations/README.txt`, especially
  UIManager Introduction, UIDispatcher Functions and common element functions:
  `AddWindow`, `RunLoop`, `ExitLoop`, `FindWindow`, `QueueEvent`, `Show`, `Hide`,
  `Raise` and event handlers.
- Installed `Workflow Integrations/Examples/Sample Script Plugin.py`: stable ID,
  existing-window check, UIManager property, event assignment and dispatcher
  loop. Its close handler exits, so hiding instead is an experiment to verify.
- Installed `Support/Developer/Scripting/README.md`: supplied host objects,
  project/Page/render getters, script locations and bundled interpreters.

The inspected introductory UIManager reference is non-exhaustive and establishes
no timer or thread-safety guarantee. Context7 was also queried for the Resolve
scripting API; its results did not provide useful scheduler documentation. The
implementation relies on the installed first-party examples, not that negative
search result or an undocumented method.
