from PyQt5 import QtCore, QtWidgets

from ui.components.common import refresh_style, set_muted_label


class TelemetryPanel(QtWidgets.QFrame):
    """Shared telemetry settings model and Settings-tab editor."""

    settings_changed = QtCore.pyqtSignal()

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        self.config = config
        self._profile = "IVCAN"
        self._targets_enabled = {"Instructor": True, "Student": True}

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 22)
        root.setSpacing(14)

        title = QtWidgets.QLabel("Connection settings")
        title.setObjectName("settingsTitle")
        subtitle = QtWidgets.QLabel("Telemetry input, router, and optional outputs")
        set_muted_label(subtitle)
        root.addWidget(title)
        root.addWidget(subtitle)

        connection = QtWidgets.QFrame()
        connection.setObjectName("settingsSection")
        grid = QtWidgets.QGridLayout(connection)
        grid.setContentsMargins(16, 14, 16, 16)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.lbl_profile = QtWidgets.QLabel()
        self.lbl_endpoint = QtWidgets.QLabel()
        self.sp_listen_udp = QtWidgets.QSpinBox()
        self.sp_listen_udp.setRange(1, 65535)
        self.ed_tcp_ip = QtWidgets.QLineEdit()
        self.sp_tcp_port = QtWidgets.QSpinBox()
        self.sp_tcp_port.setRange(1, 65535)
        self.sp_tcp_server = QtWidgets.QSpinBox()
        self.sp_tcp_server.setRange(0, 65535)
        self.sp_tcp_server.setValue(5760)
        self.cb_primer = QtWidgets.QCheckBox("Enable UDP primer")
        self.ed_primer_ip = QtWidgets.QLineEdit()
        self.sp_primer_port = QtWidgets.QSpinBox()
        self.sp_primer_port.setRange(1, 65535)
        self.cb_sudo = QtWidgets.QCheckBox("Administrator")

        section_title = QtWidgets.QLabel("Router connection")
        section_title.setObjectName("sectionTitle")
        grid.addWidget(section_title, 0, 0, 1, 4)
        grid.addWidget(QtWidgets.QLabel("Selected profile"), 1, 0)
        grid.addWidget(self.lbl_profile, 1, 1, 1, 3)
        grid.addWidget(QtWidgets.QLabel("Effective input"), 2, 0)
        grid.addWidget(self.lbl_endpoint, 2, 1, 1, 3)
        grid.addWidget(QtWidgets.QLabel("UDP listen port"), 3, 0)
        grid.addWidget(self.sp_listen_udp, 3, 1)
        grid.addWidget(QtWidgets.QLabel("TCP upstream IP"), 4, 0)
        grid.addWidget(self.ed_tcp_ip, 4, 1, 1, 3)
        grid.addWidget(QtWidgets.QLabel("TCP upstream port"), 5, 0)
        grid.addWidget(self.sp_tcp_port, 5, 1)
        grid.addWidget(QtWidgets.QLabel("Local TCP server port"), 6, 0)
        grid.addWidget(self.sp_tcp_server, 6, 1)
        grid.addWidget(self.cb_primer, 7, 0, 1, 2)
        grid.addWidget(self.cb_sudo, 7, 2, 1, 2)
        grid.addWidget(QtWidgets.QLabel("Primer IP"), 8, 0)
        grid.addWidget(self.ed_primer_ip, 8, 1, 1, 3)
        grid.addWidget(QtWidgets.QLabel("Primer port"), 9, 0)
        grid.addWidget(self.sp_primer_port, 9, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        root.addWidget(connection)

        instrument = QtWidgets.QFrame()
        instrument.setObjectName("settingsSection")
        instrument_grid = QtWidgets.QGridLayout(instrument)
        instrument_grid.setContentsMargins(16, 14, 16, 16)
        instrument_title = QtWidgets.QLabel("Instrument Light")
        instrument_title.setObjectName("sectionTitle")
        self.cb_espusr_enable = QtWidgets.QCheckBox("Enable Instrument Light output")
        self.cb_espusr_mode = QtWidgets.QComboBox()
        self.cb_espusr_mode.addItems(["TCP", "UDP"])
        self.ed_espusr_ip = QtWidgets.QLineEdit("192.168.144.200")
        self.sp_espusr_port = QtWidgets.QSpinBox()
        self.sp_espusr_port.setRange(1, 65535)
        self.sp_espusr_port.setValue(14600)
        instrument_grid.addWidget(instrument_title, 0, 0, 1, 4)
        instrument_grid.addWidget(self.cb_espusr_enable, 1, 0, 1, 4)
        self.instrument_detail_labels = [
            QtWidgets.QLabel("Mode"),
            QtWidgets.QLabel("IP"),
            QtWidgets.QLabel("Port"),
        ]
        instrument_grid.addWidget(self.instrument_detail_labels[0], 2, 0)
        instrument_grid.addWidget(self.cb_espusr_mode, 2, 1)
        instrument_grid.addWidget(self.instrument_detail_labels[1], 3, 0)
        instrument_grid.addWidget(self.ed_espusr_ip, 3, 1, 1, 3)
        instrument_grid.addWidget(self.instrument_detail_labels[2], 4, 0)
        instrument_grid.addWidget(self.sp_espusr_port, 4, 1)
        instrument_grid.setColumnStretch(1, 1)
        root.addWidget(instrument)

        for widget in (
            self.sp_listen_udp,
            self.ed_tcp_ip,
            self.sp_tcp_port,
            self.sp_tcp_server,
            self.cb_primer,
            self.ed_primer_ip,
            self.sp_primer_port,
            self.cb_sudo,
            self.cb_espusr_enable,
            self.cb_espusr_mode,
            self.ed_espusr_ip,
            self.sp_espusr_port,
        ):
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self.settings_changed)
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(self.settings_changed)
            if hasattr(widget, "toggled"):
                widget.toggled.connect(self.settings_changed)
            if hasattr(widget, "currentTextChanged"):
                widget.currentTextChanged.connect(self.settings_changed)
        self.cb_espusr_enable.toggled.connect(self._sync_instrument_enabled)
        self.set_profile("IVCAN")
        self._sync_instrument_enabled(False)

    def profile_display_name(self) -> str:
        return "Omni Trainer" if self._profile == "IVCAN" else "Demonstrator"

    def selected_profile(self) -> str:
        return self._profile

    def set_profile(self, profile: str) -> None:
        if profile not in {"HM30", "IVCAN"}:
            return
        self._profile = profile
        preset = self.config.get("telemetry", {}).get("input_presets", {}).get(profile, {})
        widgets = (
            self.sp_listen_udp,
            self.ed_tcp_ip,
            self.sp_tcp_port,
            self.cb_primer,
            self.ed_primer_ip,
            self.sp_primer_port,
        )
        for widget in widgets:
            widget.blockSignals(True)
        self.sp_listen_udp.setValue(int(preset.get("listen_udp", 19856)))
        self.ed_tcp_ip.setText(str(preset.get("tcp_up_ip", "")))
        self.sp_tcp_port.setValue(max(1, int(preset.get("tcp_up_port", 1))))
        self.cb_primer.setChecked(bool(preset.get("primer_enabled", False)))
        self.ed_primer_ip.setText(str(preset.get("primer_ip", "")))
        self.sp_primer_port.setValue(max(1, int(preset.get("primer_port", 1))))
        for widget in widgets:
            widget.blockSignals(False)
        self.lbl_profile.setText(self.profile_display_name())
        self.lbl_endpoint.setText(self.effective_connection_summary())
        tcp = str(preset.get("mode", "UDP")).upper() == "TCP"
        self.ed_tcp_ip.setEnabled(tcp)
        self.sp_tcp_port.setEnabled(tcp)
        self.sp_listen_udp.setEnabled(not tcp)
        self.cb_primer.setEnabled(not tcp)
        self.ed_primer_ip.setEnabled(not tcp and self.cb_primer.isChecked())
        self.sp_primer_port.setEnabled(not tcp and self.cb_primer.isChecked())
        self.settings_changed.emit()

    def effective_connection_summary(self) -> str:
        preset = self.config.get("telemetry", {}).get("input_presets", {}).get(
            self._profile, {}
        )
        mode = str(preset.get("mode", "UDP")).upper()
        if mode == "TCP":
            return f"TCP · {self.ed_tcp_ip.text().strip()}:{int(self.sp_tcp_port.value())}"
        return f"UDP · 0.0.0.0:{int(self.sp_listen_udp.value())}"

    def set_target_enabled(self, name: str, enabled: bool) -> None:
        if name in self._targets_enabled:
            self._targets_enabled[name] = bool(enabled)
            self.settings_changed.emit()

    def target_enabled(self, name: str) -> bool:
        return self._targets_enabled.get(name, False)

    def generated_targets_text(self) -> str:
        telemetry = self.config.get("telemetry", {})
        targets = telemetry.get("targets", {})
        port = int(telemetry.get("default_target_port", 14550))
        return "\n".join(
            f"{targets[name]}:{port}"
            for name in ("Instructor", "Student")
            if self.target_enabled(name) and name in targets
        )

    def get_router_options(self) -> dict:
        preset = self.config.get("telemetry", {}).get("input_presets", {}).get(
            self._profile, {}
        )
        return {
            "in_mode": str(preset.get("mode", "UDP")),
            "listen_udp_port": int(self.sp_listen_udp.value()),
            "tcp_up_ip": self.ed_tcp_ip.text().strip(),
            "tcp_up_port": int(self.sp_tcp_port.value()),
            "tcp_server_port_ui": int(self.sp_tcp_server.value()),
            "targets_text": self.generated_targets_text(),
            "primer_enabled": self.cb_primer.isChecked(),
            "primer_up_ip": self.ed_primer_ip.text().strip(),
            "primer_up_port": int(self.sp_primer_port.value()),
            "use_sudo": self.cb_sudo.isChecked(),
            "espusr_enabled": self.cb_espusr_enable.isChecked(),
            "espusr_mode": self.cb_espusr_mode.currentText().strip(),
            "espusr_ip": self.ed_espusr_ip.text().strip(),
            "espusr_port": int(self.sp_espusr_port.value()),
        }

    def _sync_instrument_enabled(self, enabled: bool) -> None:
        for widget in (
            self.cb_espusr_mode,
            self.ed_espusr_ip,
            self.sp_espusr_port,
            *self.instrument_detail_labels,
        ):
            widget.setEnabled(enabled)
            widget.setVisible(enabled)


class TelemetryOperatePanel(QtWidgets.QFrame):
    settings_requested = QtCore.pyqtSignal()
    targets_copy_requested = QtCore.pyqtSignal(str)
    target_toggled = QtCore.pyqtSignal(str, bool)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("operatePanel")
        self.config = config
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        root.setSpacing(0)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Telemetry")
        title.setObjectName("panelTitle")
        self.lbl_profile = QtWidgets.QLabel("Omni Trainer")
        self.lbl_profile.setObjectName("sourceName")
        self.lbl_status = QtWidgets.QLabel("Stopped")
        self.lbl_status.setObjectName("panelStatus")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.lbl_status)
        root.addLayout(header)
        root.addSpacing(8)
        root.addWidget(self.lbl_profile)
        self.lbl_connection = QtWidgets.QLabel()
        set_muted_label(self.lbl_connection)
        root.addWidget(self.lbl_connection)
        root.addSpacing(8)
        root.addWidget(self._separator())

        targets = config.get("telemetry", {}).get("targets", {})
        port = int(config.get("telemetry", {}).get("default_target_port", 14550))
        self.target_checkboxes = {}
        for name in ("Instructor", "Student"):
            row = QtWidgets.QFrame()
            row.setObjectName("operateListRow")
            row.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            row.setMinimumHeight(54)
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(2, 7, 2, 7)
            layout.setSpacing(24)
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(True)
            target_widget = QtWidgets.QWidget()
            target_widget.setFixedHeight(62)
            target_text = QtWidgets.QVBoxLayout(target_widget)
            target_text.setContentsMargins(0, 0, 0, 0)
            target_text.setSpacing(1)
            name_label = QtWidgets.QLabel(name)
            name_label.setObjectName("sourceName")
            address = QtWidgets.QLabel(str(targets.get(name, "N/A")))
            address.setObjectName("targetAddress")
            layout.addWidget(checkbox)
            target_text.addWidget(name_label)
            target_text.addWidget(address)
            layout.addWidget(target_widget, 1, QtCore.Qt.AlignVCenter)
            root.addWidget(row)
            if name == "Instructor":
                root.addWidget(self._separator())
            self.target_checkboxes[name] = checkbox
            checkbox.toggled.connect(
                lambda enabled, target=name: self.target_toggled.emit(target, enabled)
            )

        footer = QtWidgets.QHBoxLayout()
        settings = QtWidgets.QToolButton()
        settings.setText("Connection settings  →")
        copy = QtWidgets.QToolButton()
        copy.setText("Copy targets")
        settings.setProperty("role", "link")
        copy.setProperty("role", "link")
        footer.addWidget(settings)
        footer.addStretch(1)
        footer.addWidget(copy)
        root.addLayout(footer)
        settings.clicked.connect(self.settings_requested)
        copy.clicked.connect(self._copy_targets)

    @staticmethod
    def _separator() -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setObjectName("operateSeparator")
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFixedHeight(1)
        return line

    def sync_from_settings(self, settings: TelemetryPanel) -> None:
        self.lbl_profile.setText(settings.profile_display_name())
        mode = settings.effective_connection_summary().partition("·")[0].strip()
        self.lbl_connection.setText(f"{mode} connection")
        for name, checkbox in self.target_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(settings.target_enabled(name))
            checkbox.blockSignals(False)

    def set_service_state(self, state: str) -> None:
        self.lbl_status.setText(state.title())
        self.lbl_status.setProperty("serviceState", state)
        refresh_style(self.lbl_status)

    def _copy_targets(self) -> None:
        targets = self.config.get("telemetry", {}).get("targets", {})
        port = int(self.config.get("telemetry", {}).get("default_target_port", 14550))
        text = "\n".join(
            f"{targets[name]}:{port}"
            for name, checkbox in self.target_checkboxes.items()
            if checkbox.isChecked() and name in targets
        )
        self.targets_copy_requested.emit(text)
