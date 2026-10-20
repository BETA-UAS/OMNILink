import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets
from ui.components.telemetry_panel import TelemetryPanel

APP = None


def ensure_app():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return APP


def test_preset_endpoint_summary_comes_from_configuration():
    ensure_app()
    config = {
        "telemetry": {
            "input_presets": {
                "HM30": {"mode": "UDP", "listen_udp": 19856},
                "IVCAN": {
                    "mode": "TCP",
                    "tcp_up_ip": "10.50.0.7",
                    "tcp_up_port": 21001,
                },
            }
        }
    }
    panel = TelemetryPanel(config)
    assert panel.effective_connection_summary() == "TCP · 10.50.0.7:21001"


def test_instrument_light_details_are_collapsed_while_disabled():
    ensure_app()
    panel = TelemetryPanel({})
    assert not panel.ed_espusr_ip.isVisible()
    panel.show()
    panel.cb_espusr_enable.setChecked(True)
    assert not panel.ed_espusr_ip.isHidden()
