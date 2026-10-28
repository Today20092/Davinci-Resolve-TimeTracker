# Native UIManager feasibility prototype

This opt-in experiment implements the first host/window/event-dispatch checks for
[#57](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/57). The
current scope permits a lightweight worker, keeps independent on-demand Electron
reporting, and measures editing impact. A zero-process requirement from earlier
research is superseded.

## What the prototype does

`scripts/native_ui_probe.py` uses only Python standard-library modules and the
Resolve-provided `resolve`, `fusion` and `bmd` objects. It does not import the
tracker package, start Electron/HTTP, install anything, or connect to the
production database. Capability checks use an in-memory SQLite database; JSON
evidence goes to a new `resolve-native-probe-*` directory in the OS temporary
directory. The window displays the report path. Resolve itself runs the dedicated
Scripts-menu invocation in a bundled `fuscript.exe` worker; the probe does not
spawn that worker.

- Reports script PID/parent PID, interpreter/platform, and SQLite/ctypes
  availability in the actual script context.
- Uses a stable window ID. A second invocation shows/raises an existing window
  before creating a dispatcher or writing another controller report. Each menu
  invocation writes a separate bootstrap report so pre-window waits are visible.
- Close and Hide call `Hide`, leaving the event loop active. Stop probe calls
  `ExitLoop`, including when evidence can no longer be written.
- An explicit button queues ten bounded no-op callbacks and records callback
  latency. These callbacks are **not a periodic scheduler**. No UI calls are made
  from a background Python thread and no timer API is guessed.
- An explicit button reads project/Page/rendering state once. The opt-in menu
  worker also performs that read on each of its three bounded periodic ticks. It displays the
  project name locally but omits it from the JSON report. Read failures are
  explicit; no observation creates a billable Session.

This is not yet the native tracking interface. Pause/resume, history and CSV remain
in the existing application. Bounded no-op scheduling is proven in the menu
worker; periodic SDK reads during real editing and production tracking integration
still require their own successful tests.

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

Use the dedicated opt-in installer below for actual menu execution. The console
launch above records the historical in-process comparison and is not the chosen
route for the bounded worker experiment.

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

The entry opts into the bounded separate-worker experiment described below. It
adds `menu_invocation_returned: true` to the probe's temporary report
only after the entire `runpy` invocation returns. A report ending at
`after_run_loop` without that marker is not proof of full menu return. A second
activation reuses the controller report but records its own bootstrap evidence.

### Bootstrap evidence for delayed playback launch

The generated entry now writes `bootstrap.json` into its temporary probe directory
before `runpy` or any host-object lookup. The probe uses the same directory for
`probe.json`. Bootstrap evidence records process identity, interpreter, wall-clock
entry time, and monotonic phase durations. It distinguishes `before_host_context`,
`before_ui_manager`, `before_find_window`, and dispatcher/layout/show/loop phases.
An exception records only its type and last phase, never its private message.

While reproducing a delayed launch, inspect the newest `resolve-native-probe-*`
directory and its bootstrap phase **before** stopping playback. A running menu
worker with no new bootstrap file means the delay precedes the instrumented Python
entry (or standard-library imports/temp-file creation); do not attribute it to a
particular SDK getter. A file stuck at a `before_*` phase narrows the wait to that
stage. A blocked OS write can also delay evidence, so absence alone is not proof
that Python never ran. The `menu_returned` phase establishes wrapper return.

This instrumentation is opt-in diagnostic evidence, not a playback fix. The
generated-wrapper test observes the first marker at the actual fake SDK boundary,
then verifies sanitized failure and shared-directory report handoff. The live
playback reproduction remains owned by the parent test session. Remove the old
generated probe entry using its original checkout before installing this changed
wrapper; ownership checks intentionally refuse to overwrite different contents.

To remove this checkout's temporary menu entry after the experiment:

```text
uv run --python 3.13 scripts/install_resolve_menu.py --remove-native-probe
```

Both modes accept `--utility-dir` for isolated test locations. Installation and
removal refuse a file with different contents, and cleanup removes only the
matching generated probe entry. Remove it before deleting/moving the checkout.

The first menu trial explicitly enabled `ProbeEvent` in the window's `Events`
attribute, but still delivered zero callbacks after one queued event. Enabling an
arbitrary event name did not establish a native event signal. The probe now queues
the documented default `Clicked` signal of a dedicated hidden Button, separate
from the start button. A boundary test that drops arbitrary event names failed
before that change and passes afterward. The ten-callback bound and timing state
remain independent of event payloads. The subsequent live menu trial delivered
all ten callbacks, as recorded below. That delivery alone does not establish a
periodic timer.

Context7's Fusion Script Docs reference describes `UITimer.Start`, `Stop` and
`Interval`, but the fetched material does not establish how to create/register
one in this host or a supported timeout-handler API. Those timer calls remain
unverified; the worker experiment below uses the actually exported StepLoop API
instead.

### First dedicated-menu observations

The parent observed the native window launched through the dedicated menu in a
separate bundled `fuscript.exe` worker, PID 30840, rather than in the Resolve
process. Its Python version was 3.13.14. The report was written to a new temporary
`resolve-native-probe-unimmpn2` directory. Hide incremented `hidden_count` to one
while that worker remained alive. Activating the same menu entry restored the
same window and report without another probe directory or persistent controller.
This establishes menu-context hide/reopen behavior for that trial, not periodic
tracking or production history integration. The parent subsequently observed
`menu_invocation_returned: true` after Stop and confirmed that worker PID exited.

### Bounded worker scheduling experiment

Runtime inspection of the installed `bmd.UIDispatcher` Python binding exposed
`StepLoop(self, wait=False)` and `Dispatch(self, ev)`. This is evidence from the
shipped callable API, not a guessed timer method. The generated menu entry now
passes an explicit worker opt-in. Only that mode drives nonblocking
`StepLoop(wait=False)` on the menu worker's own thread, with standard-library
monotonic timing and short sleeps between event-pump steps. The console launch
keeps the original RunLoop path; do not opt a Resolve-process console into the
sleeping worker loop.

The worker automatically queues ten bounded native Button Clicked callbacks and
records three periodic ticks, waiting five seconds after each tick's work. It then
stops and returns after about fifteen seconds plus read latency, unless Stop is
clicked earlier. Missing StepLoop produces an explicit unsupported-host failure.
No tick records a Session. The report only marks `periodic_scheduler_verified`
after all three ticks; this alone is not a claim of production tracking safety.

The fake SDK/clock regression verifies nonblocking steps, exact worked-example
tick times of 5, 10 and 15 seconds, bounded callback delivery and cleanup. The
actual worker's cadence and full-invocation return were then tested by the parent.
The no-op trial report recorded a separate `fuscript.exe` worker, ten queued and
ten delivered callbacks with approximately 0.024–0.058 second latency, and ticks
at 5.000858, 10.001676 and 15.002405 seconds. It recorded `after_worker_loop`,
`periodic_limit` and `menu_invocation_returned: true`; the worker then exited.
That report's scope is `menu_worker_noop_only`, not a Resolve-observation test.

The next code slice reuses the existing read-only project/Page/render callback
on each tick and records its availability, state and latency inside that tick.
The scope is now `menu_worker_readonly_resolve`; errors include only exception
type and elapsed time, never private project names or error text. A fake SDK
success/failure regression covers these records. Later idle reads and the delayed
playback launch are recorded below; rendering remains unverified. No new thread, native timer,
dependency, billing engine or production tracker was introduced.

## Remaining live evidence checklist

The dedicated menu trial already established window creation, ten native callback
deliveries, hide/reopen reuse, Stop/full invocation return and worker exit. Its
bounded no-op scheduler also passed. The checks below track broader acceptance;
unchecked combined items may include those already observed substeps.

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
- [ ] Validate the proven bounded worker scheduler with periodic read-only SDK
  calls during editing/playback/rendering, then measure native worker resources.
  Do not report the queued-event test as that proof.

Live passes above come from the actual menu worker reports and process checks.
Automated fake SDK/GUI tests separately verify handler behavior, report/privacy
rules, bounded callback count, reuse and stop cleanup; they do not establish host
behavior.

## Historical console-only Windows attempts

These observations predate the successful dedicated menu worker trials above.
Their console failures remain relevant to that route, but their then-unverified
menu/callback/scheduling conclusions are superseded by the newer menu evidence.

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
now establishes visible console-context window creation. At this stage, menu
launch, controller lifetime and periodic scheduling had not yet been tested.

Clicking the initial Dispatch implementation left the displayed result at 0/10.
The cause had not yet been established. Its old implementation interpreted a missing
custom event timestamp as another initial button press; a host that drops custom
payload fields could therefore requeue indefinitely. A regression test reproduced
that case. Start-button handling and queued callbacks are now separate, with the
timestamp and bounded counter retained in Python state instead of trusting event
payloads. JSON records enqueued and delivered counts separately. The fake-host
regression was not proof of actual custom-event delivery. The later menu trial
still failed with a custom event; switching to a native Button Clicked signal
then delivered all ten callbacks.

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
controller. The subsequent Scripts-menu worker proves a viable bounded
feasibility route while preserving the working sidecar/dashboard. Keep #57 open
for the remaining read-only workload and resource evidence. Do not infer that menu
execution will behave the same as the console, or force tracker work into the
host process to reduce process count. Production tracking integration is outside
this disposable probe's scope.

## Read-only menu trial and playback limitation

On Windows 11 with Resolve Studio 21.1.1.10, the dedicated menu worker used
Python 3.13.14. The idle Deliver-page trial (`resolve-native-probe-u_3ldeua`)
delivered all ten callbacks and read the disposable project's Page/render state
at 5.002, 10.011 and 15.017 seconds. Reads took 1.9–6.3 ms, reported a project
open and rendering false, and the worker returned and exited. This establishes
bounded read-only scheduling while idle, not billable tracking.

A subsequent menu launch during looping playback created `fuscript.exe` PID
21312 under Resolve PID 19992, but produced no new report or visible probe
window during playback. After playback stopped, the same worker displayed its
window and wrote `resolve-native-probe-bj5h1y6f`. It then completed three Edit-page
reads in 2.2–3.3 ms and returned. The exact pre-report blocking call is unknown;
this is evidence of delayed launch during playback, not proof that StepLoop or a
particular getter blocked. Resolve's timecode continued advancing during the
delay. Do not claim successful native operation during playback or rendering.

After playback stopped, 24 OS process-tree samples over 21.00 seconds measured
0.446% of one core, 28.27 MB peak resident memory, one worker process and zero
remaining worker identities. This interval excludes startup and the earlier
playback delay. The PID was later reused by an unrelated process; creation
identity, rather than a bare PID existence check, establishes worker exit.

Recommendation: retain the existing tracking runtime and on-demand Electron
reporting. The bounded native worker is a viable idle utility experiment, but
its playback launch limitation prevents approving it as the production tracking
interface. Next isolate menu bootstrap from UI/SDK initialization, test launch
before playback and reads during playback/rendering, and retain the existing
worker if host calls cannot be made responsive. Production pause/resume,
activity classification, history/CSV and host-exit recovery are still pending.

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
