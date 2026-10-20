import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets

from ui.components.video_panel import (
    AUX_CAMERA_HOSTS,
    AUX_CAMERA_URL,
    MAIN_CAMERA_URL,
    TAIL_CAMERA_URL,
    VideoPanel,
    aux_camera_url,
    migrated_aux_camera_host,
    migrated_camera_selections,
)

APP = None


def ensure_qt_app():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return APP


def test_panel_has_exactly_three_fixed_camera_definitions():
    ensure_qt_app()
    panel = VideoPanel({}, "127.0.0.1")

    sources = panel.get_sources()
    assert [(source.input_text, source.out_path) for source in sources] == [
        (MAIN_CAMERA_URL, "cam1"),
        (TAIL_CAMERA_URL, "cam2"),
        (AUX_CAMERA_URL, "cam3"),
    ]
    assert [source.enabled for source in sources] == [True, True, False]
    assert not hasattr(panel, "cb_manual_cam")
    assert not hasattr(panel, "ed_manual_cam")


def test_legacy_third_or_manual_selection_migrates_to_fixed_aux_camera():
    assert migrated_camera_selections({"video": {"sources": {"manual": True}}}) == {
        "cam1": True,
        "cam2": True,
        "cam3": True,
    }
    assert migrated_camera_selections(
        {"video_sources": {"cam1": False, "cam2": True, "cam3": {"enabled": True}}}
    ) == {"cam1": False, "cam2": True, "cam3": True}

    ensure_qt_app()
    panel = VideoPanel({"video": {"manual_camera_enabled": True}}, "10.20.30.40")
    aux = panel.get_sources()[2]
    assert aux.enabled
    assert aux.input_text == AUX_CAMERA_URL
    assert aux.out_path == "cam3"


def test_aux_copy_url_uses_complete_current_output_url():
    ensure_qt_app()
    panel = VideoPanel({}, "10.20.30.40", 9554)

    aux_row = panel._source_rows[2]
    copy_button = aux_row["card"].findChildren(QtWidgets.QPushButton)[0]
    copy_button.click()

    assert QtWidgets.QApplication.clipboard().text() == "rtsp://10.20.30.40:9554/cam3"


def test_output_url_tracks_shared_video_settings():
    ensure_qt_app()
    panel = VideoPanel({}, "10.20.30.40", 8554)
    panel.set_output("192.168.10.2", 10554)
    assert panel.output_url("/cam1") == "rtsp://192.168.10.2:10554/cam1"


def test_aux_source_ip_selector_changes_only_the_host():
    ensure_qt_app()
    panel = VideoPanel({}, "10.20.30.40")
    selector = panel._source_rows[2]["source_selector"]

    assert tuple(selector.itemText(index) for index in range(selector.count())) == AUX_CAMERA_HOSTS
    selector.setCurrentText("192.168.144.26")

    aux = panel.get_sources()[2]
    assert aux.input_text == "rtsp://192.168.144.26:8554/main.264"
    assert aux.out_path == "cam3"
    assert panel.output_url(aux.out_path) == "rtsp://10.20.30.40:8554/cam3"


def test_saved_aux_host_migration_accepts_only_supported_hosts():
    assert migrated_aux_camera_host(
        {"video": {"sources": {"cam3": {"url": aux_camera_url("192.168.144.26")}}}}
    ) == "192.168.144.26"
    assert migrated_aux_camera_host(
        {"video": {"sources": {"cam3": {"url": "rtsp://10.0.0.5/custom"}}}}
    ) == "192.168.144.25"
