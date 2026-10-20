import logging
import re
import time
from typing import Dict, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from core.diagnostics import ResourceSampler, TrafficSampler
from core.network_utils import host_responds_to_ping, select_preferred_ethernet
from core.router_manager import RouterManager
from core.video_manager import VideoManager
from ui.components.diagnostics_panel import DiagnosticsPanel, ThroughputBar
from ui.components.network_status_panel import NetworkStatusPanel
from ui.components.telemetry_panel import TelemetryOperatePanel, TelemetryPanel
from ui.components.toolbar import Toolbar
from ui.components.video_panel import VideoPanel
from ui.components.video_settings_panel import VideoSettingsPanel

DEFAULT_PING_INTERVAL_MS = 300000
PING_TIMEOUT_SEC = 1
STATUS_MESSAGE_TIMEOUT_MS = 5000
STATUS_MESSAGE_LIMIT = 180
STATUS_UPDATE_INTERVAL_SEC = 1.0


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
        results = {}
        for device in self.devices:
            if self._cancelled:
                break
            results[device["name"]] = host_responds_to_ping(
                device["ip"], timeout_sec=PING_TIMEOUT_SEC
            )
        if not self._cancelled:
            self.result_ready.emit(results)
        self.finished.emit()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        config: dict,
        video_manager: Optional[VideoManager] = None,
        router_manager: Optional[RouterManager] = None,
    ):
        super().__init__()
        self.config = config
        self.setWindowTitle("OMNI-Link")
        self.resize(1600, 900)
        self.setMinimumSize(920, 620)
        self.video = video_manager or VideoManager(self)
        self.router = router_manager or RouterManager(self)
        self._service_states = {"video": "stopped", "telemetry": "stopped"}
        self._service_errors = {"video": "", "telemetry": ""}
        self._last_status_update = 0.0
        self._pending_status = ""
        self._interface_name, self._out_ip = select_preferred_ethernet()
        self._ping_running = False
        self._ping_thread = None
        self._ping_worker = None
        self._ping_interval_ms = self._configured_ping_interval_ms()

        self._build_ui()
        self._setup_connections()
        self._set_service_state("video", "stopped")
        self._set_service_state("telemetry", "stopped")

        self._resource_sampler = ResourceSampler(self._managed_processes, self)
        self._resource_sampler.updated.connect(self.diagnostics_panel.set_resource_stats)
        self._resource_sampler.start()
        self._traffic_sampler = TrafficSampler(
            self.video.process_ids,
            self.router.process_ids,
            self,
            video_bytes_provider=self.video.published_bytes,
        )
        self._traffic_sampler.updated.connect(self.throughput_bar.set_stats)
        self._traffic_sampler.updated.connect(self.diagnostics_panel.set_traffic_stats)
        self._traffic_sampler.start()

        self.statusBar().showMessage("Stopped")
        self._refresh_footer()
        self._refresh_status()
        self._sync_ping_state()
        self._request_ping_refresh()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        central.setObjectName("mainSurface")
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(28, 14, 28, 8)
        root.setSpacing(8)

        self.toolbar = Toolbar()
        root.addWidget(self.toolbar)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("mainTabs")
        root.addWidget(self.tabs, 1)

        self.video_settings = VideoSettingsPanel(self.config, self._out_ip)
        self.telemetry_panel = TelemetryPanel(self.config)
        self.video_panel = VideoPanel(
            self.config,
            self._out_ip,
            self.video_settings.sp_rtsp_port.value(),
        )
        self.telemetry_operate = TelemetryOperatePanel(self.config)
        self.telemetry_operate.sync_from_settings(self.telemetry_panel)
        self.network_status_panel = NetworkStatusPanel(self.config.get("ping_devices", []))
        self.throughput_bar = ThroughputBar()
        self.diagnostics_panel = DiagnosticsPanel()

        operate = QtWidgets.QWidget()
        operate_layout = QtWidgets.QVBoxLayout(operate)
        operate_layout.setContentsMargins(6, 16, 6, 0)
        operate_layout.setSpacing(16)
        upper_container = QtWidgets.QWidget()
        upper = QtWidgets.QHBoxLayout(upper_container)
        upper.setContentsMargins(0, 0, 0, 0)
        upper.setSpacing(20)
        upper.addWidget(self.video_panel, 1)
        upper.addWidget(self.telemetry_operate, 1)
        operate_layout.addWidget(upper_container, 3)
        operate_layout.addWidget(self.network_status_panel, 2)
        operate_layout.addWidget(self.throughput_bar)
        self.tabs.addTab(operate, "Operate")

        settings_content = QtWidgets.QWidget()
        settings_layout = QtWidgets.QHBoxLayout(settings_content)
        settings_layout.setContentsMargins(0, 8, 0, 0)
        settings_layout.setSpacing(16)
        settings_layout.addWidget(self.video_settings, 1, QtCore.Qt.AlignTop)
        settings_layout.addWidget(self.telemetry_panel, 1, QtCore.Qt.AlignTop)
        self.settings_scroll = self._scrollable(settings_content)
        self.tabs.addTab(self.settings_scroll, "Settings")

        diagnostics_content = QtWidgets.QWidget()
        diagnostics_layout = QtWidgets.QVBoxLayout(diagnostics_content)
        diagnostics_layout.setContentsMargins(0, 8, 0, 0)
        diagnostics_layout.addWidget(self.diagnostics_panel, 0, QtCore.Qt.AlignTop)
        diagnostics_layout.addStretch(1)
        self.tabs.addTab(self._scrollable(diagnostics_content), "Diagnostics")

        self.footer_interface = QtWidgets.QLabel()
        self.footer_interface.setObjectName("footerInterface")
        self.statusBar().addPermanentWidget(self.footer_interface)

    def _scrollable(self, widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(widget)
        return scroll

    def _setup_connections(self) -> None:
        self.toolbar.refresh_requested.connect(self._refresh_all)
        self.toolbar.video_toggle_requested.connect(self._toggle_video)
        self.toolbar.telemetry_toggle_requested.connect(self._toggle_telemetry)
        self.toolbar.all_toggle_requested.connect(self._toggle_all)
        self.toolbar.profile_changed.connect(self._profile_changed)
        self.video.status_changed.connect(self._refresh_status)
        self.router.status_changed.connect(self._refresh_status)
        self.video.status_changed.connect(self._sync_ping_state)
        self.router.status_changed.connect(self._sync_ping_state)
        self.video.message.connect(self._show_status_message)
        self.video.failed.connect(lambda message: self._service_failed("video", message))
        self.router.failed.connect(lambda message: self._service_failed("telemetry", message))
        self.video.source_status_changed.connect(self.video_panel.set_source_statuses)
        self.video_panel.settings_requested.connect(lambda: self.tabs.setCurrentIndex(1))
        self.telemetry_operate.settings_requested.connect(lambda: self.tabs.setCurrentIndex(1))
        self.telemetry_operate.targets_copy_requested.connect(self._copy_targets)
        self.telemetry_operate.target_toggled.connect(self._target_toggled)
        self.video_settings.settings_changed.connect(self._sync_video_output)
        self.telemetry_panel.settings_changed.connect(self._sync_telemetry_operate)
        self.network_status_panel.refresh_requested.connect(self._request_ping_refresh)

        self.ping_timer = QtCore.QTimer(self)
        self.ping_timer.setInterval(self._ping_interval_ms)
        self.ping_timer.timeout.connect(self._request_ping_refresh)
        self.ping_timer.start()

    def _profile_changed(self, profile: str) -> None:
        self.telemetry_panel.set_profile(profile)
        self._sync_telemetry_operate()
        self._refresh_diagnostics_connections()

    def _target_toggled(self, name: str, enabled: bool) -> None:
        self.telemetry_panel.set_target_enabled(name, enabled)

    def _sync_telemetry_operate(self) -> None:
        self.telemetry_operate.sync_from_settings(self.telemetry_panel)
        self._refresh_diagnostics_connections()

    def _sync_video_output(self) -> None:
        self.video_panel.set_output(
            self._out_ip, int(self.video_settings.sp_rtsp_port.value())
        )
        self._refresh_diagnostics_connections()

    def _refresh_all(self) -> None:
        self._refresh_ethernet_ip()
        if self._ping_should_pause():
            self._show_status_message("Network checks are paused while a service is active")
        self._request_ping_refresh()

    def _refresh_ethernet_ip(self) -> None:
        self._interface_name, self._out_ip = select_preferred_ethernet()
        self.video_settings.set_output_ip(self._out_ip)
        self._sync_video_output()
        self._refresh_footer()

    def _refresh_footer(self) -> None:
        self.footer_interface.setText(f"{self._interface_name} · {self._out_ip}")
        self._refresh_diagnostics_connections()

    def _refresh_diagnostics_connections(self) -> None:
        if not hasattr(self, "diagnostics_panel"):
            return
        self.diagnostics_panel.set_connections(
            self._interface_name,
            self._out_ip,
            self.video_settings.video_base_url(),
            self.telemetry_panel.effective_connection_summary(),
        )

    def _copy_targets(self, targets_text: str) -> None:
        QtWidgets.QApplication.clipboard().setText((targets_text or "").strip())

    def _toggle_video(self) -> None:
        if self._service_states["video"] == "running":
            self._stop_video()
        elif self._service_states["video"] in {"stopped", "failed"}:
            self._start_video()

    def _toggle_telemetry(self) -> None:
        if self._service_states["telemetry"] == "running":
            self._stop_telemetry()
        elif self._service_states["telemetry"] in {"stopped", "failed"}:
            self._start_telemetry()

    def _toggle_all(self) -> None:
        if all(state == "running" for state in self._service_states.values()):
            self._stop_video()
            self._stop_telemetry()
            return
        if self._service_states["video"] in {"stopped", "failed"}:
            self._start_video()
        if self._service_states["telemetry"] in {"stopped", "failed"}:
            self._start_telemetry()

    def _start_video(self) -> None:
        if self._service_states["video"] in {"starting", "running", "stopping"}:
            return
        self._refresh_ethernet_ip()
        self._set_service_state("video", "starting")
        options = self.video_settings.get_video_options()
        error = self.video.start(
            mediamtx_bin=options["mediamtx_bin"],
            out_port=options["out_port"],
            sources=self.video_panel.get_sources(),
            global_bitrate_kbps=options["global_bitrate_kbps"],
            passthrough=options["passthrough"],
        )
        if error:
            self._service_failed("video", error)

    def _start_telemetry(self) -> None:
        if self._service_states["telemetry"] in {"starting", "running", "stopping"}:
            return
        self._set_service_state("telemetry", "starting")
        error = self.router.start(**self.telemetry_panel.get_router_options())
        if error:
            self._service_failed("telemetry", error)

    def _stop_video(self) -> None:
        if self._service_states["video"] != "running":
            return
        self._set_service_state("video", "stopping")
        self.video.stop()

    def _stop_telemetry(self) -> None:
        if self._service_states["telemetry"] != "running":
            return
        self._set_service_state("telemetry", "stopping")
        self.router.stop()

    def _service_failed(self, service: str, message: str) -> None:
        self._service_errors[service] = self._single_line(message)
        self._set_service_state(service, "failed")
        logging.error("%s: %s", service, message)
        self._show_status_message(f"{service.title()} failed: {message}", force=True)

    def _set_service_state(self, service: str, state: str) -> None:
        self._service_states[service] = state
        self.toolbar.set_service_state(service, state)
        self.toolbar.set_all_state(
            self._service_states["video"], self._service_states["telemetry"]
        )
        if service == "video":
            self.video_panel.set_service_state(state)
        else:
            self.telemetry_operate.set_service_state(state)

    def _refresh_status(self) -> None:
        self._sync_service_from_manager("video", self.video.is_running(), self._video_active())
        self._sync_service_from_manager(
            "telemetry", self.router.is_running(), self._telemetry_active()
        )
        states = self._service_states
        if states["video"] == states["telemetry"] == "stopped":
            summary = "Stopped"
        elif states["video"] == states["telemetry"] == "running":
            summary = "Services running"
        else:
            summary = f"Video {states['video']} · Telemetry {states['telemetry']}"
        self._show_status_message(summary)

    def _sync_service_from_manager(self, service: str, running: bool, active: bool) -> None:
        current = self._service_states[service]
        if running and current != "running":
            self._service_errors[service] = ""
            self._set_service_state(service, "running")
        elif current == "stopping" and not active:
            self._set_service_state(service, "stopped")
        elif current == "running" and not active:
            self._set_service_state(service, "stopped")

    def _video_active(self) -> bool:
        process = self.video.mediamtx_process
        return bool(process and process.state() != QtCore.QProcess.NotRunning)

    def _telemetry_active(self) -> bool:
        return self.router.is_starting() or (
            self.router.router_process.state() != QtCore.QProcess.NotRunning
        )

    def _show_status_message(self, text: str, force: bool = False) -> None:
        message = self._single_line(text)[:STATUS_MESSAGE_LIMIT]
        if not message:
            return
        now = time.monotonic()
        if not force and now - self._last_status_update < STATUS_UPDATE_INTERVAL_SEC:
            self._pending_status = message
            delay = max(
                1,
                int((STATUS_UPDATE_INTERVAL_SEC - (now - self._last_status_update)) * 1000),
            )
            QtCore.QTimer.singleShot(delay, self._flush_pending_status)
            return
        self.statusBar().showMessage(message, STATUS_MESSAGE_TIMEOUT_MS)
        self._last_status_update = now

    def _flush_pending_status(self) -> None:
        if self._pending_status:
            message, self._pending_status = self._pending_status, ""
            self._show_status_message(message, force=True)

    @staticmethod
    def _single_line(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip())

    def _request_ping_refresh(self) -> None:
        if self._ping_should_pause():
            self._sync_ping_state()
            return
        if self._ping_running:
            return
        self._ping_running = True
        self.network_status_panel.set_refreshing(True)
        self._ping_thread = QtCore.QThread(self)
        self._ping_worker = PingWorker(list(self.config.get("ping_devices", [])))
        self._ping_worker.moveToThread(self._ping_thread)
        self._ping_thread.started.connect(self._ping_worker.run)
        self._ping_worker.result_ready.connect(self._apply_ping_results)
        self._ping_worker.finished.connect(self._ping_thread.quit)
        self._ping_worker.finished.connect(self._ping_worker.deleteLater)
        self._ping_thread.finished.connect(self._on_ping_finished)
        self._ping_thread.finished.connect(self._ping_thread.deleteLater)
        self._ping_thread.start()

    def _apply_ping_results(self, results: Dict[str, bool]) -> None:
        if not self._ping_should_pause():
            self.network_status_panel.apply_results(
                results, self.config.get("ping_devices", [])
            )

    def _on_ping_finished(self) -> None:
        self._ping_running = False
        self._ping_thread = None
        self._ping_worker = None
        self._sync_ping_state()

    def _configured_ping_interval_ms(self) -> int:
        try:
            interval = int(self.config.get("ping_interval_ms", DEFAULT_PING_INTERVAL_MS))
        except (TypeError, ValueError):
            interval = DEFAULT_PING_INTERVAL_MS
        return max(60000, interval)

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

    def _managed_processes(self):
        return self.video.process_ids() + self.router.process_ids()

    def closeEvent(self, event: QtGui.QCloseEvent):
        logging.info("Shutting down OMNI-Link")
        if self.ping_timer.isActive():
            self.ping_timer.stop()
        self._cancel_ping_refresh()
        self.video.emergency_shutdown()
        self.router.emergency_shutdown()
        event.accept()
