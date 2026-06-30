import logging
from typing import Dict, List

from PyQt5 import QtCore, QtGui, QtWidgets

from core.network_utils import host_responds_to_ping, select_preferred_ethernet_ipv4
from core.router_manager import RouterManager
from core.video_manager import VideoManager
from ui.components.network_status_panel import NetworkStatusPanel
from ui.components.router_control_panel import RouterControlPanel
from ui.components.telemetry_panel import TelemetryPanel
from ui.components.toolbar import Toolbar
from ui.components.video_panel import VideoPanel

DEFAULT_PING_INTERVAL_MS = 300000
PING_TIMEOUT_SEC = 1
STATUS_MESSAGE_TIMEOUT_MS = 5000


class PingWorker(QtCore.QObject):
    result_ready = QtCore.pyqtSignal(dict)
    finished = QtCore.pyqtSignal()

    def __init__(self, devices: List[Dict[str, str]], parent=None):
        super().__init__(parent)
        self.devices = devices
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @QtCore.pyqtSlot()
    def run(self) -> None:
        results: Dict[str, bool] = {}

        for dev in self.devices:
            if self._cancelled:
                break

            results[dev["name"]] = host_responds_to_ping(
                dev["ip"],
                timeout_sec=PING_TIMEOUT_SEC,
            )

        if self._cancelled:
            self.finished.emit()
            return

        self.result_ready.emit(results)
        self.finished.emit()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config: dict):
        super().__init__()

        self.config = config
        self.setWindowTitle("OMNI-Link")
        self.resize(1600, 900)
        self.setMinimumSize(920, 620)

        self.video = VideoManager(self)
        self.router = RouterManager(self)

        self.video.status_changed.connect(self._refresh_status)
        self.router.status_changed.connect(self._refresh_status)

        self.video.status_changed.connect(self._sync_ping_state)
        self.router.status_changed.connect(self._sync_ping_state)

        self.video.message.connect(self._handle_video_message)

        self._out_ip = select_preferred_ethernet_ipv4()
        self._ping_running = False
        self._ping_thread = None
        self._ping_worker = None
        self._ping_interval_ms = self._configured_ping_interval_ms()
        self._last_runtime_message = ""

        self._build_ui()
        self._setup_connections()

        self.statusBar().showMessage("Ready")
        self._refresh_status()
        self._sync_ping_state()
        self._request_ping_refresh()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        central.setObjectName("mainSurface")
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(14, 14, 14, 10)
        root_layout.setSpacing(10)

        self.toolbar = Toolbar()
        root_layout.addWidget(self.toolbar)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setOpaqueResize(True)
        split.setHandleWidth(10)
        root_layout.addWidget(split, 1)

        left_widget = QtWidgets.QWidget()
        left_widget.setMinimumWidth(420)

        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(8)

        self.video_panel = VideoPanel(self.config, self._out_ip)
        left_layout.addWidget(self.video_panel)

        split.addWidget(self._scrollable_panel(left_widget))

        right_widget = QtWidgets.QWidget()
        right_widget.setMinimumWidth(420)

        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(8)

        self.telemetry_panel = TelemetryPanel(self.config)
        self.router_control_panel = RouterControlPanel()
        self.network_status_panel = NetworkStatusPanel(
            self.config.get("ping_devices", [])
        )

        right_layout.addWidget(self.telemetry_panel)
        right_layout.addWidget(self.router_control_panel)
        right_layout.addWidget(self.network_status_panel)
        right_layout.addStretch(1)

        split.addWidget(self._scrollable_panel(right_widget))
        split.setSizes([800, 800])

    def _scrollable_panel(self, widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setWidget(widget)
        return scroll

    def _setup_connections(self) -> None:
        self.toolbar.refresh_ip_requested.connect(self._refresh_ethernet_ip)
        self.toolbar.start_all_requested.connect(self._start_all)
        self.toolbar.stop_all_requested.connect(self._stop_all)

        self.video_panel.start_requested.connect(self._start_video_clicked)
        self.video_panel.stop_requested.connect(self.video.stop)

        self.router_control_panel.start_requested.connect(self._start_router_clicked)
        self.router_control_panel.stop_requested.connect(self.router.stop)

        self.telemetry_panel.targets_copy_requested.connect(self._copy_targets)
        self.network_status_panel.refresh_requested.connect(self._request_ping_refresh)

        self.ping_timer = QtCore.QTimer(self)
        self.ping_timer.setInterval(self._ping_interval_ms)
        self.ping_timer.timeout.connect(self._request_ping_refresh)
        self.ping_timer.start()

    def _handle_video_message(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        self._last_runtime_message = text
        logging.info("Video Manager: %s", text)
        self.statusBar().showMessage(text, STATUS_MESSAGE_TIMEOUT_MS)

    def _refresh_ethernet_ip(self) -> None:
        self._out_ip = select_preferred_ethernet_ipv4()
        self.video_panel.set_output_ip(self._out_ip)

    def _copy_targets(self, targets_text: str) -> None:
        QtWidgets.QApplication.clipboard().setText((targets_text or "").strip())

    def _start_video_clicked(self) -> None:
        self._refresh_ethernet_ip()

        options = self.video_panel.get_video_options()

        err = self.video.start(
            mediamtx_bin=options["mediamtx_bin"],
            out_port=options["out_port"],
            sources=self.video_panel.get_sources(),
            global_bitrate_kbps=options["global_bitrate_kbps"],
            webcam_res=options["webcam_res"],
            webcam_fps=options["webcam_fps"],
        )

        if err:
            QtWidgets.QMessageBox.critical(self, "OMNI-Link", err)
            logging.error("Video Manager Error: %s", err)
            self.statusBar().showMessage(err, STATUS_MESSAGE_TIMEOUT_MS)

        self._refresh_status()
        self._sync_ping_state()

    def _start_router_clicked(self) -> None:
        options = self.telemetry_panel.get_router_options()

        err = self.router.start(**options)

        if err:
            QtWidgets.QMessageBox.critical(self, "OMNI-Link", err)
            logging.error("Router Manager Error: %s", err)
            self.statusBar().showMessage(err, STATUS_MESSAGE_TIMEOUT_MS)

        self._refresh_status()
        self._sync_ping_state()

    def _request_ping_refresh(self) -> None:
        if self._ping_should_pause():
            self._sync_ping_state()
            return

        if self._ping_running:
            return

        self._ping_running = True
        self.network_status_panel.set_refreshing(True)

        ping_list = list(self.config.get("ping_devices", []))

        self._ping_thread = QtCore.QThread(self)
        self._ping_worker = PingWorker(ping_list)
        self._ping_worker.moveToThread(self._ping_thread)

        self._ping_thread.started.connect(self._ping_worker.run)
        self._ping_worker.result_ready.connect(self._apply_ping_results)
        self._ping_worker.finished.connect(self._ping_thread.quit)
        self._ping_worker.finished.connect(self._ping_worker.deleteLater)
        self._ping_thread.finished.connect(self._on_ping_finished)
        self._ping_thread.finished.connect(self._ping_thread.deleteLater)

        self._ping_thread.start()

    def _apply_ping_results(self, results: Dict[str, bool]) -> None:
        if self._ping_should_pause():
            return

        self.network_status_panel.apply_results(
            results,
            self.config.get("ping_devices", []),
        )

    def _on_ping_finished(self) -> None:
        self._ping_running = False
        self._ping_thread = None
        self._ping_worker = None
        self._sync_ping_state()

    def _start_all(self) -> None:
        self._refresh_ethernet_ip()
        self._start_router_clicked()
        self._start_video_clicked()
        self._sync_ping_state()
        self._refresh_status()

    def _stop_all(self) -> None:
        self.video.stop()
        self.router.stop()
        self._refresh_status()
        self._sync_ping_state()

    def _refresh_status(self) -> None:
        v_on = self.video.is_running()
        r_on = self.router.is_running()

        self.video_panel.set_running(v_on)
        self.router_control_panel.set_running(r_on, self.router.effective_tcp_port())
        self.toolbar.set_any_running(v_on or r_on)

        status_text = f"Video: {'ON' if v_on else 'OFF'} | Router: {'ON' if r_on else 'OFF'}"

        if self._last_runtime_message and (v_on or r_on):
            status_text = f"{status_text} | {self._last_runtime_message}"

        self.statusBar().showMessage(status_text)

    def _configured_ping_interval_ms(self) -> int:
        raw_interval = self.config.get("ping_interval_ms", DEFAULT_PING_INTERVAL_MS)

        try:
            interval_ms = int(raw_interval)
        except (TypeError, ValueError):
            interval_ms = DEFAULT_PING_INTERVAL_MS

        return max(60000, interval_ms)

    def _ping_should_pause(self) -> bool:
        return self.video.is_running() or self.router.is_running()

    def _sync_ping_state(self) -> None:
        paused = self._ping_should_pause()

        if paused:
            if self.ping_timer.isActive():
                self.ping_timer.stop()

            self._cancel_ping_refresh()
            self.network_status_panel.set_paused(True)
            return

        self.network_status_panel.set_paused(False)
        self.network_status_panel.set_refreshing(self._ping_running)

        if not self.ping_timer.isActive():
            self.ping_timer.start(self._ping_interval_ms)

    def _cancel_ping_refresh(self) -> None:
        if self._ping_worker:
            self._ping_worker.cancel()

    def closeEvent(self, e: QtGui.QCloseEvent):
        logging.info("Shutting down OMNI-Link...")

        self._stop_all()

        if self._ping_thread and self._ping_thread.isRunning():
            if self.ping_timer.isActive():
                self.ping_timer.stop()

            if self._ping_worker:
                self._ping_worker.cancel()

            self._ping_thread.quit()

            if not self._ping_thread.wait(3000):
                logging.warning("Timed out waiting for ping worker to stop.")

        e.accept()