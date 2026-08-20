from PyQt5 import QtCore, QtWidgets
from ui.components.common import set_button_role


class TelemetryPanel(QtWidgets.QGroupBox):
    targets_copy_requested = QtCore.pyqtSignal(str)
    settings_changed = QtCore.pyqtSignal()

    def __init__(self, config: dict, parent=None):
        super().__init__("Telemetry Router", parent)
        self.config = config
        self._targets_generated = ""

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        self._build_presets(layout)
        self._build_targets(layout)
        self._build_instrument_light(layout)
        self._build_manual_advanced(layout)
        self._setup_connections()

        self._sync_espusr_ui()
        self._sync_targets_from_checkboxes()
        self._apply_tel_profile_ui()

    def _build_presets(self, layout: QtWidgets.QGridLayout) -> None:
        self.rb_hm30 = QtWidgets.QRadioButton("Demonstrator")
        self.rb_ivcan = QtWidgets.QRadioButton("Omni Trainer")
        self.rb_manual = QtWidgets.QRadioButton("Manual")
        self.rb_ivcan.setChecked(True)
        self.rb_hm30.setVisible(True)
        self.rb_manual.setVisible(False)

        preset_box = QtWidgets.QGroupBox("Input Preset")
        preset_box.setObjectName("innerPanel")
        pv = QtWidgets.QHBoxLayout(preset_box)
        pv.setContentsMargins(12, 10, 12, 10)
        pv.setSpacing(12)
        pv.addWidget(self.rb_hm30)
        pv.addWidget(self.rb_ivcan)
        pv.addWidget(self.rb_manual)
        pv.addStretch(1)
        layout.addWidget(preset_box, 0, 0, 1, 4)

    def _build_targets(self, layout: QtWidgets.QGridLayout) -> None:
        targets_box = QtWidgets.QGroupBox("Targets / Client")
        targets_box.setObjectName("innerPanel")
        tv = QtWidgets.QGridLayout(targets_box)
        tv.setContentsMargins(12, 10, 12, 10)
        tv.setHorizontalSpacing(12)
        tv.setVerticalSpacing(8)

        targets_cfg = self.config.get("telemetry", {}).get("targets", {})

        self.cb_t_pc1 = QtWidgets.QCheckBox(f"Instructor ({targets_cfg.get('Instructor', 'N/A')})")
        self.cb_t_pc2 = QtWidgets.QCheckBox(f"Student ({targets_cfg.get('Student', 'N/A')})")
        self.cb_t_pc1.setChecked(True)
        self.cb_t_pc2.setChecked(True)

        self.sp_target_port = QtWidgets.QSpinBox()
        self.sp_target_port.setRange(1, 65535)
        self.sp_target_port.setValue(
            self.config.get("telemetry", {}).get("default_target_port", 14550)
        )

        self.btn_copy_targets = QtWidgets.QPushButton("Copy Targets")
        set_button_role(self.btn_copy_targets, "secondary")

        tv.addWidget(self.cb_t_pc1, 0, 0, 1, 2)
        tv.addWidget(self.cb_t_pc2, 0, 2, 1, 2)
        tv.addWidget(QtWidgets.QLabel("Port"), 1, 0)
        tv.addWidget(self.sp_target_port, 1, 1)
        tv.addWidget(self.btn_copy_targets, 1, 2, 1, 2)
        tv.setColumnStretch(3, 1)
        layout.addWidget(targets_box, 1, 0, 1, 4)

    def _build_instrument_light(self, layout: QtWidgets.QGridLayout) -> None:
        tap_box = QtWidgets.QGroupBox("Instrument Light")
        tap_box.setObjectName("innerPanel")
        tapg = QtWidgets.QGridLayout(tap_box)
        tapg.setContentsMargins(12, 10, 12, 10)
        tapg.setHorizontalSpacing(12)
        tapg.setVerticalSpacing(8)

        self.cb_espusr_enable = QtWidgets.QCheckBox("Enable")
        self.cb_espusr_enable.setChecked(False)

        self.cb_espusr_mode = QtWidgets.QComboBox()
        self.cb_espusr_mode.addItems(["TCP", "UDP"])
        self.cb_espusr_mode.setCurrentText("TCP")

        self.ed_espusr_ip = QtWidgets.QLineEdit("192.168.144.200")
        self.sp_espusr_port = QtWidgets.QSpinBox()
        self.sp_espusr_port.setRange(1, 65535)
        self.sp_espusr_port.setValue(14600)

        tapg.addWidget(self.cb_espusr_enable, 0, 0, 1, 4)
        tapg.addWidget(QtWidgets.QLabel("Mode"), 1, 0)
        tapg.addWidget(self.cb_espusr_mode, 1, 1)
        tapg.addWidget(QtWidgets.QLabel("Port"), 1, 2)
        tapg.addWidget(self.sp_espusr_port, 1, 3)
        tapg.addWidget(QtWidgets.QLabel("IP"), 2, 0)
        tapg.addWidget(self.ed_espusr_ip, 2, 1, 1, 3)
        tapg.setColumnStretch(1, 1)
        layout.addWidget(tap_box, 2, 0, 1, 4)

    def _build_manual_advanced(self, layout: QtWidgets.QGridLayout) -> None:
        self.manual_box = QtWidgets.QGroupBox("Manual Advanced")
        self.manual_box.setObjectName("innerPanel")
        mv = QtWidgets.QGridLayout(self.manual_box)
        mv.setContentsMargins(12, 10, 12, 10)
        mv.setHorizontalSpacing(12)
        mv.setVerticalSpacing(8)

        self.rb_m_udp = QtWidgets.QRadioButton("UDP")
        self.rb_m_tcp = QtWidgets.QRadioButton("TCP")
        self.rb_m_udp.setChecked(True)

        mode_row = QtWidgets.QHBoxLayout()
        mode_row.setSpacing(10)
        mode_row.addWidget(self.rb_m_udp)
        mode_row.addWidget(self.rb_m_tcp)
        mode_row.addStretch(1)
        w_mode = QtWidgets.QWidget()
        w_mode.setLayout(mode_row)

        self.sp_listen_udp = QtWidgets.QSpinBox()
        self.sp_listen_udp.setRange(1, 65535)
        self.sp_listen_udp.setValue(19856)

        self.ed_tcp_ip = QtWidgets.QLineEdit("192.168.144.11")
        self.sp_tcp_port = QtWidgets.QSpinBox()
        self.sp_tcp_port.setRange(1, 65535)
        self.sp_tcp_port.setValue(20001)

        self.sp_tcp_server = QtWidgets.QSpinBox()
        self.sp_tcp_server.setRange(0, 65535)
        self.sp_tcp_server.setValue(5760)

        self.cb_primer = QtWidgets.QCheckBox("Primer (UDP only)")
        self.cb_primer.setChecked(True)

        self.ed_primer_ip = QtWidgets.QLineEdit("192.168.144.12")
        self.sp_primer_port = QtWidgets.QSpinBox()
        self.sp_primer_port.setRange(1, 65535)
        self.sp_primer_port.setValue(19856)

        self.cb_sudo = QtWidgets.QCheckBox("Administrator")
        self.cb_sudo.setChecked(False)

        self.txt_targets = QtWidgets.QPlainTextEdit()
        self.txt_targets.setPlaceholderText("Targets, one per line: IP:PORT")
        self.txt_targets.setMinimumHeight(100)
        self.txt_targets.setMaximumHeight(140)

        mv.addWidget(QtWidgets.QLabel("Input Mode"), 0, 0)
        mv.addWidget(w_mode, 0, 1, 1, 3)
        mv.addWidget(QtWidgets.QLabel("Listen UDP"), 1, 0)
        mv.addWidget(self.sp_listen_udp, 1, 1)
        mv.addWidget(QtWidgets.QLabel("TCP Server Port"), 2, 0)
        mv.addWidget(self.sp_tcp_server, 2, 1)
        mv.addWidget(QtWidgets.QLabel("TCP Upstream IP"), 3, 0)
        mv.addWidget(self.ed_tcp_ip, 3, 1, 1, 3)
        mv.addWidget(QtWidgets.QLabel("TCP Port"), 4, 0)
        mv.addWidget(self.sp_tcp_port, 4, 1)
        mv.addWidget(self.cb_primer, 5, 0, 1, 2)
        mv.addWidget(self.cb_sudo, 5, 2, 1, 2)
        mv.addWidget(QtWidgets.QLabel("Primer Upstream IP"), 6, 0)
        mv.addWidget(self.ed_primer_ip, 6, 1, 1, 3)
        mv.addWidget(QtWidgets.QLabel("Primer Port"), 7, 0)
        mv.addWidget(self.sp_primer_port, 7, 1)
        mv.addWidget(QtWidgets.QLabel("Targets (Manual)"), 8, 0, 1, 4)
        mv.addWidget(self.txt_targets, 9, 0, 1, 4)
        mv.setColumnStretch(1, 1)
        mv.setColumnStretch(3, 1)

        layout.addWidget(self.manual_box, 3, 0, 1, 4)
        self.manual_box.setVisible(False)

    def _setup_connections(self) -> None:
        self.rb_hm30.toggled.connect(self._apply_tel_profile_ui)
        self.rb_ivcan.toggled.connect(self._apply_tel_profile_ui)
        self.rb_manual.toggled.connect(self._apply_tel_profile_ui)

        self.cb_t_pc1.toggled.connect(self._sync_targets_from_checkboxes)
        self.cb_t_pc2.toggled.connect(self._sync_targets_from_checkboxes)
        self.sp_target_port.valueChanged.connect(lambda _v: self._sync_targets_from_checkboxes())
        self.btn_copy_targets.clicked.connect(
            lambda: self.targets_copy_requested.emit(self.generated_targets_text())
        )

        self.rb_m_udp.toggled.connect(self._apply_manual_mode_ui)
        self.rb_m_tcp.toggled.connect(self._apply_manual_mode_ui)
        self.cb_espusr_enable.toggled.connect(self._sync_espusr_ui)

    def generated_targets_text(self) -> str:
        return (self._targets_generated or "").strip()

    def get_router_options(self) -> dict:
        prof = self.selected_profile()
        if prof == "MANUAL":
            in_mode = "UDP" if self.rb_m_udp.isChecked() else "TCP"
            targets_text = self.txt_targets.toPlainText().strip()
        else:
            presets = self.config.get("telemetry", {}).get("input_presets", {})
            in_mode = presets.get(prof, {}).get("mode", "UDP")
            targets_text = self.generated_targets_text()

        return {
            "in_mode": in_mode,
            "listen_udp_port": int(self.sp_listen_udp.value()),
            "tcp_up_ip": self.ed_tcp_ip.text().strip(),
            "tcp_up_port": int(self.sp_tcp_port.value()),
            "tcp_server_port_ui": int(self.sp_tcp_server.value()),
            "targets_text": targets_text,
            "primer_enabled": self.cb_primer.isChecked(),
            "primer_up_ip": self.ed_primer_ip.text().strip(),
            "primer_up_port": int(self.sp_primer_port.value()),
            "use_sudo": self.cb_sudo.isChecked(),
            "espusr_enabled": self.cb_espusr_enable.isChecked(),
            "espusr_mode": self.cb_espusr_mode.currentText().strip(),
            "espusr_ip": self.ed_espusr_ip.text().strip(),
            "espusr_port": int(self.sp_espusr_port.value()),
        }

    def selected_profile(self) -> str:
        if self.rb_ivcan.isChecked():
            return "IVCAN"
        if self.rb_manual.isChecked():
            return "MANUAL"
        return "HM30"

    def _sync_targets_from_checkboxes(self) -> None:
        port = int(self.sp_target_port.value())
        targets_cfg = self.config.get("telemetry", {}).get("targets", {})

        lines = []
        if self.cb_t_pc1.isChecked() and "Instructor" in targets_cfg:
            lines.append(f"{targets_cfg['Instructor']}:{port}")
        if self.cb_t_pc2.isChecked() and "Student" in targets_cfg:
            lines.append(f"{targets_cfg['Student']}:{port}")

        txt = "\n".join(lines).strip()
        if not self.rb_manual.isChecked():
            self.txt_targets.blockSignals(True)
            self.txt_targets.setPlainText(txt if txt else "")
            self.txt_targets.blockSignals(False)

        self._targets_generated = txt
        self.settings_changed.emit()

    def _sync_espusr_ui(self) -> None:
        on = self.cb_espusr_enable.isChecked()
        self.cb_espusr_mode.setEnabled(on)
        self.ed_espusr_ip.setEnabled(on)
        self.sp_espusr_port.setEnabled(on)
        self.settings_changed.emit()

    def _apply_manual_mode_ui(self) -> None:
        udp = self.rb_m_udp.isChecked()
        self.sp_listen_udp.setEnabled(udp)
        self.cb_primer.setEnabled(udp)
        self.ed_primer_ip.setEnabled(udp)
        self.sp_primer_port.setEnabled(udp)
        self.ed_tcp_ip.setEnabled(not udp)
        self.sp_tcp_port.setEnabled(not udp)
        self.settings_changed.emit()

    def _apply_tel_profile_ui(self) -> None:
        prof = self.selected_profile()
        manual = prof == "MANUAL"

        self.manual_box.setVisible(manual)
        self.txt_targets.setReadOnly(not manual)

        presets = self.config.get("telemetry", {}).get("input_presets", {})
        if prof in presets:
            p = presets[prof]
            if p.get("mode") == "UDP":
                self.rb_m_udp.setChecked(True)
            else:
                self.rb_m_tcp.setChecked(True)

            self.sp_listen_udp.setValue(int(p.get("listen_udp", 19856)))
            self.cb_primer.setChecked(bool(p.get("primer_enabled", False)))
            self.ed_primer_ip.setText(str(p.get("primer_ip", "")))
            self.sp_primer_port.setValue(int(p.get("primer_port", 0)))

            if p.get("mode") == "TCP":
                self.ed_tcp_ip.setText(str(p.get("tcp_up_ip", "")))
                self.sp_tcp_port.setValue(int(p.get("tcp_up_port", 0)))

            self._apply_manual_mode_ui()

        self._sync_targets_from_checkboxes()
