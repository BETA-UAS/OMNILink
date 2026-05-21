from PyQt5 import QtCore, QtWidgets
from ui.components.common import set_button_role


class Toolbar(QtWidgets.QWidget):
    refresh_ip_requested = QtCore.pyqtSignal()
    start_all_requested = QtCore.pyqtSignal()
    stop_all_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolbar")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        title = QtWidgets.QLabel("OMNI-Link")
        title.setObjectName("appTitle")


        title_box = QtWidgets.QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(1)
        title_box.addWidget(title)
        layout.addLayout(title_box)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)

        self.btn_refresh_ip = QtWidgets.QPushButton("Refresh Ethernet IP")
        self.btn_start_all = QtWidgets.QPushButton("Start All")
        self.btn_stop_all = QtWidgets.QPushButton("Stop All")
        self.btn_stop_all.setEnabled(False)
        set_button_role(self.btn_refresh_ip, "secondary")
        set_button_role(self.btn_start_all, "primary")
        set_button_role(self.btn_stop_all, "danger")

        actions.addWidget(self.btn_refresh_ip)
        actions.addStretch(1)
        actions.addWidget(self.btn_start_all)
        actions.addWidget(self.btn_stop_all)
        layout.addLayout(actions)

        self.btn_refresh_ip.clicked.connect(self.refresh_ip_requested)
        self.btn_start_all.clicked.connect(self.start_all_requested)
        self.btn_stop_all.clicked.connect(self.stop_all_requested)

    def set_any_running(self, any_on: bool) -> None:
        self.btn_start_all.setEnabled(not any_on)
        self.btn_stop_all.setEnabled(any_on)
