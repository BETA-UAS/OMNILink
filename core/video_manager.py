from pathlib import Path
from typing import List, Optional

from core.config_models import VideoConfig, VideoSource
from core.video_config import active_video_sources, build_ffmpeg_args, validate_video_config
from PyQt5 import QtCore


class VideoManager(QtCore.QObject):
    status_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mediamtx_process: Optional[QtCore.QProcess] = None
        self.ffmpeg_processes: List[QtCore.QProcess] = []

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

        active_sources = active_video_sources(config.sources)
        if not active_sources:
            return "Tidak ada source yang aktif"

        config_path = self._write_mediamtx_cfg([source.out_path for source in active_sources])

        self.mediamtx_process = QtCore.QProcess(self)
        self.mediamtx_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.mediamtx_process.finished.connect(lambda _code, _status: self.stop())
        self.mediamtx_process.start(config.mediamtx_bin, [str(config_path)])

        if not self.mediamtx_process.waitForStarted(2500):
            self.mediamtx_process.deleteLater()
            self.mediamtx_process = None
            return "mediamtx gagal start"

        def start_ffmpeg_publishers() -> None:
            if not self.mediamtx_process:
                return

            self.ffmpeg_processes = []
            for source in active_sources:
                publish_url = f"rtsp://127.0.0.1:{int(config.out_port)}/{source.out_path}"
                process = QtCore.QProcess(self)
                process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
                process.finished.connect(lambda _code, _status: self.stop())
                process.start(
                    "ffmpeg",
                    build_ffmpeg_args(
                        source=source,
                        publish_url=publish_url,
                        bitrate_kbps=int(config.global_bitrate_kbps),
                        webcam_res=config.webcam_res,
                        webcam_fps=int(config.webcam_fps),
                    ),
                )
                self.ffmpeg_processes.append(process)

            self.watchdog.start()
            self.status_changed.emit()

        QtCore.QTimer.singleShot(700, start_ffmpeg_publishers)
        self.status_changed.emit()
        return None

    def stop(self) -> None:
        self.watchdog.stop()

        for process in list(self.ffmpeg_processes):
            self._stop_process(process)

        if self.mediamtx_process:
            self._stop_process(self.mediamtx_process)

        for process in list(self.ffmpeg_processes):
            try:
                process.deleteLater()
            except RuntimeError:
                pass
        self.ffmpeg_processes = []

        if self.mediamtx_process:
            try:
                self.mediamtx_process.deleteLater()
            except RuntimeError:
                pass
        self.mediamtx_process = None
        self.status_changed.emit()

    def _watch(self) -> None:
        if self.mediamtx_process and self.mediamtx_process.state() == QtCore.QProcess.NotRunning:
            self.stop()
            return

        for process in list(self.ffmpeg_processes):
            if process.state() == QtCore.QProcess.NotRunning:
                self.stop()
                return

    def _write_mediamtx_cfg(self, paths: List[str]) -> Path:
        config_dir = Path.home() / ".config" / "mediamtx"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "mediamtx.yml"

        lines: List[str] = ["paths:"]
        for stream_path in paths:
            lines.append(f"  {stream_path}:")
            lines.append("    source: publisher")

        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config_path

    def _stop_process(self, process: QtCore.QProcess) -> None:
        try:
            process.terminate()
            if not process.waitForFinished(1200):
                process.kill()
                process.waitForFinished(1200)
        except RuntimeError:
            pass
