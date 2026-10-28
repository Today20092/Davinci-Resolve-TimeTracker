# Resolve-hosted tracker feasibility

Research continuation for [#57](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/57), 2026-10-27. This is a documentation review and a standalone interpreter capability probe, not a native tracker prototype.

## Decision for the next step

Try a small Python UIManager host/lifetime probe before porting the application or choosing Lua. Resolve 21.1 supplies Python and LuaJIT, and the bundled Windows Python has SQLite and ctypes. However, a bundled interpreter executable is not evidence that menu scripts run in the Resolve application process. The strict requirement of no separate tracker-owned process remains unproven. [S1, S2, P1]

Do not rewrite the dashboard, remove the working sidecar, change Python compatibility constraints, or migrate history until the host/lifetime probe succeeds. Existing standalone reporting after Resolve exits would be intentionally lost under a strict Resolve-only model. [#57](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/57)

## Evidence and limits

| Question | Finding | Evidence strength |
| --- | --- | --- |
| Does Resolve supply Python? | Installed scripting documentation says Resolve 21.1 and later includes a custom Python 3.14 distribution, with automatic bridge import configuration but without pip, TK or IDLE. | Documented, S1 lines 92–112. |
| Can Python access local storage without a server? | The bundled Windows interpreter successfully imports sqlite3 and ctypes. SQLite reports 3.50.4. | Direct standalone probe P1; not a Mac or embedded-host result. |
| Is the current package compatible with that interpreter? | Its declared requirement is Python >=3.10,<3.14. Standard installation is excluded by that declaration; no application compatibility test on Python 3.14 was performed, so this is not evidence of an actual engine/runtime failure. | Repository declaration, [pyproject.toml](../../pyproject.toml). |
| Is a native utility UI documented? | UIManager and UIDispatcher create windows and dispatch events. The supplied Python example uses FindWindow and a stable window ID to focus an existing window. | Documented and first-party example, S2/S3. |
| Does closing a window preserve tracking? | The sample's close handler exits the dispatcher loop. Keeping a controller alive after hiding/closing its UI is not demonstrated by that sample. | S3; persistent-controller behavior remains untested. |
| Is a periodic host-safe scheduler established? | The inspected introductory UIDispatcher reference documents RunLoop, ExitLoop and QueueEvent. It does not establish a periodic timer API, event-loop reentrancy or thread-safe Resolve calls. The document explicitly says it is not exhaustive. | Bounded negative finding, S2 lines 155–185 and 351–352. Do not infer that timers are impossible. |
| Are Electron Workflow Integrations a solution? | They are Electron applications according to the SDK; they do not satisfy the no-Electron requirement. Python/Lua UIManager scripts are a separate option. | S2 Overview and Sample Workflow Integration Script sections. |
| Is automatic application startup established? | Startup script-folder scanning creates menu entries; it is not a documented application-wide execution hook in the inspected material. | S1 Script Menu and Script Locations section; automatic execution remains unverified. |
| Can the existing bridge be reused? | ResolveBridge accepts an injected resolve_object, avoiding its external connection setup. Its snapshot also reads optional timeline/timecode information and OS activity, so injecting an object alone does not establish safe host scheduling. | [resolve_bridge.py](../../src/resolve_time_tracker/resolve_bridge.py), ResolveBridge constructor, snapshot and resolve. |

The bridge's inbound call graph currently routes through api.run_api. Reuse the engine/storage and injection seam in a separate feasibility entry point; do not instantiate the HTTP runtime merely to get a bridge object. This is a prototype design inference from the current call graph, not a host integration result. [resolve_bridge.py](../../src/resolve_time_tracker/resolve_bridge.py), [api.py](../../src/resolve_time_tracker/api.py)

## macOS implications

The installed SDK gives the bundled interpreter path as `/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython` and LuaJIT as the app's `Contents/Libraries/Fusion/fuscript`. These paths describe the installed SDK's supported distribution; confirm the user's actual edition/version and bundle layout on the Mac. Launching either executable from a shell creates a separate process and therefore does not prove the strict hosting goal. [S1 lines 100–112]

Apple documents a Core Graphics function that reports time since an input event, including an all-input event selector. It also documents NSWorkspace.frontmostApplication as the application receiving key events. These are candidate native signals for a Mac implementation, not proof that the required Python bindings, permissions or host-thread behavior are available inside Resolve. A future ctypes/native bridge must be tested on the Mac; do not add an Objective-C bridge dependency before establishing what is already available. [Apple idle-time API](https://developer.apple.com/documentation/coregraphics/cgeventsource/secondssincelasteventtype(_:eventtype:)?language=objc), [Apple foreground-app API](https://developer.apple.com/documentation/appkit/nsworkspace/frontmostapplication?language=objc)

UIManager HasFocus describes a widget's focus and is not evidence of Resolve application foreground state. Preserve the existing rule that unavailable activity cannot silently become billable Active Work. [S2 common element functions], [activity_tracker.py](../../src/resolve_time_tracker/activity_tracker.py)

## Smallest next prototype

1. Use a saved disposable Resolve project and temporary tracker data. Record OS, edition/version and SDK documentation revision. Do not touch production history or install a new startup mechanism.
2. Start a minimal UIManager script from Resolve's menu. Record script PID, parent PID, interpreter version, module availability and the application process tree. Determine whether execution is genuinely inside Resolve or uses a separate interpreter, and whether that process exists only for this script.
3. Create one window with a stable ID using the first-party sample pattern. Repeated activation should focus/reuse it. Test Show/Hide separately from the sample's ExitLoop shutdown. Record whether script state survives the return of the menu invocation and a later activation.
4. Establish a supported periodic scheduling mechanism by inspecting the actual host API/docs, then run a bounded number of short callbacks with timestamps. Do not invent AddTimer syntax or assume QueueEvent schedules future work. Begin with host-only no-op callbacks, then the minimum read-only project/Page/render getters.
5. Have the user exercise editing, playback and a short render while observing responsiveness and callback latency. Do not intentionally block an SDK call in the host process. Stop the prototype if responsiveness degrades.
6. Confirm SQLite/ctypes availability in this exact script context. Write/read a temporary database only after the process/lifetime test passes. Then evaluate native Mac idle/foreground reads and denial/unavailable behavior.
7. Record a pass/fail result for process ownership, singleton behavior, UI-independent lifetime, supported scheduling, responsiveness and persistence. Only then connect the existing Session engine and storage. A failed Python host test may justify a Lua comparison, not an immediate port of billing/storage logic.

No external tracker process is a hard acceptance condition, not a naming choice. If both languages require a separate script process, record the strict goal as unsupported by the tested route and present that evidence before changing scope. [#57](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/57)

## Sources and reproduction

- **S1:** Installed first-party SDK `C:/ProgramData/Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/README.md`, especially Script Menu/Locations, Built-in Python and LuaJIT Interpreters, External Interpreters and Studio API limitations. On the Mac, inspect the equivalent Developer/Scripting documentation shipped with the actual installation.
- **S2:** Installed first-party SDK `C:/ProgramData/Blackmagic Design/DaVinci Resolve/Support/Developer/Workflow Integrations/README.txt`, marked updated 3 October 2024; Overview, Sample Workflow Integration Script, UIDispatcher Functions, common element functions and final non-exhaustiveness notice.
- **S3:** Installed first-party sample `C:/ProgramData/Blackmagic Design/DaVinci Resolve/Support/Developer/Workflow Integrations/Examples/Sample Script Plugin.py`, window ID/single-instance check and OnClose handler. Its example contains a project-creation action; it was read, not executed.
- **P1:** Ran only the installed `ResolvePython/ResolvePython.exe` with `-I -c` importing `sys`, `sqlite3`, `ctypes`, `json`, and `importlib.util`. Output: Python 3.14.4, SQLite 3.50.4, ctypes import successful, DaVinciResolveScript module discoverable. No connection to Resolve, project mutation, UI script, package install or database write was performed.
- Existing user-owned `resolve-21.1-*` research notes were read as context and left unchanged; they are not substitutes for the first-party SDK evidence above.

Context7 resolution was attempted for the Resolve/Fusion SDK, but the service reported its monthly quota exhausted. No documentation query could run. Installed first-party SDK documentation and current Apple documentation supplied the API evidence instead.

Exact P1 command, from PowerShell:

```powershell
& 'C:/Program Files/Blackmagic Design/DaVinci Resolve/ResolvePython/ResolvePython.exe' -I -c 'import sys, sqlite3, ctypes, json, importlib.util; print(json.dumps({"version":sys.version,"sqlite":sqlite3.sqlite_version,"ctypes":bool(ctypes),"bridge_found":importlib.util.find_spec("DaVinciResolveScript") is not None}))'
```

The analogous standalone check on a Mac can use its installed ResolvePython executable with the same Python expression. It only establishes that executable's capabilities. The decisive next check still runs from the menu and compares the script PID with Resolve's actual PID before testing a persistent UI/controller.

No live Resolve execution, native scheduling, Mac behavior, permission handling, crash recovery or zero-process ownership was verified in this continuation. Resolve was not running, and was not launched.
