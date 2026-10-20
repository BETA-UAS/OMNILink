from PyQt5 import QtCore, QtWidgets

from ui.components.common import set_button_role, set_field_value_label, set_muted_label


class VideoSettingsPanel(QtWidgets.QFrame):
    settings_changed = QtCore.pyqtSignal()

    def __init__(self, config: dict, output_ip: str, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        self.config = config
        self._output_ip = output_ip

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 22)
        root.setSpacing(14)
        title = QtWidgets.QLabel("Video settings")
        title.setObjectName("settingsTitle")
        subtitle = QtWidgets.QLabel("RTSP output and camera encoding")
        set_muted_label(subtitle)
        root.addWidget(title)
        root.addWidget(subtitle)

        output = QtWidgets.QFrame()
        output.setObjectName("settingsSection")
        output_grid = QtWidgets.QGridLayout(output)
        output_grid.setContentsMargins(16, 14, 16, 16)
        output_grid.setHorizontalSpacing(14)
        output_grid.setVerticalSpacing(11)
        output_title = QtWidgets.QLabel("Output")
        output_title.setObjectName("sectionTitle")
        self.lbl_interface = QtWidgets.QLabel(output_ip)
        set_field_value_label(self.lbl_interface)
        self.sp_rtsp_port = QtWidgets.QSpinBox()
        self.sp_rtsp_port.setRange(1, 65535)
        self.sp_rtsp_port.setValue(int(config.get("video", {}).get("rtsp_port", 8554)))
        self.lbl_base = QtWidgets.QLabel()
        set_muted_label(self.lbl_base)
        copy = QtWidgets.QPushButton("Copy RTSP base")
        set_button_role(copy, "secondary")
        copy.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(self.video_base_url())
        )
        output_grid.addWidget(output_title, 0, 0, 1, 3)
        output_grid.addWidget(QtWidgets.QLabel("Interface / output IP"), 1, 0)
        output_grid.addWidget(self.lbl_interface, 1, 1, 1, 2)
        output_grid.addWidget(QtWidgets.QLabel("RTSP port"), 2, 0)
        output_grid.addWidget(self.sp_rtsp_port, 2, 1)
        output_grid.addWidget(copy, 2, 2)
        output_grid.addWidget(self.lbl_base, 3, 0, 1, 3)
        output_grid.setColumnStretch(1, 1)
        root.addWidget(output)

        encoding = QtWidgets.QFrame()
        encoding.setObjectName("settingsSection")
        encoding_grid = QtWidgets.QGridLayout(encoding)
        encoding_grid.setContentsMargins(16, 14, 16, 16)
        encoding_grid.setHorizontalSpacing(14)
        encoding_grid.setVerticalSpacing(11)
        encoding_title = QtWidgets.QLabel("Encoding")
        encoding_title.setObjectName("sectionTitle")
        self.ed_mediamtx = QtWidgets.QLineEdit(
            config.get("mediamtx_bin_default", "/usr/local/bin/mediamtx")
        )
        self.sp_bitrate = QtWidgets.QSpinBox()
        self.sp_bitrate.setRange(200, 20000)
        self.sp_bitrate.setValue(int(config.get("video", {}).get("bitrate_kbps", 2500)))
        self.cb_passthrough = QtWidgets.QCheckBox("Use RTSP stream passthrough")
        self.cb_passthrough.setChecked(
            bool(config.get("video", {}).get("passthrough", False))
        )
        passthrough_help = QtWidgets.QLabel(
            "Passthrough preserves the camera's original codec and bitrate. "
            "Transcoding remains the default."
        )
        passthrough_help.setWordWrap(True)
        set_muted_label(passthrough_help)
        encoding_grid.addWidget(encoding_title, 0, 0, 1, 2)
        encoding_grid.addWidget(QtWidgets.QLabel("MediaMTX binary"), 1, 0)
        encoding_grid.addWidget(self.ed_mediamtx, 1, 1)
        encoding_grid.addWidget(QtWidgets.QLabel("Transcode bitrate (kbps)"), 2, 0)
        encoding_grid.addWidget(self.sp_bitrate, 2, 1)
        encoding_grid.addWidget(self.cb_passthrough, 3, 0, 1, 2)
        encoding_grid.addWidget(passthrough_help, 4, 0, 1, 2)
        encoding_grid.setColumnStretch(1, 1)
        root.addWidget(encoding)

        self.sp_rtsp_port.valueChanged.connect(self._changed)
        self.sp_bitrate.valueChanged.connect(self.settings_changed)
        self.ed_mediamtx.textChanged.connect(self.settings_changed)
        self.cb_passthrough.toggled.connect(self.settings_changed)
        self._update_base()

    def _changed(self) -> None:
        self._update_base()
        self.settings_changed.emit()

    def _update_base(self) -> None:
        self.lbl_base.setText(f"RTSP base · {self.video_base_url()}")

    def set_output_ip(self, output_ip: str) -> None:
        self._output_ip = output_ip
        self.lbl_interface.setText(output_ip)
        self._update_base()
        self.settings_changed.emit()

    def video_base_url(self) -> str:
        return f"rtsp://{self._output_ip}:{int(self.sp_rtsp_port.value())}/"

    def get_video_options(self) -> dict:
        return {
            "mediamtx_bin": self.ed_mediamtx.text().strip()
            or self.config.get("mediamtx_bin_default", "/usr/local/bin/mediamtx"),
            "out_port": int(self.sp_rtsp_port.value()),
            "global_bitrate_kbps": int(self.sp_bitrate.value()),
            "passthrough": self.cb_passthrough.isChecked(),
        }
