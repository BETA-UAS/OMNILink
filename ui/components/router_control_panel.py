from PyQt5 import QtCore, QtWidgets
from ui.components.common import set_button_role, set_muted_label, set_status_label


class RouterControlPanel(QtWidgets.QGroupBox):
    start_requested = QtCore.pyqtSignal()
    stop_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Router Control", parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.btn_router_start = QtWidgets.QPushButton("Start Router")
        self.btn_router_stop = QtWidgets.QPushButton("Stop Router")
        self.btn_router_stop.setEnabled(False)
        set_button_role(self.btn_router_start, "primary")
        set_button_role(self.btn_router_stop, "danger")

        self.lbl_router = QtWidgets.QLabel("STOPPED")
        set_status_label(self.lbl_router, "STOPPED", False)

        self.lbl_tcp_info = QtWidgets.QLabel("TCP Server: -")
        set_muted_label(self.lbl_tcp_info)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.btn_router_start)
        actions.addWidget(self.btn_router_stop)
        actions.addStretch(1)

        status = QtWidgets.QHBoxLayout()
        status.setSpacing(8)
        status.addWidget(QtWidgets.QLabel("Status"))
        status.addWidget(self.lbl_router)
        status.addStretch(1)

        layout.addLayout(actions)
        layout.addLayout(status)
        layout.addWidget(self.lbl_tcp_info)

        self.btn_router_start.clicked.connect(self.start_requested)
        self.btn_router_stop.clicked.connect(self.stop_requested)

    def set_running(self, running: bool, tcp_port: int = 0) -> None:
        set_status_label(self.lbl_router, "RUNNING" if running else "STOPPED", running)
        self.lbl_tcp_info.setText(
            f"TCP Server: 127.0.0.1:{tcp_port}" if running else "TCP Server: -"
        )
        self.btn_router_start.setEnabled(not running)
        self.btn_router_stop.setEnabled(running)
