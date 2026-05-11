from typing import Dict, List

from PyQt5 import QtCore, QtWidgets
from ui.components.common import (
    set_button_role,
    set_device_name_label,
    set_muted_label,
    set_status_card,
    set_status_dot,
)


class NetworkStatusPanel(QtWidgets.QGroupBox):
    refresh_requested = QtCore.pyqtSignal()

    def __init__(self, devices: List[Dict[str, str]], parent=None):
        super().__init__("Network Status", parent)
        self.devices = devices
        self.ping_labels = {}
        self.ping_texts = {}
        self.ping_cards_by_name = {}
        self.ping_cards = []
        self._status_cols = 0
        self._relayout_pending = False

        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        ping_top = QtWidgets.QHBoxLayout()
        ping_top.setSpacing(8)

        self.lbl_ping_summary = QtWidgets.QLabel("Devices: -")
        set_muted_label(self.lbl_ping_summary)

        ping_top.addWidget(self.lbl_ping_summary)
        ping_top.addStretch(1)

        self.btn_ping_refresh = QtWidgets.QPushButton("Refresh")
        set_button_role(self.btn_ping_refresh, "secondary")
        ping_top.addWidget(self.btn_ping_refresh)
        root.addLayout(ping_top)

        self.pg_status = QtWidgets.QGridLayout()
        self.pg_status.setHorizontalSpacing(10)
        self.pg_status.setVerticalSpacing(8)
        self.pg_status.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self.pg_status)

        for dev in self.devices:
            self.ping_cards.append(self._build_status_dot(dev["name"], dev["ip"]))

        self.relayout_cards(force=True)
        self.btn_ping_refresh.clicked.connect(self.refresh_requested)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._queue_relayout_cards()

    def _queue_relayout_cards(self) -> None:
        cols = self._desired_columns()
        if cols == self._status_cols or self._relayout_pending:
            return

        self._relayout_pending = True
        QtCore.QTimer.singleShot(0, self.relayout_cards)

    def _desired_columns(self) -> int:
        return 2 if self.width() >= 450 else 1

    def relayout_cards(self, force: bool = False) -> None:
        self._relayout_pending = False
        cols = self._desired_columns()
        if not force and cols == self._status_cols:
            return

        self.setUpdatesEnabled(False)
        while self.pg_status.count():
            item = self.pg_status.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        for i, card in enumerate(self.ping_cards):
            row, col = divmod(i, cols)
            self.pg_status.addWidget(card, row, col)

        for c in range(cols):
            self.pg_status.setColumnStretch(c, 1)
        self._status_cols = cols
        self.setUpdatesEnabled(True)

    def set_refreshing(self, refreshing: bool) -> None:
        self.btn_ping_refresh.setEnabled(not refreshing)
        self.btn_ping_refresh.setText("Refreshing..." if refreshing else "Refresh")

    def apply_results(self, results: Dict[str, bool], devices: List[Dict[str, str]]) -> None:
        connected = 0
        total = len(devices)

        for dev in devices:
            name = dev["name"]
            ip = dev["ip"]
            ok = bool(results.get(name, False))

            lbl = self.ping_labels.get(name)
            txt = self.ping_texts.get(name)
            card = self.ping_cards_by_name.get(name)
            if not lbl or not txt:
                continue

            if ok:
                connected += 1
                txt.setToolTip(f"{name} {ip} connected")
            else:
                txt.setToolTip(f"{name} {ip} disconnected")
            set_status_dot(lbl, ok)
            if card:
                set_status_card(card, ok)

        self.lbl_ping_summary.setText(f"Devices online: {connected}/{total}")

    def _build_status_dot(self, name: str, ip: str) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("statusCard")
        card.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        card.setMinimumHeight(46)
        card.setMaximumHeight(46)
        card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        set_status_card(card, False)

        lay = QtWidgets.QHBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        dot = QtWidgets.QLabel("●")
        dot.setAlignment(QtCore.Qt.AlignCenter)
        dot.setFixedWidth(18)
        set_status_dot(dot, False)

        text_box = QtWidgets.QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(0)

        name_lbl = QtWidgets.QLabel(name)
        set_device_name_label(name_lbl)

        ip_lbl = QtWidgets.QLabel(ip)
        set_muted_label(ip_lbl)

        text_box.addWidget(name_lbl)
        text_box.addWidget(ip_lbl)
        lay.addWidget(dot)
        lay.addLayout(text_box, 1)

        self.ping_labels[name] = dot
        self.ping_texts[name] = name_lbl
        self.ping_cards_by_name[name] = card
        return card
