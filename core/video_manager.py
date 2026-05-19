import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.config_models import VideoConfig, VideoSource
from core.video_config import (
    active_video_sources,
    build_ffmpeg_args,
    validate_video_config,
)
from PyQt5 import QtCore


@dataclass
class StreamRuntime:
    source: VideoSource
    process: Optional[QtCore.QProcess] = None
    restart_timer: Optional[QtCore.QTimer] = None
    restart_count: int = 0
    intentional_stop: bool = False
    last_started_at: float = field(default_factory=time.monotonic)
    last_progress_at: float = field(default_factory=time.monotonic)
    last_frame_count: Optional[int] = None
    last_out_time_us: Optional[int] = None
    progress_buffer: str = ""


class VideoManager(QtCore.QObject):
    status_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.mediamtx_process: Optional[QtCore.QProcess] = None

        # New design:
        # One runtime object per video source.
        # Each FFmpeg process can die and restart independently.
        self.streams: Dict[str, StreamRuntime] = {}

        self._config: Optional[VideoConfig] = None
        self._rtsp_port = 8554
        self._stopping = False

        self.watchdog = QtCore.QTimer(self)
        self.watchdog.setInterval(1000)
        self.watchdog.timeout.connect(self._watch)

        self._ffmpeg_restart_delay_ms = 1200
        self._ffmpeg_max_restart_delay_ms = 8000
        self._ffmpeg_start_grace_sec = 15.0
        self._ffmpeg_stall_timeout_sec = 10.0

    def is_running(self) -> bool:
        if self.mediamtx_process:
            return True

        for runtime in self.streams.values():
            if runtime.process:
                return True

        return False

    def start(
        self,
        mediamtx_bin: str,
        out_port: int,
        sources: List[VideoSource],
        global_bitrate_kbps: int,
        webcam_res: str,
        webcam_fps: int,
    ) -> Optional[str]:
        if self.is_running():
            return None

        config = VideoConfig(
            mediamtx_bin=mediamtx_bin,
            out_port=out_port,
            sources=sources,
            global_bitrate_kbps=global_bitrate_kbps,
            webcam_res=webcam_res,
            webcam_fps=webcam_fps,
        )

        validation_error = validate_video_config(config)
        if validation_error:
            return validation_error

        active_sources = active_video_sources(config.sources)
        if not active_sources:
            return "tidak ada video source aktif"

        self._config = config
        self._rtsp_port = int(config.out_port)
        self._stopping = False

        logging.info("Starting Video Manager")
        logging.info("Starting MediaMTX as shared RTSP server")
        logging.info("FFmpeg streams will run independently per source")

        config_path = self._write_mediamtx_cfg([source.out_path for source in active_sources])

        self.mediamtx_process = QtCore.QProcess(self)
        self.mediamtx_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.mediamtx_process.finished.connect(self._on_mediamtx_finished)
        self.mediamtx_process.readyReadStandardOutput.connect(self._log_mediamtx_output)

        self.mediamtx_process.start(config.mediamtx_bin, [str(config_path)])

        if not self.mediamtx_process.waitForStarted(2500):
            logging.error("MediaMTX failed to start")
            self.mediamtx_process.deleteLater()
            self.mediamtx_process = None
            self._config = None
            return "mediamtx gagal start"

        self.streams = {}

        for source in active_sources:
            key = self._stream_key(source)
            timer = QtCore.QTimer(self)
            timer.setSingleShot(True)

            runtime = StreamRuntime(
                source=source,
                process=None,
                restart_timer=timer,
                restart_count=0,
                intentional_stop=False,
            )

            timer.timeout.connect(lambda stream_key=key: self._restart_ffmpeg_stream(stream_key))

            self.streams[key] = runtime

        # Give MediaMTX a short time to bind the RTSP port before publishing.
        QtCore.QTimer.singleShot(700, self._start_all_ffmpeg_streams)

        self.watchdog.start()
        self.status_changed.emit()
        return None

    def stop(self) -> None:
        if not self.mediamtx_process and not self.streams:
            self.status_changed.emit()
            return

        logging.info("Stopping Video Manager")
        self._stopping = True
        self.watchdog.stop()

        for key in list(self.streams.keys()):
            self._stop_ffmpeg_stream(key, intentional=True)

        if self.mediamtx_process:
            self._stop_process(self.mediamtx_process, "MediaMTX")
            self.mediamtx_process.deleteLater()
            self.mediamtx_process = None

        self.streams = {}
        self._config = None
        self._stopping = False
        self.status_changed.emit()

    def _watch(self) -> None:
        if self._stopping:
            return

        if self.mediamtx_process:
            if self.mediamtx_process.state() == QtCore.QProcess.NotRunning:
                logging.warning("MediaMTX stopped unexpectedly")
                self.stop()
                return

        # Important:
        # Do not call self.stop() when FFmpeg dies.
        # Each stream owns its own restart lifecycle.
        for key, runtime in list(self.streams.items()):
            process = runtime.process

            if process is None:
                continue

            if process.state() == QtCore.QProcess.NotRunning:
                if not runtime.intentional_stop:
                    logging.warning(
                        "FFmpeg stream is not running, scheduling restart: %s",
                        key,
                    )
                    self._schedule_ffmpeg_restart(key)
                continue

            if self._ffmpeg_stream_is_stalled(runtime):
                idle_sec = time.monotonic() - runtime.last_progress_at
                logging.warning(
                    "FFmpeg stream stalled for %.1f seconds, restarting: %s",
                    idle_sec,
                    key,
                )
                self._replace_unhealthy_ffmpeg_stream(key, "progress timeout")

    def _write_mediamtx_cfg(self, paths: List[str]) -> Path:
        config_dir = Path.home() / ".config" / "mediamtx"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "mediamtx.yml"

        lines: List[str] = [
            f"rtspAddress: :{self._rtsp_port}",
            "paths:",
        ]

        for stream_path in paths:
            lines.append(f"  {stream_path}:")
            lines.append("    source: publisher")

        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config_path

    def _start_all_ffmpeg_streams(self) -> None:
        if self._stopping:
            return

        if not self._config:
            return

        if not self.mediamtx_process:
            logging.warning("Cannot start FFmpeg streams because MediaMTX is missing")
            return

        if self.mediamtx_process.state() != QtCore.QProcess.Running:
            logging.warning("Cannot start FFmpeg streams because MediaMTX is not running")
            return

        for key in list(self.streams.keys()):
            self._start_ffmpeg_stream(key)

        self.status_changed.emit()

    def _start_ffmpeg_stream(self, key: str) -> None:
        if self._stopping:
            return

        if not self._config:
            return

        runtime = self.streams.get(key)
        if not runtime:
            return

        existing_process = runtime.process
        if existing_process and existing_process.state() != QtCore.QProcess.NotRunning:
            return

        runtime.intentional_stop = False
        runtime.progress_buffer = ""
        runtime.last_started_at = time.monotonic()
        runtime.last_progress_at = runtime.last_started_at
        runtime.last_frame_count = None
        runtime.last_out_time_us = None

        publish_url = f"rtsp://127.0.0.1:{self._config.out_port}/{runtime.source.out_path}"

        args = build_ffmpeg_args(
            source=runtime.source,
            publish_url=publish_url,
            bitrate_kbps=int(self._config.global_bitrate_kbps),
            webcam_res=self._config.webcam_res,
            webcam_fps=int(self._config.webcam_fps),
        )

        process = QtCore.QProcess(self)
        process.setProcessChannelMode(QtCore.QProcess.SeparateChannels)

        process.finished.connect(
            lambda exit_code, exit_status, stream_key=key, proc=process: self._on_ffmpeg_finished(
                stream_key,
                proc,
                exit_code,
                exit_status,
            )
        )

        process.readyReadStandardOutput.connect(
            lambda stream_key=key, proc=process: self._read_ffmpeg_progress(stream_key, proc)
        )
        process.readyReadStandardError.connect(
            lambda stream_key=key, proc=process: self._log_ffmpeg_error(stream_key, proc)
        )

        runtime.process = process

        logging.info("Starting FFmpeg stream: %s", key)
        process.start("ffmpeg", args)

        if not process.waitForStarted(2500):
            logging.warning("FFmpeg failed to start: %s", key)
            self._cleanup_ffmpeg_process(key)
            self._schedule_ffmpeg_restart(key)
            return

        self.status_changed.emit()

    def _restart_ffmpeg_stream(self, key: str) -> None:
        if self._stopping:
            return

        if not self.mediamtx_process:
            return

        if self.mediamtx_process.state() != QtCore.QProcess.Running:
            return

        runtime = self.streams.get(key)
        if not runtime:
            return

        logging.info("Restarting FFmpeg stream: %s", key)

        self._cleanup_ffmpeg_process(key)
        self._start_ffmpeg_stream(key)

    def _schedule_ffmpeg_restart(self, key: str) -> None:
        if self._stopping:
            return

        runtime = self.streams.get(key)
        if not runtime:
            return

        if runtime.intentional_stop:
            return

        if not runtime.restart_timer:
            return

        if runtime.restart_timer.isActive():
            return

        runtime.restart_count += 1

        delay_ms = min(
            self._ffmpeg_restart_delay_ms * runtime.restart_count,
            self._ffmpeg_max_restart_delay_ms,
        )

        logging.warning(
            "Scheduling FFmpeg restart for %s in %d ms",
            key,
            delay_ms,
        )

        runtime.restart_timer.start(delay_ms)
        self.status_changed.emit()

    def _replace_unhealthy_ffmpeg_stream(self, key: str, reason: str) -> None:
        runtime = self.streams.get(key)
        if not runtime or runtime.intentional_stop:
            return

        logging.warning("Replacing unhealthy FFmpeg stream %s: %s", key, reason)
        runtime.intentional_stop = True
        self._cleanup_ffmpeg_process(key)
        runtime.intentional_stop = False
        self._schedule_ffmpeg_restart(key)

    def _ffmpeg_stream_is_stalled(self, runtime: StreamRuntime) -> bool:
        if runtime.intentional_stop:
            return False

        now = time.monotonic()
        if runtime.last_frame_count is None and runtime.last_out_time_us is None:
            return now - runtime.last_started_at > self._ffmpeg_start_grace_sec

        return now - runtime.last_progress_at > self._ffmpeg_stall_timeout_sec

    def _stop_ffmpeg_stream(self, key: str, intentional: bool) -> None:
        runtime = self.streams.get(key)
        if not runtime:
            return

        runtime.intentional_stop = intentional

        if runtime.restart_timer:
            runtime.restart_timer.stop()

        process = runtime.process
        if process:
            self._stop_process(process, f"FFmpeg {key}")
            process.deleteLater()
            runtime.process = None

        self.status_changed.emit()

    def _cleanup_ffmpeg_process(self, key: str) -> None:
        runtime = self.streams.get(key)
        if not runtime:
            return

        process = runtime.process
        if process:
            try:
                if process.state() != QtCore.QProcess.NotRunning:
                    process.kill()
                    process.waitForFinished(800)
            except RuntimeError:
                logging.exception("Error cleaning FFmpeg process: %s", key)

            process.deleteLater()
            runtime.process = None

    def _stop_process(self, process: QtCore.QProcess, process_name: str) -> None:
        try:
            process.terminate()

            if not process.waitForFinished(1200):
                process.kill()
                process.waitForFinished(1200)

        except RuntimeError:
            logging.exception("Error stopping %s process", process_name)

    def _stream_key(self, source: VideoSource) -> str:
        return str(source.out_path)

    def _on_mediamtx_finished(
        self,
        _exit_code: int,
        _exit_status: QtCore.QProcess.ExitStatus,
    ) -> None:
        if self._stopping:
            return

        logging.warning("MediaMTX stopped unexpectedly")

        # MediaMTX is the shared RTSP server.
        # If it dies, all FFmpeg publishers lose their target.
        # This is the only case where global stop is correct.
        self.stop()

    def _on_ffmpeg_finished(
        self,
        key: str,
        process: QtCore.QProcess,
        exit_code: int,
        exit_status: QtCore.QProcess.ExitStatus,
    ) -> None:
        if self._stopping:
            return

        runtime = self.streams.get(key)
        if not runtime:
            return

        if runtime.process is not process:
            return

        if runtime.intentional_stop:
            return

        logging.warning(
            "FFmpeg stream stopped unexpectedly: %s, exit_code=%s, exit_status=%s",
            key,
            exit_code,
            exit_status,
        )

        # Do not stop VideoManager.
        # Do not stop MediaMTX.
        # Do not stop other streams.
        self._cleanup_ffmpeg_process(key)
        self._schedule_ffmpeg_restart(key)

    def _log_mediamtx_output(self) -> None:
        process = self.mediamtx_process
        if not process:
            return

        try:
            output = (
                bytes(process.readAllStandardOutput())
                .decode(
                    "utf-8",
                    errors="replace",
                )
                .strip()
            )

            if output:
                logging.debug("MediaMTX: %s", output)

        except RuntimeError:
            pass

    def _read_ffmpeg_progress(self, key: str, process: QtCore.QProcess) -> None:
        runtime = self.streams.get(key)
        if not runtime or runtime.process is not process:
            return

        try:
            output = bytes(process.readAllStandardOutput()).decode(
                "utf-8",
                errors="replace",
            )
        except RuntimeError:
            return

        if not output:
            return

        text = runtime.progress_buffer + output
        complete = text.endswith(("\n", "\r"))
        lines = text.splitlines()

        if complete:
            runtime.progress_buffer = ""
        elif lines:
            runtime.progress_buffer = lines.pop()
        else:
            runtime.progress_buffer = text

        for line in lines:
            self._handle_ffmpeg_progress_line(key, runtime, line.strip())

    def _handle_ffmpeg_progress_line(
        self,
        key: str,
        runtime: StreamRuntime,
        line: str,
    ) -> None:
        if not line or "=" not in line:
            return

        name, value = line.split("=", 1)
        if name == "frame":
            self._record_numeric_progress(
                key,
                runtime,
                value,
                attribute_name="last_frame_count",
            )
        elif name in {"out_time_ms", "out_time_us"}:
            self._record_numeric_progress(
                key,
                runtime,
                value,
                attribute_name="last_out_time_us",
            )

    def _record_numeric_progress(
        self,
        key: str,
        runtime: StreamRuntime,
        raw_value: str,
        attribute_name: str,
    ) -> None:
        try:
            current_value = int(raw_value)
        except ValueError:
            return

        previous_value = getattr(runtime, attribute_name)
        if previous_value is not None and current_value <= previous_value:
            return

        setattr(runtime, attribute_name, current_value)
        if current_value <= 0:
            return

        runtime.last_progress_at = time.monotonic()
        runtime.restart_count = 0
        logging.debug("FFmpeg %s progress: %s=%d", key, attribute_name, current_value)

    def _log_ffmpeg_error(self, key: str, process: QtCore.QProcess) -> None:
        try:
            output = (
                bytes(process.readAllStandardError())
                .decode(
                    "utf-8",
                    errors="replace",
                )
                .strip()
            )

            if output:
                logging.debug("FFmpeg %s: %s", key, output)

        except RuntimeError:
            pass
