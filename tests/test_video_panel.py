import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets
from ui.components.video_panel import DEFAULT_MANUAL_CAMERA_ADDRESS, VideoPanel

APP = None


def ensure_qt_app():
    global APP

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    APP = app
    return app


def test_manual_camera_address_defaults_disabled_and_editable_when_enabled():
    ensure_qt_app()
    panel = VideoPanel({}, "127.0.0.1")

    assert not panel.cb_manual_cam.isChecked()
    assert not panel.ed_manual_cam.isEnabled()
    assert panel.ed_manual_cam.text() == DEFAULT_MANUAL_CAMERA_ADDRESS
    assert all(source.out_path != "cam3" for source in panel.get_sources())

    panel.cb_manual_cam.setChecked(True)

    assert panel.ed_manual_cam.isEnabled()
    manual_sources = [source for source in panel.get_sources() if source.out_path == "cam3"]
    assert len(manual_sources) == 1
    assert manual_sources[0].input_text == DEFAULT_MANUAL_CAMERA_ADDRESS

    panel.ed_manual_cam.setText("rtsp://192.168.144.99:8554/custom.264")

    manual_sources = [source for source in panel.get_sources() if source.out_path == "cam3"]
    assert manual_sources[0].input_text == "rtsp://192.168.144.99:8554/custom.264"

    panel.cb_manual_cam.setChecked(False)

    assert not panel.ed_manual_cam.isEnabled()
    assert all(source.out_path != "cam3" for source in panel.get_sources())
