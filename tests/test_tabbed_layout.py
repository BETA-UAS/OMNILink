import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets

from ui.main_window import MainWindow

APP = None


def ensure_app():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return APP


def load_config():
    path = Path(__file__).resolve().parents[1] / "config" / "settings.json"
    return json.loads(path.read_text())


def build_window(monkeypatch):
    ensure_app()
    monkeypatch.setattr(MainWindow, "_request_ping_refresh", lambda self: None)
    monkeypatch.setattr("ui.main_window.ResourceSampler.start", lambda self: None)
    monkeypatch.setattr("ui.main_window.TrafficSampler.start", lambda self: None)
    return MainWindow(load_config())


def test_tabs_preserve_camera_and_destination_selections(monkeypatch):
    window = build_window(monkeypatch)
    window.video_panel._source_rows[2]["checkbox"].setChecked(True)
    window.telemetry_operate.target_checkboxes["Student"].setChecked(False)

    window.tabs.setCurrentIndex(1)
    window.tabs.setCurrentIndex(2)
    window.tabs.setCurrentIndex(0)

    assert window.video_panel.get_sources()[2].enabled
    assert not window.telemetry_panel.target_enabled("Student")
    assert not window.telemetry_operate.target_checkboxes["Student"].isChecked()


def test_network_devices_remain_on_operate_and_use_three_columns(monkeypatch):
    app = ensure_app()
    window = build_window(monkeypatch)
    window.resize(1280, 720)
    window.show()
    app.processEvents()

    assert window.tabs.currentIndex() == 0
    assert window.network_status_panel.isVisible()
    assert len(window.network_status_panel.ping_cards) == 6
    assert window.network_status_panel._status_cols == 3
    assert window.network_status_panel.parentWidget() is not window.settings_scroll
    window.hide()
