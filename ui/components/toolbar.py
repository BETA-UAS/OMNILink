from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

from ui.components.common import set_button_role


class Toolbar(QtWidgets.QWidget):
    refresh_ip_requested = QtCore.pyqtSignal()
    start_all_requested = QtCore.pyqtSignal()
    stop_all_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolbar")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        title_container = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)

        self.logo = QtWidgets.QLabel()
        self.logo.setObjectName("appLogo")
        self.logo.setFixedSize(42, 30)
        self.logo.setAlignment(QtCore.Qt.AlignCenter)

        logo_path = Path(__file__).resolve().parents[1] / "assets" / "betawhite.png"
        logo_pixmap = QtGui.QPixmap(str(logo_path))

        if not logo_pixmap.isNull():
            self.logo.setPixmap(
                logo_pixmap.scaled(
                    self.logo.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )

        self.title = QtWidgets.QLabel("OMNI-Link")
        self.title.setObjectName("appTitle")
        self.title.setAlignment(QtCore.Qt.AlignVCenter)

        title_layout.addWidget(self.logo)
        title_layout.addWidget(self.title)

        layout.addWidget(title_container)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)

        self.btn_refresh_ip = QtWidgets.QPushButton("Refresh Ethernet IP")
        self.btn_start_all = QtWidgets.QPushButton("Start All")
        self.btn_stop_all = QtWidgets.QPushButton("Stop All")
        self.btn_stop_all.setEnabled(False)
        for button in (self.btn_refresh_ip, self.btn_start_all, self.btn_stop_all):
            button.setMinimumHeight(32)
        self.btn_start_all.setMinimumWidth(96)
        self.btn_stop_all.setMinimumWidth(96)

        set_button_role(self.btn_refresh_ip, "secondary")
        set_button_role(self.btn_start_all, "primary")
        set_button_role(self.btn_stop_all, "danger")

        actions.addStretch(1)
        actions.addWidget(self.btn_refresh_ip)
        actions.addWidget(self.btn_start_all)
        actions.addWidget(self.btn_stop_all)

        layout.addLayout(actions)

        self.btn_refresh_ip.clicked.connect(self.refresh_ip_requested)
        self.btn_start_all.clicked.connect(self.start_all_requested)
        self.btn_stop_all.clicked.connect(self.stop_all_requested)

    def set_any_running(self, any_on: bool) -> None:
        self.btn_start_all.setEnabled(not any_on)
        self.btn_stop_all.setEnabled(any_on)
