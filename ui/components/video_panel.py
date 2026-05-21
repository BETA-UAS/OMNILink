from typing import List

from core.config_models import VideoSource
from core.video_config import FPS_CHOICES, RES_CHOICES, VIDEO_TYPE_RTSP
from PyQt5 import QtCore, QtWidgets
from ui.components.common import (
    set_button_role,
    set_field_value_label,
    set_muted_label,
    set_status_label,
)

DEFAULT_MANUAL_CAMERA_ADDRESS = "rtsp://192.168.144.25:8554/main.264"


class VideoPanel(QtWidgets.QWidget):
    start_requested = QtCore.pyqtSignal()
    stop_requested = QtCore.pyqtSignal()
    settings_changed = QtCore.pyqtSignal()
    refresh_ip_requested = QtCore.pyqtSignal()

    def __init__(self, config: dict, output_ip: str, parent=None):
        super().__init__(parent)
        self.config = config
        self._out_ip = output_ip

        self.root_layout = QtWidgets.QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(10)

        self._build_output_section()
        self._build_sources_section()
        self._build_controls()
        self._build_settings_section()
        self.root_layout.addStretch(1)

        self.add_fixed_camera_row(True, "Main Camera", "rtsp://192.168.144.25:554", "cam1")
        self.add_fixed_camera_row(True, "Tail Camera", "rtsp://192.168.144.26:554", "cam2")
        self._update_video_table_height()
        self._update_video_base_hint()

    def _build_output_section(self) -> None:
        gb_out = QtWidgets.QGroupBox("Video Output")
        self.root_layout.addWidget(gb_out)
        og = QtWidgets.QGridLayout(gb_out)
        og.setContentsMargins(14, 12, 14, 12)
        og.setHorizontalSpacing(12)
        og.setVerticalSpacing(9)

        self.lbl_out_ip = QtWidgets.QLabel(self._out_ip)
        set_field_value_label(self.lbl_out_ip)

        btn_copy_ip = QtWidgets.QPushButton("Copy IP")
        set_button_role(btn_copy_ip, "secondary")
        btn_copy_ip.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(self._out_ip)
        )

        self.sp_rtsp_port = QtWidgets.QSpinBox()
        self.sp_rtsp_port.setRange(1, 65535)
        self.sp_rtsp_port.setValue(8554)

        self.lbl_out_hint = QtWidgets.QLabel("RTSP Base: -")
        set_muted_label(self.lbl_out_hint)

        btn_copy_base = QtWidgets.QPushButton("Copy Base")
        set_button_role(btn_copy_base, "secondary")
        btn_copy_base.clicked.connect(self.copy_video_base)

        og.addWidget(QtWidgets.QLabel("Ethernet Output IP"), 0, 0)
        og.addWidget(self.lbl_out_ip, 0, 1)
        og.addWidget(btn_copy_ip, 0, 2)
        og.addWidget(QtWidgets.QLabel("RTSP Port"), 1, 0)
        og.addWidget(self.sp_rtsp_port, 1, 1)
        og.addWidget(btn_copy_base, 1, 2)
        og.addWidget(self.lbl_out_hint, 2, 0, 1, 3)
        og.setColumnStretch(1, 1)
        og.setColumnStretch(2, 0)

        self.sp_rtsp_port.valueChanged.connect(lambda _v: self._update_video_base_hint())
        self.sp_rtsp_port.valueChanged.connect(lambda _v: self.settings_changed.emit())

    def _build_sources_section(self) -> None:
        gb_sources = QtWidgets.QGroupBox("Video Sources")
        gb_sources.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        self.root_layout.addWidget(gb_sources)

        sg = QtWidgets.QVBoxLayout(gb_sources)
        sg.setContentsMargins(14, 12, 14, 12)
        sg.setSpacing(8)

        self.tbl = QtWidgets.QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["On", "Camera", "Address", "Path"])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setShowGrid(False)
        self.tbl.setWordWrap(False)
        self.tbl.setTextElideMode(QtCore.Qt.ElideRight)
        self.tbl.verticalHeader().setDefaultSectionSize(40)
        self.tbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sg.addWidget(self.tbl, 0)

        hdr = self.tbl.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        self.tbl.setColumnWidth(0, 52)
        self.tbl.setColumnHidden(2, True)
        self.tbl.setColumnHidden(3, True)

        manual_box = QtWidgets.QFrame()
        manual_box.setObjectName("compactPanel")
        manual_box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        manual_lay = QtWidgets.QVBoxLayout(manual_box)
        manual_lay.setContentsMargins(10, 8, 10, 8)
        manual_lay.setSpacing(6)

        self.cb_manual_cam = QtWidgets.QCheckBox("Enable Manual Camera Address")
        self.ed_manual_cam = QtWidgets.QLineEdit(DEFAULT_MANUAL_CAMERA_ADDRESS)
        self.ed_manual_cam.setPlaceholderText(DEFAULT_MANUAL_CAMERA_ADDRESS)
        self.ed_manual_cam.setEnabled(False)
        manual_lay.addWidget(self.cb_manual_cam)
        manual_lay.addWidget(self.ed_manual_cam)
        sg.addWidget(manual_box, 0)

        self.cb_manual_cam.toggled.connect(self._set_manual_camera_enabled)
        self.cb_manual_cam.toggled.connect(lambda _checked: self.settings_changed.emit())
        self.ed_manual_cam.textChanged.connect(lambda _text: self.settings_changed.emit())

    def _build_controls(self) -> None:
        video_bottom = QtWidgets.QVBoxLayout()
        video_bottom.setSpacing(8)

        self.btn_toggle_vsettings = QtWidgets.QToolButton()
        self.btn_toggle_vsettings.setText("Show Video Settings")
        self.btn_toggle_vsettings.setCheckable(True)
        self.btn_toggle_vsettings.setChecked(False)
        set_button_role(self.btn_toggle_vsettings, "toggle")

        self.btn_video_start = QtWidgets.QPushButton("Start Video")
        self.btn_video_stop = QtWidgets.QPushButton("Stop Video")
        self.btn_video_stop.setEnabled(False)
        set_button_role(self.btn_video_start, "primary")
        set_button_role(self.btn_video_stop, "danger")

        self.lbl_video = QtWidgets.QLabel("STOPPED")
        set_status_label(self.lbl_video, "STOPPED", False)

        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(self.btn_toggle_vsettings)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_video_start)
        action_row.addWidget(self.btn_video_stop)

        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addStretch(1)
        status_row.addWidget(QtWidgets.QLabel("Status"))
        status_row.addWidget(self.lbl_video)

        video_bottom.addLayout(action_row)
        video_bottom.addLayout(status_row)
        self.root_layout.addLayout(video_bottom)

        self.btn_toggle_vsettings.clicked.connect(self._toggle_video_settings)
        self.btn_video_start.clicked.connect(self.start_requested)
        self.btn_video_stop.clicked.connect(self.stop_requested)

    def _build_settings_section(self) -> None:
        self.gb_vctl = QtWidgets.QGroupBox("Video Settings")
        self.root_layout.addWidget(self.gb_vctl)
        vg = QtWidgets.QGridLayout(self.gb_vctl)
        vg.setContentsMargins(14, 12, 14, 12)
        vg.setHorizontalSpacing(12)
        vg.setVerticalSpacing(9)

        self.ed_mediamtx = QtWidgets.QLineEdit(
            self.config.get("mediamtx_bin_default", "/usr/local/bin/mediamtx")
        )
        self.sp_bitrate = QtWidgets.QSpinBox()
        self.sp_bitrate.setRange(200, 20000)
        self.sp_bitrate.setValue(2500)

        self.cb_res = QtWidgets.QComboBox()
        self.cb_res.addItems(RES_CHOICES)
        self.cb_res.setCurrentText("1280x720")

        self.cb_fps = QtWidgets.QComboBox()
        self.cb_fps.addItems(FPS_CHOICES)
        self.cb_fps.setCurrentText("30")

        vg.addWidget(QtWidgets.QLabel("mediamtx"), 0, 0)
        vg.addWidget(self.ed_mediamtx, 0, 1, 1, 3)
        vg.addWidget(QtWidgets.QLabel("Bitrate (kbps)"), 1, 0)
        vg.addWidget(self.sp_bitrate, 1, 1)
        vg.addWidget(QtWidgets.QLabel("Webcam Res"), 1, 2)
        vg.addWidget(self.cb_res, 1, 3)
        vg.addWidget(QtWidgets.QLabel("Webcam FPS"), 2, 0)
        vg.addWidget(self.cb_fps, 2, 1)

        self.gb_vctl.setVisible(False)

    def set_output_ip(self, output_ip: str) -> None:
        self._out_ip = output_ip
        self.lbl_out_ip.setText(self._out_ip)
        self._update_video_base_hint()

    def copy_video_base(self) -> None:
        QtWidgets.QApplication.clipboard().setText(self.video_base_url())

    def video_base_url(self) -> str:
        return f"rtsp://{self._out_ip}:{int(self.sp_rtsp_port.value())}/"

    def get_video_options(self) -> dict:
        return {
            "mediamtx_bin": self.ed_mediamtx.text().strip()
            or self.config.get("mediamtx_bin_default", "/usr/local/bin/mediamtx"),
            "out_port": int(self.sp_rtsp_port.value()),
            "global_bitrate_kbps": int(self.sp_bitrate.value()),
            "webcam_res": self.cb_res.currentText().strip(),
            "webcam_fps": int(self.cb_fps.currentText().strip()),
        }

    def get_sources(self) -> List[VideoSource]:
        out: List[VideoSource] = []
        for r in range(self.tbl.rowCount()):
            enabled = True
            w0 = self.tbl.cellWidget(r, 0)
            if w0:
                cbx = w0.findChild(QtWidgets.QCheckBox)
                if cbx:
                    enabled = cbx.isChecked()

            addr = self.tbl.item(r, 2).text().strip() if self.tbl.item(r, 2) else ""
            path = self.tbl.item(r, 3).text().strip().lstrip("/") if self.tbl.item(r, 3) else ""
            if addr and path:
                out.append(
                    VideoSource(
                        enabled=enabled, vtype=VIDEO_TYPE_RTSP, input_text=addr, out_path=path
                    )
                )

        if self.cb_manual_cam.isChecked():
            addr = self.ed_manual_cam.text().strip()
            out.append(
                VideoSource(enabled=True, vtype=VIDEO_TYPE_RTSP, input_text=addr, out_path="cam3")
            )

        return out

    def set_running(self, running: bool) -> None:
        set_status_label(self.lbl_video, "RUNNING" if running else "STOPPED", running)
        self.btn_video_start.setEnabled(not running)
        self.btn_video_stop.setEnabled(running)

    def add_fixed_camera_row(
        self, enabled: bool, display_name: str, address: str, out_path: str
    ) -> None:
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)

        chk = QtWidgets.QCheckBox()
        chk.setObjectName("videoSourceToggle")
        chk.setChecked(bool(enabled))
        w = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(chk)
        self.tbl.setCellWidget(r, 0, w)

        self.tbl.setItem(r, 1, QtWidgets.QTableWidgetItem(display_name))
        self.tbl.setItem(r, 2, QtWidgets.QTableWidgetItem(address))
        self.tbl.setItem(r, 3, QtWidgets.QTableWidgetItem(out_path))

        self._update_video_table_height()

    def _toggle_video_settings(self) -> None:
        on = self.btn_toggle_vsettings.isChecked()
        self.gb_vctl.setVisible(on)
        self.btn_toggle_vsettings.setText("Hide Video Settings" if on else "Show Video Settings")

    def _set_manual_camera_enabled(self, enabled: bool) -> None:
        self.ed_manual_cam.setEnabled(enabled)

    def _update_video_base_hint(self) -> None:
        self.lbl_out_hint.setText(f"RTSP Base: {self.video_base_url()}")

    def _update_video_table_height(self) -> None:
        header_h = self.tbl.horizontalHeader().height()
        row_h_total = sum(self.tbl.rowHeight(r) for r in range(self.tbl.rowCount()))

        frame = self.tbl.frameWidth() * 2
        extra = 6

        desired = header_h + row_h_total + frame + extra
        min_h = header_h + 3 * self.tbl.verticalHeader().defaultSectionSize() + frame + extra
        max_h = header_h + 8 * self.tbl.verticalHeader().defaultSectionSize() + frame + extra

        desired = max(min_h, min(desired, max_h))

        self.tbl.setMinimumHeight(min(desired, min_h))
        self.tbl.setMaximumHeight(desired)
