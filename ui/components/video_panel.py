from typing import List

from core.config_models import VideoSource
from core.video_config import MAIN_CAMERA_URLS, VIDEO_TYPE_RTSP
from PyQt5 import QtCore, QtWidgets
from ui.components.common import refresh_style, set_button_role, set_muted_label

MAIN_CAMERA_URL = MAIN_CAMERA_URLS[0]
TAIL_CAMERA_URL = "rtsp://192.168.144.26:554/"
AUX_CAMERA_URL = "rtsp://192.168.144.25:8554/main.264"
AUX_CAMERA_HOSTS = ("192.168.144.25", "192.168.144.26")


def aux_camera_url(host: str) -> str:
    selected = host if host in AUX_CAMERA_HOSTS else AUX_CAMERA_HOSTS[0]
    return f"rtsp://{selected}:8554/main.264"


def migrated_aux_camera_host(config: dict) -> str:
    """Keep a saved .25/.26 Aux choice while rejecting arbitrary legacy URLs."""
    video = config.get("video", {})
    saved = video.get("sources", config.get("video_sources", {}))
    candidates = []
    if isinstance(saved, dict):
        aux = saved.get("cam3", saved.get("aux", {}))
        if isinstance(aux, dict):
            candidates.extend(aux.get(key) for key in ("input_text", "url", "source_url"))
        elif isinstance(aux, str):
            candidates.append(aux)
    candidates.extend(video.get(key) for key in ("aux_camera_url", "aux_source_url", "cam3_url"))
    for candidate in candidates:
        text = str(candidate or "")
        for host in AUX_CAMERA_HOSTS:
            if host in text:
                return host
    return AUX_CAMERA_HOSTS[0]


def migrated_camera_selections(config: dict) -> dict:
    """Read current selections and map a legacy third/manual source to Aux."""
    video = config.get("video", {})
    saved = video.get("sources", config.get("video_sources", {}))
    if not isinstance(saved, dict):
        saved = {}

    def selected(keys, default):
        for key in keys:
            value = saved.get(key)
            if isinstance(value, dict) and "enabled" in value:
                return bool(value["enabled"])
            if isinstance(value, bool):
                return value
            if key in video and isinstance(video[key], bool):
                return video[key]
            if key in config and isinstance(config[key], bool):
                return config[key]
        return default

    return {
        "cam1": selected(("cam1", "main", "main_enabled"), True),
        "cam2": selected(("cam2", "tail", "tail_enabled"), True),
        "cam3": selected(
            ("cam3", "aux", "manual", "manual_enabled", "manual_camera_enabled"), False
        ),
    }


class VideoPanel(QtWidgets.QFrame):
    settings_requested = QtCore.pyqtSignal()
    settings_changed = QtCore.pyqtSignal()

    SOURCES = (
        ("cam1", "Main Camera", MAIN_CAMERA_URL),
        ("cam2", "Tail Camera", TAIL_CAMERA_URL),
        ("cam3", "Aux Camera", AUX_CAMERA_URL),
    )

    def __init__(self, config: dict, output_ip: str, output_port: int = 8554, parent=None):
        super().__init__(parent)
        self.setObjectName("operatePanel")
        self._output_ip = output_ip
        self._output_port = int(output_port)
        self._source_rows = []
        selections = migrated_camera_selections(config)
        aux_host = migrated_aux_camera_host(config)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        root.setSpacing(0)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Video")
        title.setObjectName("panelTitle")
        self.lbl_status = QtWidgets.QLabel("Stopped")
        self.lbl_status.setObjectName("panelStatus")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.lbl_status)
        root.addLayout(header)
        root.addSpacing(12)
        root.addWidget(self._separator())

        self.sources_layout = QtWidgets.QVBoxLayout()
        self.sources_layout.setSpacing(0)
        root.addLayout(self.sources_layout)
        for index, (path, name, url) in enumerate(self.SOURCES):
            if path == "cam3":
                url = aux_camera_url(aux_host)
            self._add_source_row(selections[path], name, url, path)
            if index < len(self.SOURCES) - 1:
                self.sources_layout.addWidget(self._separator())

        footer = QtWidgets.QHBoxLayout()
        self.lbl_source_health = QtWidgets.QLabel("")
        set_muted_label(self.lbl_source_health)
        self.lbl_source_health.setVisible(False)
        self.btn_settings = QtWidgets.QToolButton()
        self.btn_settings.setText("Video settings  →")
        set_button_role(self.btn_settings, "link")
        footer.addWidget(self.btn_settings)
        footer.addStretch(1)
        footer.addWidget(self.lbl_source_health)
        root.addLayout(footer)
        self.btn_settings.clicked.connect(self.settings_requested)

    @staticmethod
    def _separator() -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setObjectName("operateSeparator")
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFixedHeight(1)
        return line

    def _add_source_row(self, enabled: bool, name: str, source_url: str, path: str) -> None:
        card = QtWidgets.QFrame()
        card.setObjectName("operateListRow")
        card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        card.setMinimumHeight(54)
        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(2, 7, 2, 7)
        layout.setSpacing(30)

        checkbox = QtWidgets.QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.setToolTip(f"Enable {name}")
        text_widget = QtWidgets.QWidget()
        text_widget.setFixedHeight(62)
        text = QtWidgets.QVBoxLayout(text_widget)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        name_label = QtWidgets.QLabel(name)
        name_label.setObjectName("sourceName")
        secondary = {"cam1": "Camera 1 · MT11 / Viewpro auto", "cam2": "Camera 2"}.get(
            path, source_url
        )
        url_label = QtWidgets.QLabel(secondary)
        url_label.setObjectName("sourceAddress")
        url_label.setToolTip("\n".join(MAIN_CAMERA_URLS) if path == "cam1" else source_url)
        url_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        text.addWidget(name_label)
        text.addWidget(url_label)

        copy = QtWidgets.QPushButton("Copy URL")
        copy.setFixedWidth(128)
        set_button_role(copy, "secondary")
        copy.clicked.connect(
            lambda _checked=False, output_path=path: QtWidgets.QApplication.clipboard().setText(
                self.output_url(output_path)
            )
        )
        layout.addWidget(checkbox)
        layout.addWidget(text_widget, 1, QtCore.Qt.AlignVCenter)
        source_selector = None
        if path == "cam3":
            source_selector = QtWidgets.QComboBox()
            source_selector.setObjectName("auxSourceSelector")
            source_selector.addItems(AUX_CAMERA_HOSTS)
            source_selector.setCurrentText(
                next((host for host in AUX_CAMERA_HOSTS if host in source_url), AUX_CAMERA_HOSTS[0])
            )
            source_selector.setFixedWidth(188)
            source_selector.setToolTip("Select the Aux Camera source IP")
            layout.addWidget(source_selector)
        layout.addWidget(copy)
        self.sources_layout.addWidget(card)
        self._source_rows.append(
            {
                "card": card,
                "checkbox": checkbox,
                "name": name,
                "address": source_url,
                "address_label": url_label,
                "path": path,
                "source_selector": source_selector,
            }
        )
        checkbox.toggled.connect(lambda _checked: self.settings_changed.emit())
        if source_selector is not None:
            source_selector.currentTextChanged.connect(
                lambda host, row=self._source_rows[-1]: self._set_aux_source(row, host)
            )

    def _set_aux_source(self, row: dict, host: str) -> None:
        url = aux_camera_url(host)
        row["address"] = url
        row["address_label"].setText(url)
        row["address_label"].setToolTip(url)
        self.settings_changed.emit()

    def output_url(self, path: str) -> str:
        return f"rtsp://{self._output_ip}:{self._output_port}/{path.lstrip('/')}"

    def set_output(self, output_ip: str, output_port: int) -> None:
        self._output_ip = output_ip
        self._output_port = int(output_port)

    def get_sources(self) -> List[VideoSource]:
        return [
            VideoSource(
                enabled=row["checkbox"].isChecked(),
                vtype=VIDEO_TYPE_RTSP,
                input_text=row["address"],
                out_path=row["path"],
            )
            for row in self._source_rows
        ]

    def set_service_state(self, state: str) -> None:
        self.lbl_status.setText(state.title())
        self.lbl_status.setProperty("serviceState", state)
        refresh_style(self.lbl_status)

    def set_source_statuses(self, statuses: dict) -> None:
        if not statuses:
            self.lbl_source_health.clear()
            self.lbl_source_health.setVisible(False)
            return
        streaming = sum(value == "streaming" for value in statuses.values())
        waiting = sum(value in {"waiting", "starting"} for value in statuses.values())
        self.lbl_source_health.setText(
            f"{streaming} streaming · {waiting} waiting for source"
            if waiting
            else f"{streaming} sources streaming"
        )
        self.lbl_source_health.setVisible(True)
