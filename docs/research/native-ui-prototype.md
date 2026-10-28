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

## Dedicated Scripts-menu experiment

The existing menu installer has an opt-in probe mode. From the checkout under
test, run:

```text
uv run --python 3.13 scripts/install_resolve_menu.py --native-probe
```

This creates only `ResolveTimeTrackerNativeProbe.py` in the documented per-user
Utility folder. It does not replace either production menu entry or start the
tracker. Restart Resolve after saving existing work, open the disposable project,
then choose **Workspace > Scripts > ResolveTimeTrackerNativeProbe**. The entry
executes the probe using the menu's own `resolve`, `fusion` and `bmd` objects;
it does not create an external scripting connection.

The entry adds `menu_invocation_returned: true` to the probe's temporary report
only after the entire `runpy` invocation returns. A report ending at
`after_run_loop` without that marker is not proof of full menu return. A second
activation that only focuses an existing window creates no report of its own.

To remove this checkout's temporary menu entry after the experiment:

```text
uv run --python 3.13 scripts/install_resolve_menu.py --remove-native-probe
```

Both modes accept `--utility-dir` for isolated test locations. Installation and
removal refuse a file with different contents, and cleanup removes only the
matching generated probe entry. Remove it before deleting/moving the checkout.

The callback probe now explicitly enables `ProbeEvent` in the window's `Events`
attribute. The first-party Workflow Integrations README, lines 340–344, states
that event handlers can be enabled/disabled there and only common events such as
Clicked/Close are enabled by default. A boundary test models that filtering and
reproduces zero callback delivery without the declaration. This is a documented
API configuration correction, not yet proof of real host delivery.

Context7's Fusion Script Docs reference describes `UITimer.Start`, `Stop` and
`Interval`, but the fetched material does not establish how to create/register
one in this host or a supported timeout-handler API. The menu experiment does
not claim a periodic scheduler or guess those calls.

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

## Initial Windows host attempt

The parent agent launched the probe from the Python console of Resolve on Windows
11 build 26200, with a saved disposable project. The initial temporary JSON
reported PID 32324, matching the independently observed Resolve PID, Python
3.13.14, and successful SQLite/ctypes checks. This is direct evidence for that
console context. It does not establish the Scripts-menu interpreter or justify
changing the project's supported Python versions. The separate bundled Python
3.14 executable is a different runtime.

The initial top-level window inventory did not list a native probe window. That
inventory was insufficient: the later attempt established that this UIManager
window is a child of Resolve's main window. The first result is therefore
inconclusive, not proof that dispatcher creation failed. The initial report was
written before dispatcher construction and recorded no callback or read result.
Normal shutdown did not end the first attempt; the parent subsequently terminated
the disposable Resolve process. This does not establish clean host shutdown.

The probe now writes before/after phase markers around dispatcher creation,
layout construction, AddWindow, handler setup, Show and RunLoop. Each write is
closed before calling the SDK. An exception records its phase and exception type
without private error text and is re-raised. A hanging call leaves the last
`before_*` marker available for inspection. The parent controls stopping the old
attempt and any retry; no retry should run alongside a possibly active dispatcher.

On the instrumented retry the parent found a visible native child window owned by
Resolve, PID 34384, with Python 3.13.14 and a report at `before_run_loop`. That is
the expected phase while the event loop is active. The layout call matches the
shipped sample's `AddWindow(properties, ui.VGroup([children]))` shape and the retry
now establishes visible console-context window creation. Menu launch, independent
controller lifetime, periodic scheduling and real tracking remain unverified.

Clicking the initial Dispatch implementation left the displayed result at 0/10.
The cause is not yet established. Its old implementation interpreted a missing
custom event timestamp as another initial button press; a host that drops custom
payload fields could therefore requeue indefinitely. A regression test reproduced
that case. Start-button handling and queued callbacks are now separate, with the
timestamp and bounded counter retained in Python state instead of trusting event
payloads. JSON records enqueued and delivered counts separately. The fake-host
regression is not proof of actual custom-event delivery, and a live retry of the
bounded-callback fix has not been completed.

The parent also observed the original probe's explicit read succeeding while
idle: a project was open, Page was `cut`, rendering was false and the getter
sequence took approximately 0.00269 seconds. Stop recorded `stopped: true` and
`after_run_loop`, and the child window hid. However, the console input remained
disabled and did not accept a subsequent command minutes later. This establishes
event-loop exit, not successful return from the full console invocation. The
current phase markers do not distinguish a blocked final Hide from object
cleanup/destruction or other host-console behavior. No repeat invocation or
stale-window experiment could be completed in that console.

A subsequent normal application-close request eventually ended the second test
instance; no Resolve process remained at the final cleanup check. The first
attempt had been terminated after a normal exit request did not complete while
its probe was active. No existing project was opened or edited. The saved empty
`TimeTracker Spec Probe 20261027` project remains available for later checks.

The console route is therefore not yet suitable for a production tracking
controller. Keep #57 open for a safe Scripts-menu or lightweight-worker
experiment, preserving the working sidecar/dashboard. Do not infer that menu
execution will behave the same as the console, or force tracker work into the
host process to reduce process count. The bounded callback correction is tested
against the SDK boundary only and still needs a fresh live host trial.

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
