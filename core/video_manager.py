import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional

from core.config_models import VideoConfig, VideoSource
from core.diagnostics import SuppressingLogger
from core.video_config import (
    MAIN_CAMERA_URLS,
    active_video_sources,
    build_ffmpeg_args,
    validate_video_config,
)
from PyQt5 import QtCore

STARTUP_GRACE_SEC = 8.0
STALL_TIMEOUT_SEC = 10.0
STABLE_STREAM_SEC = 30.0
RETRY_DELAYS_SEC = (2, 5, 10, 30)
PROCESS_STOP_DEADLINE_MS = 1500
MAX_OUTPUT_BYTES_PER_EVENT = 65536


class VideoManager(QtCore.QObject):
    status_changed = QtCore.pyqtSignal()
    message = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)
    source_status_changed = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mediamtx_process: Optional[QtCore.QProcess] = None
        self.ffmpeg_processes: List[QtCore.QProcess] = []
        self._publishers: Dict[str, dict] = {}
        self._session = 0
        self._stopping = False
        self._config: Optional[VideoConfig] = None
        self._passthrough = False
        self._noisy_log = SuppressingLogger(logging.getLogger("video.subprocess"))

        self.watchdog = QtCore.QTimer(self)
        self.watchdog.setInterval(1000)
        self.watchdog.timeout.connect(self._watch)

    def is_running(self) -> bool:
        return bool(
            self.mediamtx_process and self.mediamtx_process.state() == QtCore.QProcess.Running
        )

    def process_ids(self):
        result = []
        if self.mediamtx_process:
            result.append(("MediaMTX", int(self.mediamtx_process.processId())))
        for path, record in self._publishers.items():
            process = record.get("process")
            if process:
                result.append((f"FFmpeg:{path}", int(process.processId())))
        return result

    def source_statuses(self) -> Dict[str, str]:
        return {path: record["state"] for path, record in self._publishers.items()}

    def published_bytes(self) -> int:
        return sum(int(record.get("published_bytes", 0)) for record in self._publishers.values())

    def start(
        self,
        mediamtx_bin: str,
        out_port: int,
        sources: List[VideoSource],
        global_bitrate_kbps: int,
        passthrough: bool = False,
    ) -> Optional[str]:
        if self.mediamtx_process is not None or self._publishers:
            return None
        config = VideoConfig(
            mediamtx_bin=mediamtx_bin,
            out_port=out_port,
            sources=sources,
            global_bitrate_kbps=global_bitrate_kbps,
        )
        error = validate_video_config(config)
        if error:
            return error

        active_sources = active_video_sources(config.sources)
        normalized_paths = [self._normalize_path(source.out_path) for source in active_sources]
        try:
            config_path = self._write_mediamtx_cfg(normalized_paths, int(config.out_port))
        except OSError as exc:
            return f"Unable to write MediaMTX configuration: {exc}"

        self._session += 1
        session = self._session
        self._stopping = False
        self._config = config
        self._passthrough = passthrough
        self._publishers = {
            self._normalize_path(source.out_path): {
                "source": source,
                "source_urls": (
                    MAIN_CAMERA_URLS
                    if self._normalize_path(source.out_path) == "cam1"
                    and source.input_text.strip() in MAIN_CAMERA_URLS
                    else (source.input_text.strip(),)
                ),
                "source_index": 0,
                "process": None,
                "retry_timer": None,
                "retry_index": 0,
                "state": "waiting",
                "last_progress": None,
                "started_at": 0.0,
                "stable_since": None,
                "buffer": "",
                "published_bytes": 0,
                "last_reported_size": 0,
            }
            for source in active_sources
        }
        self._emit_source_status()

        process = QtCore.QProcess(self)
        self.mediamtx_process = process
        process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        process.stateChanged.connect(lambda _state, s=session: self._media_state_changed(s))
        process.started.connect(lambda s=session: self._media_started(s))
        process.errorOccurred.connect(lambda _error, s=session: self._media_error(s))
        process.finished.connect(
            lambda code, status, s=session: self._media_finished(s, code, status)
        )
        process.readyReadStandardOutput.connect(lambda s=session: self._drain_media_output(s))
        logging.info("Starting MediaMTX on RTSP port %d", int(config.out_port))
        process.start(config.mediamtx_bin, [str(config_path)])
        self.status_changed.emit()
        return None

    def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        self._session += 1
        self.watchdog.stop()
        logging.info("Stopping video service")
        for record in self._publishers.values():
            timer = record.get("retry_timer")
            if timer:
                timer.stop()
                timer.deleteLater()
                record["retry_timer"] = None
            process = record.get("process")
            if process:
                self._terminate_process(process)
            record["state"] = "stopped"
        if self.mediamtx_process:
            self._terminate_process(self.mediamtx_process)
        else:
            self._finish_stop()
        self._emit_source_status()
        self.status_changed.emit()

    def emergency_shutdown(self) -> None:
        """Terminate and immediately kill remaining children during application exit."""
        self.stop()
        processes = [self.mediamtx_process]
        processes.extend(record.get("process") for record in self._publishers.values())
        for process in processes:
            if process and process.state() != QtCore.QProcess.NotRunning:
                process.kill()

    def _media_started(self, session: int) -> None:
        if session != self._session or self._stopping:
            return
        self.watchdog.start()
        for path in self._publishers:
            QtCore.QTimer.singleShot(300, lambda p=path, s=session: self._start_publisher(p, s))
        self.status_changed.emit()

    def _media_state_changed(self, session: int) -> None:
        if session == self._session:
            self.status_changed.emit()

    def _media_error(self, session: int) -> None:
        if session != self._session or self._stopping or not self.mediamtx_process:
            return
        message = f"MediaMTX failed to start: {self.mediamtx_process.errorString()}"
        logging.error(message)
        self.failed.emit(message)

    def _media_finished(self, session: int, code: int, _status) -> None:
        process = self.mediamtx_process
        if process:
            process.deleteLater()
        self.mediamtx_process = None
        if session != self._session:
            if self._stopping:
                self._finish_stop()
            return
        if not self._stopping:
            message = f"MediaMTX exited unexpectedly (code {code})"
            logging.error(message)
            self.failed.emit(message)
            self.stop()
        else:
            self._finish_stop()
        self.status_changed.emit()

    def _start_publisher(self, path: str, session: int) -> None:
        if session != self._session or self._stopping or not self.is_running():
            return
        record = self._publishers.get(path)
        if not record or record.get("process") is not None:
            return
        timer = record.get("retry_timer")
        if timer:
            timer.stop()
            timer.deleteLater()
            record["retry_timer"] = None

        config = self._config
        if not config:
            return
        publish_url = f"rtsp://127.0.0.1:{int(config.out_port)}/{path}"
        source_urls = record.get("source_urls") or (record["source"].input_text.strip(),)
        source_url = source_urls[record.get("source_index", 0)]
        args = build_ffmpeg_args(
            source=replace(record["source"], input_text=source_url),
            publish_url=publish_url,
            bitrate_kbps=int(config.global_bitrate_kbps),
            passthrough=self._passthrough,
        )
        process = QtCore.QProcess(self)
        process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        record.update(
            process=process,
            state="starting",
            last_progress=None,
            started_at=time.monotonic(),
            stable_since=None,
            buffer="",
            last_reported_size=0,
        )
        self.ffmpeg_processes.append(process)
        process.started.connect(
            lambda p=path, s=session, q=process: self._publisher_started(p, s, q)
        )
        process.readyReadStandardOutput.connect(
            lambda p=path, s=session, q=process: self._drain_publisher_output(p, s, q)
        )
        process.errorOccurred.connect(
            lambda _error, p=path, s=session, q=process: self._publisher_error(p, s, q)
        )
        process.finished.connect(
            lambda code, status, p=path, s=session, q=process: self._publisher_finished(
                p, s, q, code, status
            )
        )
        logging.info("Starting camera publisher %s from %s", path, source_url)
        process.start("ffmpeg", args)
        self._emit_source_status()

    def _publisher_started(self, path: str, session: int, process: QtCore.QProcess) -> None:
        record = self._publishers.get(path)
        if session != self._session or not record or record.get("process") is not process:
            self._terminate_process(process)
            return
        record["state"] = "waiting"
        self._emit_source_status()

    def _publisher_error(self, path: str, session: int, process: QtCore.QProcess) -> None:
        record = self._publishers.get(path)
        if session != self._session or not record or record.get("process") is not process:
            return
        logging.warning("Camera %s process error: %s", path, process.errorString())
        record["state"] = "waiting"
        self._emit_source_status()

    def _publisher_finished(
        self, path: str, session: int, process: QtCore.QProcess, code: int, _status
    ) -> None:
        if process in self.ffmpeg_processes:
            self.ffmpeg_processes.remove(process)
        process.deleteLater()
        record = self._publishers.get(path)
        if not record or record.get("process") is not process:
            return
        record["process"] = None
        if session != self._session or self._stopping:
            record["state"] = "stopped"
            self._emit_source_status()
            if self._stopping:
                self._finish_stop()
            return
        logging.warning("Camera %s publisher exited (code %d); waiting to retry", path, code)
        record["state"] = "waiting"
        if self._advance_main_camera_source(record):
            logging.info(
                "Camera %s switching to %s",
                path,
                record["source_urls"][record["source_index"]],
            )
            QtCore.QTimer.singleShot(0, lambda p=path, s=session: self._start_publisher(p, s))
        else:
            self._schedule_retry(path, session)
        self._emit_source_status()

    @staticmethod
    def _advance_main_camera_source(record: dict) -> bool:
        """Try the fallback immediately; back off after both URLs fail."""
        urls = record.get("source_urls", ())
        if len(urls) < 2:
            return False
        index = record.get("source_index", 0)
        record["source_index"] = (index + 1) % len(urls)
        return index == 0

    def _schedule_retry(self, path: str, session: int) -> None:
        record = self._publishers.get(path)
        if not record or record.get("retry_timer") is not None or record.get("process") is not None:
            return
        index = min(record["retry_index"], len(RETRY_DELAYS_SEC) - 1)
        delay = RETRY_DELAYS_SEC[index]
        record["retry_index"] = min(index + 1, len(RETRY_DELAYS_SEC) - 1)
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda p=path, s=session: self._retry_timeout(p, s))
        record["retry_timer"] = timer
        timer.start(delay * 1000)
        logging.info("Camera %s retry scheduled in %d seconds", path, delay)

    def _retry_timeout(self, path: str, session: int) -> None:
        record = self._publishers.get(path)
        if not record:
            return
        timer = record.get("retry_timer")
        record["retry_timer"] = None
        if timer:
            timer.deleteLater()
        self._start_publisher(path, session)

    def _drain_publisher_output(self, path: str, session: int, process: QtCore.QProcess) -> None:
        data = bytes(process.readAllStandardOutput())
        record = self._publishers.get(path)
        if session != self._session or not record or record.get("process") is not process:
            return
        text = record["buffer"] + data[:MAX_OUTPUT_BYTES_PER_EVENT].decode("utf-8", "replace")
        lines = text.splitlines(keepends=True)
        record["buffer"] = ""
        if lines and not lines[-1].endswith(("\n", "\r")):
            record["buffer"] = lines.pop()[-4096:]
        now = time.monotonic()
        for raw in lines[:512]:
            line = raw.strip()
            if line.startswith(("out_time_ms=", "out_time_us=", "frame=")):
                value = line.partition("=")[2].strip()
                if value and value != "N/A" and value != "0":
                    record["last_progress"] = now
                    if record["stable_since"] is None:
                        record["stable_since"] = now
                    if record["state"] != "streaming":
                        record["state"] = "streaming"
                        self._emit_source_status()
            elif line.startswith("total_size="):
                value = line.partition("=")[2].strip()
                if value.isdigit():
                    current_size = int(value)
                    previous_size = int(record.get("last_reported_size", 0))
                    if current_size >= previous_size:
                        record["published_bytes"] += current_size - previous_size
                    record["last_reported_size"] = current_size
            elif line and not line.startswith("progress="):
                self._noisy_log.record(f"FFmpeg {path}: {line[:500]}")

    def _drain_media_output(self, session: int) -> None:
        if session != self._session or not self.mediamtx_process:
            return
        data = bytes(self.mediamtx_process.readAllStandardOutput())
        for line in data[:MAX_OUTPUT_BYTES_PER_EVENT].decode("utf-8", "replace").splitlines()[:256]:
            if line.strip():
                self._noisy_log.record(f"MediaMTX: {line.strip()[:500]}")

    def _watch(self) -> None:
        if self._stopping:
            return
        now = time.monotonic()
        for path, record in list(self._publishers.items()):
            process = record.get("process")
            if not process or process.state() != QtCore.QProcess.Running:
                continue
            last = record.get("last_progress")
            age = now - record["started_at"]
            stalled = (last is None and age > STARTUP_GRACE_SEC + STALL_TIMEOUT_SEC) or (
                last is not None and now - last > STALL_TIMEOUT_SEC
            )
            if stalled:
                logging.warning("Camera %s stalled; restarting publisher", path)
                record["state"] = "waiting"
                self._emit_source_status()
                self._terminate_process(process)
                continue
            stable_since = record.get("stable_since")
            if stable_since is not None and now - stable_since >= STABLE_STREAM_SEC:
                record["retry_index"] = 0

    def _terminate_process(self, process: QtCore.QProcess) -> None:
        if process.state() == QtCore.QProcess.NotRunning:
            return
        process.terminate()
        QtCore.QTimer.singleShot(PROCESS_STOP_DEADLINE_MS, lambda p=process: self._safe_kill(p))

    @staticmethod
    def _safe_kill(process: QtCore.QProcess) -> None:
        try:
            if process.state() != QtCore.QProcess.NotRunning:
                process.kill()
        except RuntimeError:
            # The process can finish and be deleteLater()'d before this deadline.
            return

    def _finish_stop(self) -> None:
        if any(record.get("process") for record in self._publishers.values()):
            return
        self.ffmpeg_processes = []
        self._publishers = {}
        self._config = None
        self._stopping = False
        self._noisy_log.flush()
        self.status_changed.emit()

    def _emit_source_status(self) -> None:
        self.source_status_changed.emit(self.source_statuses())

    def _write_mediamtx_cfg(self, paths: List[str], out_port: int = 8554) -> Path:
        config_dir = Path.home() / ".config" / "mediamtx"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "mediamtx.yml"
        lines: List[str] = [f"rtspAddress: :{int(out_port)}", "paths:"]
        for stream_path in paths:
            clean_path = self._normalize_path(stream_path)
            lines.extend((f"  {clean_path}:", "    source: publisher"))
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config_path

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path.strip().lstrip("/")
