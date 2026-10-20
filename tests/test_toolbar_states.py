import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets
from ui.components.toolbar import Toolbar
from ui.main_window import MainWindow

APP = None


def ensure_app():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return APP


def test_toolbar_service_state_labels_roles_and_stable_size():
    ensure_app()
    toolbar = Toolbar()
    size = toolbar.btn_video.size()
    toolbar.set_service_state("video", "starting")
    assert toolbar.btn_video.text() == "Starting Video…"
    assert toolbar.btn_video.property("serviceState") == "starting"
    assert not toolbar.btn_video.isEnabled()
    toolbar.set_service_state("video", "running")
    assert toolbar.btn_video.text() == "Stop Video"
    assert toolbar.btn_video.property("serviceState") == "running"
    assert toolbar.btn_video.isEnabled()
    assert toolbar.btn_video.size() == size
    toolbar.set_service_state("video", "failed")
    assert toolbar.btn_video.text() == "Start Video"
    assert toolbar.btn_video.property("serviceState") == "failed"


def test_transition_disables_conflicting_actions_then_restores_them():
    ensure_app()
    toolbar = Toolbar()
    toolbar.set_service_state("video", "starting")
    toolbar.set_all_state("starting", "stopped")
    assert not toolbar.btn_video.isEnabled()
    assert not toolbar.btn_telemetry.isEnabled()
    assert not toolbar.btn_all.isEnabled()

    toolbar.set_service_state("video", "running")
    toolbar.set_all_state("running", "stopped")
    assert toolbar.btn_video.isEnabled()
    assert toolbar.btn_telemetry.isEnabled()
    assert toolbar.btn_all.isEnabled()


def test_start_all_dispatches_only_missing_service_and_stop_all_dispatches_both():
    calls = []
    window = SimpleNamespace(
        _service_states={"video": "running", "telemetry": "stopped"},
        _start_video=lambda: calls.append("start-video"),
        _start_telemetry=lambda: calls.append("start-telemetry"),
        _stop_video=lambda: calls.append("stop-video"),
        _stop_telemetry=lambda: calls.append("stop-telemetry"),
    )
    MainWindow._toggle_all(window)
    assert calls == ["start-telemetry"]
    calls.clear()
    window._service_states = {"video": "running", "telemetry": "running"}
    MainWindow._toggle_all(window)
    assert calls == ["stop-video", "stop-telemetry"]


def test_repeated_start_click_does_not_dispatch_duplicate_manager_start():
    starts = []
    manager = SimpleNamespace(start=lambda **kwargs: starts.append(kwargs))
    settings = SimpleNamespace(
        get_video_options=lambda: {
            "mediamtx_bin": "/bin/true",
            "out_port": 8554,
            "global_bitrate_kbps": 2500,
            "passthrough": False,
        },
    )
    panel = SimpleNamespace(get_sources=lambda: [])
    window = SimpleNamespace(
        _service_states={"video": "stopped"},
        video=manager,
        video_panel=panel,
        video_settings=settings,
        _refresh_ethernet_ip=lambda: None,
        _service_failed=lambda *_args: None,
    )

    def set_state(service, state):
        window._service_states[service] = state

    window._set_service_state = set_state
    MainWindow._start_video(window)
    MainWindow._start_video(window)
    assert len(starts) == 1


def test_start_all_from_stopped_dispatches_both_services():
    calls = []
    window = SimpleNamespace(
        _service_states={"video": "stopped", "telemetry": "failed"},
        _start_video=lambda: calls.append("start-video"),
        _start_telemetry=lambda: calls.append("start-telemetry"),
        _stop_video=lambda: calls.append("stop-video"),
        _stop_telemetry=lambda: calls.append("stop-telemetry"),
    )
    MainWindow._toggle_all(window)
    assert calls == ["start-video", "start-telemetry"]
