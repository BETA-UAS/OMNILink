from pathlib import Path

from PyQt5 import QtCore, QtWidgets

from ui.components.common import set_field_value_label, set_muted_label


def format_bytes(value: float) -> str:
    value = max(0.0, float(value))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return "0 B"


class ThroughputBar(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("throughputBar")
        self.setFixedHeight(50)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)
        video_name = QtWidgets.QLabel("Video")
        telemetry_name = QtWidgets.QLabel("Telemetry")
        self.lbl_video_rate = QtWidgets.QLabel("0 B/s")
        self.lbl_telemetry_rate = QtWidgets.QLabel("Unavailable")
        set_field_value_label(self.lbl_video_rate)
        set_muted_label(self.lbl_telemetry_rate)
        layout.addWidget(video_name)
        layout.addWidget(self.lbl_video_rate)
        layout.addSpacing(22)
        layout.addWidget(telemetry_name)
        layout.addWidget(self.lbl_telemetry_rate)
        layout.addStretch(1)

    def set_stats(self, stats: dict) -> None:
        self.lbl_video_rate.setText(f"{format_bytes(stats.get('video_bytes_per_sec', 0))}/s")
        self.lbl_telemetry_rate.setText("Unavailable")


def _card(title: str):
    frame = QtWidgets.QFrame()
    frame.setObjectName("diagnosticCard")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 18)
    layout.setSpacing(12)
    heading = QtWidgets.QLabel(title)
    heading.setObjectName("sectionTitle")
    layout.addWidget(heading)
    return frame, layout


class DiagnosticsPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 8, 6, 0)
        root.setSpacing(16)

        title = QtWidgets.QLabel("Diagnostics")
        title.setObjectName("pageTitle")
        subtitle = QtWidgets.QLabel(
            "Managed process health, resource sampling, and active configuration"
        )
        set_muted_label(subtitle)
        root.addWidget(title)
        root.addWidget(subtitle)

        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(16)

        resources, resource_layout = _card("Runtime resources")
        resource_grid = QtWidgets.QGridLayout()
        resource_grid.setHorizontalSpacing(18)
        resource_grid.setVerticalSpacing(12)
        self.lbl_process_count = QtWidgets.QLabel("0")
        self.lbl_resource_summary = QtWidgets.QLabel("Waiting for first 5-second sample")
        self.lbl_resource_summary.setWordWrap(True)
        set_field_value_label(self.lbl_process_count)
        set_muted_label(self.lbl_resource_summary)
        resource_grid.addWidget(QtWidgets.QLabel("Managed child processes"), 0, 0)
        resource_grid.addWidget(self.lbl_process_count, 0, 1)
        resource_grid.addWidget(QtWidgets.QLabel("Latest CPU / memory sample"), 1, 0)
        resource_grid.addWidget(self.lbl_resource_summary, 1, 1)
        resource_grid.setColumnStretch(1, 1)
        resource_layout.addLayout(resource_grid)
        resource_layout.addStretch(1)

        connections, connection_layout = _card("Connection details")
        detail_grid = QtWidgets.QGridLayout()
        detail_grid.setHorizontalSpacing(18)
        detail_grid.setVerticalSpacing(12)
        self.lbl_interface = QtWidgets.QLabel("—")
        self.lbl_video_endpoint = QtWidgets.QLabel("—")
        self.lbl_telemetry_endpoint = QtWidgets.QLabel("—")
        for row, (name, label) in enumerate(
            (
                ("Selected interface", self.lbl_interface),
                ("Video output", self.lbl_video_endpoint),
                ("Telemetry input", self.lbl_telemetry_endpoint),
            )
        ):
            set_field_value_label(label)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            detail_grid.addWidget(QtWidgets.QLabel(name), row, 0)
            detail_grid.addWidget(label, row, 1)
        detail_grid.setColumnStretch(1, 1)
        connection_layout.addLayout(detail_grid)
        connection_layout.addStretch(1)
        cards.addWidget(resources, 1)
        cards.addWidget(connections, 1)
        root.addLayout(cards)

        logging_card, logging_layout = _card("Diagnostic logging")
        logging_grid = QtWidgets.QGridLayout()
        logging_grid.setHorizontalSpacing(18)
        logging_grid.setVerticalSpacing(10)
        path = Path.home() / ".local" / "state" / "omnilink" / "omnilink.log"
        path_label = QtWidgets.QLabel(str(path))
        path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        set_field_value_label(path_label)
        logging_grid.addWidget(QtWidgets.QLabel("Rotating log file"), 0, 0)
        logging_grid.addWidget(path_label, 0, 1)
        logging_grid.addWidget(QtWidgets.QLabel("Retention"), 1, 0)
        logging_grid.addWidget(QtWidgets.QLabel("5 MB per file · 3 backups"), 1, 1)
        logging_grid.setColumnStretch(1, 1)
        logging_layout.addLayout(logging_grid)
        root.addWidget(logging_card)
        root.addStretch(1)

    def set_traffic_stats(self, stats: dict) -> None:
        self.lbl_process_count.setText(str(int(stats.get("process_count", 0))))

    def set_resource_stats(self, stats: dict) -> None:
        self.lbl_resource_summary.setText(stats.get("summary", "No live processes"))

    def set_connections(
        self, interface: str, ip: str, video_endpoint: str, telemetry_endpoint: str
    ) -> None:
        self.lbl_interface.setText(f"{interface} · {ip}")
        self.lbl_video_endpoint.setText(video_endpoint)
        self.lbl_telemetry_endpoint.setText(telemetry_endpoint)

    @staticmethod
    def _format_rate(value: float) -> str:
        return f"{format_bytes(value)}/s"

    @staticmethod
    def _format_bytes(value: float) -> str:
        return format_bytes(value)
