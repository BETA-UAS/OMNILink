from types import SimpleNamespace

from ui.main_window import DEFAULT_PING_INTERVAL_MS, MainWindow


class FakeRunning:
    def __init__(self, running: bool):
        self.running = running

    def is_running(self) -> bool:
        return self.running


class FakeTimer:
    def __init__(self, active: bool = False):
        self.active = active
        self.started_with = None
        self.stopped = False

    def isActive(self) -> bool:
        return self.active

    def start(self, interval_ms: int) -> None:
        self.active = True
        self.started_with = interval_ms

    def stop(self) -> None:
        self.active = False
        self.stopped = True


class FakePanel:
    def __init__(self):
        self.paused = None
        self.refreshing = None

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def set_refreshing(self, refreshing: bool) -> None:
        self.refreshing = refreshing


class FakeWorker:
    def __init__(self):
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class MainWindowStub(SimpleNamespace):
    _ping_should_pause = MainWindow._ping_should_pause
    _cancel_ping_refresh = MainWindow._cancel_ping_refresh


def main_window_stub(**overrides):
    values = {
        "config": {},
        "video": FakeRunning(False),
        "router": FakeRunning(False),
        "ping_timer": FakeTimer(False),
        "network_status_panel": FakePanel(),
        "_ping_running": False,
        "_ping_worker": None,
        "_ping_interval_ms": DEFAULT_PING_INTERVAL_MS,
    }
    values.update(overrides)
    return MainWindowStub(**values)


def test_configured_ping_interval_has_safe_minimum():
    window = main_window_stub(config={"ping_interval_ms": 1000})

    assert MainWindow._configured_ping_interval_ms(window) == 60000


def test_ping_policy_pauses_when_router_is_running():
    worker = FakeWorker()
    timer = FakeTimer(active=True)
    panel = FakePanel()
    window = main_window_stub(
        router=FakeRunning(True),
        ping_timer=timer,
        network_status_panel=panel,
        _ping_worker=worker,
    )

    MainWindow._sync_ping_state(window)

    assert timer.stopped
    assert worker.cancelled
    assert panel.paused is True


def test_ping_policy_resumes_timer_when_idle():
    timer = FakeTimer(active=False)
    panel = FakePanel()
    window = main_window_stub(
        ping_timer=timer,
        network_status_panel=panel,
        _ping_running=False,
        _ping_interval_ms=300000,
    )

    MainWindow._sync_ping_state(window)

    assert panel.paused is False
    assert panel.refreshing is False
    assert timer.started_with == 300000
