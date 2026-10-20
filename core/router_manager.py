import logging
import os
import socket
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

from core.config_models import RouterConfig
from core.diagnostics import SuppressingLogger
from core.mavlink import mavlink_v1_heartbeat_packet
from core.network_utils import (
    command_exists,
    is_valid_ipv4_address,
    is_valid_network_port,
    noninteractive_sudo_error,
)
from core.router_config import build_router_config, parse_router_targets
from PyQt5 import QtCore


class UdpHeartbeatPrimer(QtCore.QThread):
    def __init__(self, listen_port: int, upstream_ip: str, upstream_port: int, parent=None):
        super().__init__(parent)
        self.listen_port = int(listen_port)
        self.upstream_ip = upstream_ip
        self.upstream_port = int(upstream_port)

    def run(self) -> None:
        socket_obj: Optional[socket.socket] = None
        try:
            logging.info(
                "Sending UDP Primer heartbeat to %s:%s",
                self.upstream_ip,
                self.upstream_port,
            )
            socket_obj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socket_obj.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socket_obj.bind(("0.0.0.0", self.listen_port))

            sequence = 0
            for _ in range(3):
                socket_obj.sendto(
                    mavlink_v1_heartbeat_packet(sequence),
                    (self.upstream_ip, self.upstream_port),
                )
                sequence = (sequence + 1) & 0xFF
                time.sleep(0.2)
        except OSError:
            logging.exception("UDP Primer error")
        finally:
            if socket_obj:
                socket_obj.close()


class RouterManager(QtCore.QObject):
    status_changed = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.router_bin = "mavlink-routerd"
        self.router_process = QtCore.QProcess(self)
        self.router_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.router_process.stateChanged.connect(lambda _state: self.status_changed.emit())
        self.router_process.finished.connect(self._on_router_finished)
        self.router_process.errorOccurred.connect(self._on_router_error)
        self.router_process.readyReadStandardOutput.connect(self._log_router_output)

        self._effective_tcp_port = 5760
        self._primer: Optional[UdpHeartbeatPrimer] = None
        self._router_config_path: Optional[Path] = None
        self._stopping = False
        self._starting = False
        self._failure_reported = False
        self._noisy_log = SuppressingLogger(logging.getLogger("router.subprocess"))
        self._stop_timer = QtCore.QTimer(self)
        self._stop_timer.setSingleShot(True)
        self._stop_timer.timeout.connect(self._force_stop)

    def is_running(self) -> bool:
        return self.router_process.state() == QtCore.QProcess.Running

    def is_starting(self) -> bool:
        return self._starting

    def process_ids(self):
        pid = int(self.router_process.processId())
        return [("MAVLink Router", pid)] if pid else []

    def effective_tcp_port(self) -> int:
        return int(self._effective_tcp_port)

    def _parse_targets(self, text: str) -> List[Tuple[str, int]]:
        return parse_router_targets(text)

    def _build_config_text(
        self,
        tcp_server_port_ui: int,
        in_mode: str,
        listen_udp_port: int,
        tcp_up_ip: str,
        tcp_up_port: int,
        targets_text: str,
        espusr_enabled: bool,
        espusr_mode: str,
        espusr_ip: str,
        espusr_port: int,
    ) -> str:
        config = RouterConfig(
            in_mode=in_mode,
            listen_udp_port=listen_udp_port,
            tcp_up_ip=tcp_up_ip,
            tcp_up_port=tcp_up_port,
            tcp_server_port_ui=tcp_server_port_ui,
            targets_text=targets_text,
            primer_enabled=False,
            primer_up_ip="",
            primer_up_port=0,
            use_sudo=False,
            espusr_enabled=espusr_enabled,
            espusr_mode=espusr_mode,
            espusr_ip=espusr_ip,
            espusr_port=espusr_port,
        )
        config_text, effective_tcp_port = build_router_config(config)
        self._effective_tcp_port = effective_tcp_port
        return config_text

    def start(
        self,
        in_mode: str,
        listen_udp_port: int,
        tcp_up_ip: str,
        tcp_up_port: int,
        tcp_server_port_ui: int,
        targets_text: str,
        primer_enabled: bool,
        primer_up_ip: str,
        primer_up_port: int,
        use_sudo: bool,
        espusr_enabled: bool,
        espusr_mode: str,
        espusr_ip: str,
        espusr_port: int,
    ) -> Optional[str]:
        if self._starting or self.router_process.state() != QtCore.QProcess.NotRunning:
            return None

        if not command_exists(self.router_bin):
            return f"{self.router_bin} tidak ditemukan"
        if use_sudo:
            sudo_error = noninteractive_sudo_error()
            if sudo_error:
                return sudo_error

        config = RouterConfig(
            in_mode=in_mode,
            listen_udp_port=listen_udp_port,
            tcp_up_ip=tcp_up_ip,
            tcp_up_port=tcp_up_port,
            tcp_server_port_ui=tcp_server_port_ui,
            targets_text=targets_text,
            primer_enabled=primer_enabled,
            primer_up_ip=primer_up_ip,
            primer_up_port=primer_up_port,
            use_sudo=use_sudo,
            espusr_enabled=espusr_enabled,
            espusr_mode=espusr_mode,
            espusr_ip=espusr_ip,
            espusr_port=espusr_port,
        )

        try:
            config_text, self._effective_tcp_port = build_router_config(config)
            config_path = self._write_temp_config(config_text)
        except ValueError as exc:
            logging.error("Router config error: %s", exc)
            return str(exc)
        except OSError:
            logging.exception("Router config file error")
            return "Gagal membuat konfigurasi router"

        command = self.router_bin
        args = ["-c", str(config_path)]
        if config.use_sudo:
            command = "sudo"
            args = ["-n", self.router_bin] + args

        self._starting = True
        self._failure_reported = False
        if not self._run_udp_primer(config, lambda: self._launch_router(command, args)):
            self._launch_router(command, args)
        self.status_changed.emit()
        return None

    def _launch_router(self, command: str, args: List[str]) -> None:
        if not self._starting or self._stopping:
            return
        logging.info("Starting MAVLink Router: %s %s", command, " ".join(args))
        self.router_process.start(command, args)

    def stop(self) -> None:
        if self.router_process.state() == QtCore.QProcess.NotRunning:
            self._starting = False
            self._cleanup_router_config()
            self.status_changed.emit()
            return

        logging.info("Stopping MAVLink Router")
        self._stopping = True
        self._starting = False
        self.router_process.terminate()
        self._stop_timer.start(1500)
        self.status_changed.emit()

    def emergency_shutdown(self) -> None:
        self.stop()
        if self.router_process.state() != QtCore.QProcess.NotRunning:
            self.router_process.kill()

    def _force_stop(self) -> None:
        if self.router_process.state() != QtCore.QProcess.NotRunning:
            self.router_process.kill()

    def _on_router_error(self, _error: QtCore.QProcess.ProcessError) -> None:
        if self._stopping:
            return
        message = f"Telemetry router process error: {self.router_process.errorString()}"
        self._starting = False
        logging.error(message)
        self._cleanup_router_config()
        self._failure_reported = True
        self.failed.emit(message)
        self.status_changed.emit()

    def _write_temp_config(self, config_text: str) -> Path:
        self._cleanup_router_config()
        file_descriptor, config_path = tempfile.mkstemp(
            prefix="omni-link-router-",
            suffix=".conf",
        )
        os.close(file_descriptor)
        path = Path(config_path)
        path.write_text(config_text, encoding="utf-8")
        self._router_config_path = path
        return path

    def _run_udp_primer(self, config: RouterConfig, callback) -> bool:
        if config.in_mode.strip().upper() != "UDP" or not config.primer_enabled:
            return False
        if not (
            is_valid_ipv4_address(config.primer_up_ip)
            and is_valid_network_port(config.primer_up_port)
            and is_valid_network_port(config.listen_udp_port)
        ):
            return False

        self._primer = UdpHeartbeatPrimer(
            listen_port=config.listen_udp_port,
            upstream_ip=config.primer_up_ip,
            upstream_port=config.primer_up_port,
        )
        self._primer.start()
        primer = self._primer

        def finished() -> None:
            if self._primer is primer:
                self._primer = None
            primer.deleteLater()
            callback()

        primer.finished.connect(finished)
        return True

    def _cleanup_router_config(self) -> None:
        if not self._router_config_path:
            return

        try:
            self._router_config_path.unlink(missing_ok=True)
        except OSError:
            logging.exception("Failed to remove temporary router config")
        finally:
            self._router_config_path = None

    def _on_router_finished(self, exit_code: int, _exit_status: QtCore.QProcess.ExitStatus) -> None:
        was_stopping = self._stopping
        self._starting = False
        self._stop_timer.stop()
        self._stopping = False
        self._cleanup_router_config()
        if not was_stopping and not self._failure_reported:
            message = f"Telemetry router exited unexpectedly (code {exit_code})"
            logging.error(message)
            self.failed.emit(message)
        self._failure_reported = False
        self._noisy_log.flush()
        self.status_changed.emit()

    def _log_router_output(self) -> None:
        try:
            output = bytes(self.router_process.readAllStandardOutput())
        except RuntimeError:
            return

        for line in output[:65536].decode("utf-8", errors="replace").splitlines()[:512]:
            if line.strip():
                self._noisy_log.record(f"MAVLink Router: {line.strip()[:500]}")
