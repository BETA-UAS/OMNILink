from datetime import datetime
from typing import Dict, List

from PyQt5 import QtCore, QtWidgets
from ui.components.common import (
    set_device_name_label,
    set_muted_label,
    set_status_card,
    set_status_dot,
)


class NetworkStatusPanel(QtWidgets.QFrame):
    refresh_requested = QtCore.pyqtSignal()

    def __init__(self, devices: List[Dict[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("operatePanel")
        self.devices = devices
        self.ping_labels = {}
        self.ping_texts = {}
        self.ping_cards_by_name = {}
        self.status_text_by_name = {}
        self.ping_cards = []
        self._status_cols = 0
        self._relayout_pending = False
        self._paused = False
        self._last_updated = None

        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 12)
        root.setSpacing(9)

        ping_top = QtWidgets.QHBoxLayout()
        ping_top.setSpacing(8)

        title = QtWidgets.QLabel("Network devices")
        title.setObjectName("networkTitle")
        self.lbl_ping_summary = QtWidgets.QLabel(
            f"●  0 / {len(self.devices)} online   |   Not checked"
        )
        set_muted_label(self.lbl_ping_summary)

        ping_top.addWidget(title)
        ping_top.addSpacing(12)
        ping_top.addWidget(self.lbl_ping_summary)
        ping_top.addStretch(1)
        root.addLayout(ping_top)

        self.pg_status = QtWidgets.QGridLayout()
        self.pg_status.setHorizontalSpacing(10)
        self.pg_status.setVerticalSpacing(8)
        self.pg_status.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self.pg_status)

        for dev in self.devices:
            self.ping_cards.append(self._build_status_dot(dev["name"], dev["ip"]))

        self.relayout_cards(force=True)

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
        if self.width() >= 900:
            return 3
        if self.width() >= 560:
            return 2
        return 1

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
        if self._paused:
            return
        if refreshing:
            self.lbl_ping_summary.setText("Checking devices…")

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        if paused:
            suffix = (
                f" · last updated {self._last_updated.strftime('%H:%M:%S')}"
                if self._last_updated
                else " · no previous results"
            )
            self.lbl_ping_summary.setText(f"Checks paused while a service is active{suffix}")

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
            state_text = self.status_text_by_name.get(name)
            if not lbl or not txt:
                continue

            if ok:
                connected += 1
                txt.setToolTip(f"{name} {ip} connected")
            else:
                txt.setToolTip(f"{name} {ip} disconnected")
            set_status_dot(lbl, ok)
            if state_text:
                state_text.setText("Online" if ok else "Offline")
                state_text.setProperty("state", "ok" if ok else "error")
                state_text.style().unpolish(state_text)
                state_text.style().polish(state_text)
            if card:
                set_status_card(card, ok)

        self._last_updated = datetime.now()
        self.lbl_ping_summary.setText(
            f"●  {connected} / {total} online   |   Checked {self._last_updated.strftime('%H:%M:%S')}"
        )

    def _build_status_dot(self, name: str, ip: str) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("statusCard")
        card.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        card.setMinimumHeight(48)
        card.setMaximumHeight(82)
        card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        set_status_card(card, state="unchecked")

        lay = QtWidgets.QHBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        dot = QtWidgets.QLabel("●")
        dot.setAlignment(QtCore.Qt.AlignCenter)
        dot.setFixedWidth(18)
        set_status_dot(dot, state="unchecked")

        text_box = QtWidgets.QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(0)

        display_name = {"Main-Cam": "Main Camera", "Tail-Cam": "Tail Camera"}.get(
            name, name
        )
        name_lbl = QtWidgets.QLabel(display_name)
        set_device_name_label(name_lbl)

        ip_lbl = QtWidgets.QLabel(ip)
        ip_lbl.setObjectName("deviceAddress")

        status_lbl = QtWidgets.QLabel("Not checked")
        status_lbl.setObjectName("networkState")
        status_lbl.setProperty("state", "unchecked")

        text_box.addWidget(name_lbl)
        text_box.addWidget(ip_lbl)
        lay.addWidget(dot)
        lay.addLayout(text_box, 1)
        lay.addWidget(status_lbl)

        self.ping_labels[name] = dot
        self.ping_texts[name] = name_lbl
        self.ping_cards_by_name[name] = card
        self.status_text_by_name[name] = status_lbl
        return card
