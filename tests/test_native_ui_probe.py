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
        return self.items.setdefault(name, SimpleNamespace(Text=""))


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
        for name in (WINDOW_ID, "Read", "Dispatch", "Hide", "Stop", "ProbeEvent"):
            window.On[name] = SimpleNamespace()
        self.windows[props["ID"]] = window
        return window

    def RunLoop(self):
        self.loop_runs += 1
        for action in self.actions:
            action(self.windows[WINDOW_ID])
        while self.events:
            window, name, event = self.events.pop(0)
            getattr(window.On[WINDOW_ID], name)(event)

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
