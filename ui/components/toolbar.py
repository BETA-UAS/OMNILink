import sys
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets
from ui.components.common import set_button_role, set_service_state


def logo_asset_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "ui" / "assets" / "betawhite.png"
    return Path(__file__).resolve().parents[1] / "assets" / "betawhite.png"


class Toolbar(QtWidgets.QWidget):
    refresh_requested = QtCore.pyqtSignal()
    video_toggle_requested = QtCore.pyqtSignal()
    telemetry_toggle_requested = QtCore.pyqtSignal()
    all_toggle_requested = QtCore.pyqtSignal()
    profile_changed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolbar")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(14)

        self.logo = QtWidgets.QLabel()
        self.logo.setObjectName("appLogo")
        self.logo.setFixedSize(82, 54)
        pixmap = QtGui.QPixmap(str(logo_asset_path()))
        if not pixmap.isNull():
            self.logo.setPixmap(
                pixmap.scaled(
                    self.logo.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
                )
            )

        brand = QtWidgets.QVBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(0)
        title = QtWidgets.QLabel("OMNI-Link")
        title.setObjectName("appTitle")
        brand.addWidget(title)

        self.profile_selector = QtWidgets.QComboBox()
        self.profile_selector.addItem("Demonstrator", "HM30")
        self.profile_selector.addItem("Omni Trainer", "IVCAN")
        self.profile_selector.setCurrentIndex(1)
        self.profile_selector.setFixedSize(196, 48)
        self.profile_selector.setObjectName("profileSelector")

        layout.addWidget(self.logo)
        layout.addLayout(brand)
        layout.addWidget(self.profile_selector)
        layout.addStretch(1)

        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_video = QtWidgets.QPushButton("Start Video")
        self.btn_telemetry = QtWidgets.QPushButton("Start Telemetry")
        self.btn_all = QtWidgets.QPushButton("Start All")
        self.btn_refresh.setFixedSize(152, 54)
        self.btn_video.setFixedSize(170, 54)
        self.btn_telemetry.setFixedSize(207, 54)
        self.btn_all.setFixedSize(156, 54)
        set_button_role(self.btn_refresh, "secondary")
        set_button_role(self.btn_all, "secondary")
        self.set_service_state("video", "stopped")
        self.set_service_state("telemetry", "stopped")

        for button in (self.btn_refresh, self.btn_video, self.btn_telemetry, self.btn_all):
            layout.addWidget(button)

        self.btn_refresh.clicked.connect(self.refresh_requested)
        self.btn_video.clicked.connect(self.video_toggle_requested)
        self.btn_telemetry.clicked.connect(self.telemetry_toggle_requested)
        self.btn_all.clicked.connect(self.all_toggle_requested)
        self.profile_selector.currentIndexChanged.connect(
            lambda _index: self.profile_changed.emit(self.selected_profile())
        )

    def selected_profile(self) -> str:
        return str(self.profile_selector.currentData())

    def set_service_state(self, service: str, state: str) -> None:
        button = self.btn_video if service == "video" else self.btn_telemetry
        noun = "Video" if service == "video" else "Telemetry"
        labels = {
            "stopped": f"Start {noun}",
            "failed": f"Start {noun}",
            "starting": f"Starting {noun}…",
            "running": f"Stop {noun}",
            "stopping": "Stopping…",
        }
        button.setText(labels[state])
        button.setEnabled(state not in {"starting", "stopping"})
        set_service_state(button, state)

    def set_all_state(self, video_state: str, telemetry_state: str) -> None:
        transitioning = any(
            state in {"starting", "stopping"} for state in (video_state, telemetry_state)
        )
        both_running = video_state == telemetry_state == "running"
        self.btn_all.setText("Stop All" if both_running else "Start All")
        self.btn_all.setEnabled(not transitioning)
        set_service_state(self.btn_all, "running" if both_running else "neutral")
        if transitioning:
            self.btn_video.setEnabled(False)
            self.btn_telemetry.setEnabled(False)
        else:
            self.btn_video.setEnabled(video_state not in {"starting", "stopping"})
            self.btn_telemetry.setEnabled(
                telemetry_state not in {"starting", "stopping"}
            )
