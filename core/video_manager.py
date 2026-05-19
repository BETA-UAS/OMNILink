import logging
from pathlib import Path
from typing import List, Optional

from core.config_models import VideoConfig, VideoSource
from core.video_config import (
    active_video_sources,
    build_ffmpeg_args,
    validate_video_config,
)
from PyQt5 import QtCore


class VideoManager(QtCore.QObject):
    status_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mediamtx_process: Optional[QtCore.QProcess] = None
        self.ffmpeg_processes: List[QtCore.QProcess] = []
        self._rtsp_port = 8554
        self._stopping = False
        self.watchdog = QtCore.QTimer(self)
        self.watchdog.setInterval(700)
        self.watchdog.timeout.connect(self._watch)

    def is_running(self) -> bool:
        return bool(self.mediamtx_process or self.ffmpeg_processes)

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

        self._rtsp_port = int(config.out_port)
        active_sources = active_video_sources(config.sources)
        logging.info("Starting Video Manager (MediaMTX + FFmpeg)")
        config_path = self._write_mediamtx_cfg([source.out_path for source in active_sources])

        self.mediamtx_process = QtCore.QProcess(self)
        self.mediamtx_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.mediamtx_process.finished.connect(self._on_mediamtx_finished)
        self.mediamtx_process.start(config.mediamtx_bin, [str(config_path)])

        if not self.mediamtx_process.waitForStarted(2500):
            self.mediamtx_process.deleteLater()
            self.mediamtx_process = None
            return "mediamtx gagal start"

        QtCore.QTimer.singleShot(700, lambda: self._start_ffmpeg_processes(config, active_sources))
        self.status_changed.emit()
        return None

    def stop(self) -> None:
        if not self.mediamtx_process and not self.ffmpeg_processes:
            self.status_changed.emit()
            return

        logging.info("Stopping Video Manager")
        self._stopping = True
        self.watchdog.stop()

        for ffmpeg_process in list(self.ffmpeg_processes):
            self._stop_process(ffmpeg_process, "FFmpeg")

        if self.mediamtx_process:
            self._stop_process(self.mediamtx_process, "MediaMTX")

        self._clear_processes()
        self._stopping = False
        self.status_changed.emit()

    def _watch(self) -> None:
        if self.mediamtx_process and self.mediamtx_process.state() == QtCore.QProcess.NotRunning:
            logging.warning("MediaMTX stopped unexpectedly.")
            self.stop()
            return

        for ffmpeg_process in list(self.ffmpeg_processes):
            if ffmpeg_process.state() == QtCore.QProcess.NotRunning:
                logging.warning("An FFmpeg stream stopped unexpectedly.")
                self.stop()
                return

    def _write_mediamtx_cfg(self, paths: List[str]) -> Path:
        config_dir = Path.home() / ".config" / "mediamtx"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "mediamtx.yml"

        lines: List[str] = [f"rtspAddress: :{self._rtsp_port}", "paths:"]
        for stream_path in paths:
            lines.append(f"  {stream_path}:")
            lines.append("    source: publisher")
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config_path

    def _start_ffmpeg_processes(
        self,
        config: VideoConfig,
        sources: List[VideoSource],
    ) -> None:
        if not self.mediamtx_process:
            return

        self.ffmpeg_processes = []
        for source in sources:
            publish_url = f"rtsp://127.0.0.1:{config.out_port}/{source.out_path}"
            ffmpeg_process = QtCore.QProcess(self)
            ffmpeg_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
            ffmpeg_process.finished.connect(self._on_ffmpeg_finished)

            args = build_ffmpeg_args(
                source=source,
                publish_url=publish_url,
                bitrate_kbps=int(config.global_bitrate_kbps),
                webcam_res=config.webcam_res,
                webcam_fps=int(config.webcam_fps),
            )

            logging.info("Starting FFmpeg for stream: %s", source.out_path)
            ffmpeg_process.start("ffmpeg", args)
            self.ffmpeg_processes.append(ffmpeg_process)

        self.watchdog.start()
        self.status_changed.emit()

    def _stop_process(self, process: QtCore.QProcess, process_name: str) -> None:
        try:
            process.terminate()
            if not process.waitForFinished(1200):
                process.kill()
                process.waitForFinished(1200)
        except RuntimeError:
            logging.exception("Error stopping %s process", process_name)

    def _clear_processes(self) -> None:
        for ffmpeg_process in list(self.ffmpeg_processes):
            ffmpeg_process.deleteLater()
        self.ffmpeg_processes = []

        if self.mediamtx_process:
            self.mediamtx_process.deleteLater()
        self.mediamtx_process = None

    def _on_mediamtx_finished(
        self,
        _exit_code: int,
        _exit_status: QtCore.QProcess.ExitStatus,
    ) -> None:
        if not self._stopping:
            logging.warning("MediaMTX stopped unexpectedly.")
            self.stop()

    def _on_ffmpeg_finished(
        self,
        _exit_code: int,
        _exit_status: QtCore.QProcess.ExitStatus,
    ) -> None:
        if not self._stopping:
            logging.warning("An FFmpeg stream stopped unexpectedly.")
            self.stop()
