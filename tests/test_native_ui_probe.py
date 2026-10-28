import json
from types import SimpleNamespace

import pytest

from scripts.native_ui_probe import WINDOW_ID, main, run_probe


class Window:
    def __init__(self, props):
        self.props = props
        self.visible = False
        self.raised = False
        self.items = {}
        self.On = {}

    def Show(self):
        self.visible = True

    def Hide(self):
        self.visible = False

    def Raise(self):
        self.raised = True

    def Find(self, name):
        return self.items.setdefault(
            name, SimpleNamespace(Text="", window=self, name=name)
        )


class Host:
    def __init__(self):
        self.UIManager = self
        self.windows = {}
        self.actions = []
        self.exited = False
        self.loop_runs = 0
        self.events = []

    def FindWindow(self, name):
        return self.windows.get(name)

    def VGroup(self, children):
        return children

    def HGroup(self, children):
        return children

    def Label(self, props):
        return props

    def Button(self, props):
        return props

    def UIDispatcher(self, ui):
        assert ui is self
        return self

    def AddWindow(self, props, children):
        window = Window(props)
        for name in (WINDOW_ID, "Read", "Dispatch", "Hide", "Stop", "Callback"):
            window.On[name] = SimpleNamespace()
        self.windows[props["ID"]] = window
        return window

    def RunLoop(self):
        self.loop_runs += 1
        for action in self.actions:
            action(self.windows[WINDOW_ID])
        while self.events:
            widget, name, event = self.events.pop(0)
            getattr(widget.window.On[widget.name], name)(event)

    def QueueEvent(self, window, name, event):
        self.events.append((window, name, event))

    def ExitLoop(self):
        self.exited = True


def test_probe_records_capabilities_in_disposable_report(tmp_path):
    host = Host()
    target = tmp_path / "probe.json"
    result = run_probe(None, host, host, report_path=target)

    assert result["tracking_connected"] is False
    assert result["sqlite_available"] is True
    assert result["ctypes_available"] is True
    assert result["periodic_scheduler_verified"] is False
    assert result["pid"] > 0
    assert json.loads(target.read_text())["window_id"] == WINDOW_ID
    assert host.loop_runs == 1


def test_close_preserves_dispatcher_and_reactivation_reuses_window(tmp_path):
    host = Host()

    def close_then_reopen(window):
        window.On[WINDOW_ID].Close({})
        assert window.visible is False
        assert host.exited is False
        result = run_probe(None, host, host, report_path=tmp_path / "unused.json")
        assert result["reused_window"] is True
        assert window.visible and window.raised
        window.On["Stop"].Clicked({})

    host.actions = [close_then_reopen]
    report = run_probe(None, host, host, report_path=tmp_path / "probe.json")
    assert report["hidden_count"] == 1
    assert report["stopped"] is True
    assert host.exited is True
    assert host.loop_runs == 1
    assert not (tmp_path / "unused.json").exists()


def test_dispatch_probe_is_bounded_and_does_not_claim_periodic_scheduling(tmp_path):
    host = Host()
    host.actions = [lambda window: window.On["Dispatch"].Clicked({})]
    result = run_probe(None, host, host, report_path=tmp_path / "probe.json")
    assert len(result["dispatch_callbacks"]) == 10
    assert all(item["latency_seconds"] >= 0 for item in result["dispatch_callbacks"])
    assert result["periodic_scheduler_verified"] is False


def test_dispatch_stays_bounded_when_host_drops_custom_event_fields(tmp_path):
    class PayloadDroppingHost(Host):
        def QueueEvent(self, window, name, event):
            self.events.append((window, name, {}))

        def RunLoop(self):
            self.loop_runs += 1
            self.windows[WINDOW_ID].On["Dispatch"].Clicked({})
            delivered = 0
            while self.events and delivered < 30:
                widget, name, event = self.events.pop(0)
                getattr(widget.window.On[widget.name], name)(event)
                delivered += 1
            assert delivered == 10
            assert not self.events

    host = PayloadDroppingHost()
    result = run_probe(None, host, host, report_path=tmp_path / "probe.json")
    assert len(result["dispatch_callbacks"]) == 10


def test_resolve_reads_are_explicit_read_only_and_do_not_log_project_names(tmp_path):
    host = Host()
    project = SimpleNamespace(
        GetName=lambda: "private <project>", IsRenderingInProgress=lambda: False
    )
    resolve = SimpleNamespace(
        GetProjectManager=lambda: SimpleNamespace(GetCurrentProject=lambda: project),
        GetCurrentPage=lambda: "edit",
    )
    host.actions = [lambda window: window.On["Read"].Clicked({})]
    report = run_probe(resolve, host, host, report_path=tmp_path / "probe.json")
    assert report["resolve_read"]["project_open"] is True
    assert report["resolve_read"]["page"] == "edit"
    assert report["resolve_read"]["rendering"] is False
    assert "private" not in (tmp_path / "probe.json").read_text()
    assert "&lt;project&gt;" in host.windows[WINDOW_ID].Find("Status").Text


def test_failed_resolve_read_is_explicit_and_never_assumes_activity(tmp_path):
    host = Host()
    host.actions = [lambda window: window.On["Read"].Clicked({})]
    report = run_probe(None, host, host, report_path=tmp_path / "probe.json")
    assert report["resolve_read"]["available"] is False
    assert report["tracking_connected"] is False


def test_standalone_entry_refuses_to_connect_to_or_start_resolve():
    with pytest.raises(RuntimeError, match="Resolve.*console"):
        main({})


def test_stop_exits_even_if_report_can_no_longer_be_saved(tmp_path):
    host = Host()
    target = tmp_path / "probe.json"

    def stop_with_unwritable_report(window):
        target.unlink()
        target.mkdir()
        window.On["Stop"].Clicked({})

    host.actions = [stop_with_unwritable_report]
    with pytest.raises(OSError):
        run_probe(None, host, host, report_path=target)
    assert host.exited is True
    assert host.windows[WINDOW_ID].visible is False


def test_probe_records_sdk_phase_before_a_failure_without_private_error_text(tmp_path):
    class BrokenDispatcher(Host):
        def UIDispatcher(self, ui):
            raise RuntimeError("private host detail")

    host = BrokenDispatcher()
    target = tmp_path / "probe.json"
    with pytest.raises(RuntimeError):
        run_probe(None, host, host, report_path=target)
    report = json.loads(target.read_text())
    assert report["phase"] == "failed"
    assert report["failed_phase"] == "dispatcher"
    assert report["error_type"] == "RuntimeError"
    assert "private host detail" not in target.read_text()


def test_probe_reports_completed_host_phases(tmp_path):
    host = Host()
    result = run_probe(None, host, host, report_path=tmp_path / "probe.json")
    assert result["phases"] == [
        "before_dispatcher",
        "after_dispatcher",
        "before_layout",
        "after_layout",
        "before_window",
        "after_window",
        "before_handlers",
        "after_handlers",
        "before_show",
        "after_show",
        "before_run_loop",
        "after_run_loop",
    ]


def test_dispatch_uses_a_native_signal_instead_of_an_arbitrary_event_name(tmp_path):
    class NativeSignalOnlyHost(Host):
        def QueueEvent(self, window, name, event):
            if name == "Clicked":
                super().QueueEvent(window, name, event)

    host = NativeSignalOnlyHost()
    host.actions = [lambda window: window.On["Dispatch"].Clicked({})]
    result = run_probe(None, host, host, report_path=tmp_path / "probe.json")
    assert len(result["dispatch_callbacks"]) == 10


@pytest.mark.parametrize("resolve_available", [True, False])
def test_opt_in_menu_worker_delivers_bounded_periodic_ticks_on_the_ui_thread(
    tmp_path, monkeypatch, resolve_available
):
    class StepHost(Host):
        def __init__(self):
            super().__init__()
            self.waits = []

        def StepLoop(self, wait=False):
            self.waits.append(wait)
            if self.actions:
                self.actions.pop(0)(self.windows[WINDOW_ID])
            if self.events:
                widget, name, event = self.events.pop(0)
                getattr(widget.window.On[widget.name], name)(event)

    clock = [0.0]
    monkeypatch.setattr("scripts.native_ui_probe.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "scripts.native_ui_probe.time.sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    host = StepHost()
    host.actions = [lambda window: window.On["Dispatch"].Clicked({})]
    project = SimpleNamespace(
        GetName=lambda: "private test project", IsRenderingInProgress=lambda: False
    )
    resolve = (
        SimpleNamespace(
            GetProjectManager=lambda: SimpleNamespace(
                GetCurrentProject=lambda: project
            ),
            GetCurrentPage=lambda: "edit",
        )
        if resolve_available
        else None
    )
    result = run_probe(
        resolve, host, host, report_path=tmp_path / "probe.json", menu_worker=True
    )

    assert [tick["elapsed_seconds"] for tick in result["periodic_callbacks"]] == [
        5.0,
        10.0,
        15.0,
    ]
    assert len(result["dispatch_callbacks"]) == 10
    assert set(host.waits) == {False}
    assert host.loop_runs == 0
    assert host.exited and not host.windows[WINDOW_ID].visible
    assert result["stop_reason"] == "periodic_limit"
    assert result["tracking_connected"] is False
    assert result["periodic_scope"] == "menu_worker_readonly_resolve"
    assert [
        tick["resolve_read"]["available"] for tick in result["periodic_callbacks"]
    ] == [resolve_available] * 3
    assert all(
        tick["resolve_read"]["duration_seconds"] >= 0
        for tick in result["periodic_callbacks"]
    )
    if resolve_available:
        assert [
            tick["resolve_read"]["page"] for tick in result["periodic_callbacks"]
        ] == ["edit"] * 3
    else:
        assert [
            tick["resolve_read"]["error_type"] for tick in result["periodic_callbacks"]
        ] == ["AttributeError"] * 3
    assert "private test project" not in (tmp_path / "probe.json").read_text()


def test_menu_worker_fails_clearly_if_nonblocking_step_loop_is_unavailable(tmp_path):
    host = Host()
    with pytest.raises(RuntimeError, match="StepLoop"):
        run_probe(
            None, host, host, report_path=tmp_path / "probe.json", menu_worker=True
        )
