from pathlib import Path
from typing import List, Optional

from PyQt5 import QtCore

from core.config_models import VideoConfig, VideoSource
from core.video_config import active_video_sources, build_ffmpeg_args, validate_video_config


class VideoManager(QtCore.QObject):
    status_changed = QtCore.pyqtSignal()
    message = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.mediamtx_process: Optional[QtCore.QProcess] = None
        self.ffmpeg_processes: List[QtCore.QProcess] = []
        self._stopping = False

        self.watchdog = QtCore.QTimer(self)
        self.watchdog.setInterval(700)
        self.watchdog.timeout.connect(self._watch)

    def is_running(self) -> bool:
        return bool(
            self.mediamtx_process is not None
            or len(self.ffmpeg_processes) > 0
        )

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

        normalized_paths = [
            self._normalize_path(source.out_path)
            for source in active_sources
        ]

        config_path = self._write_mediamtx_cfg(
            normalized_paths,
            int(config.out_port),
        )

        self.message.emit(f"Starting MediaMTX on RTSP port {int(config.out_port)}")
        self.message.emit(f"MediaMTX config: {config_path}")

        self.mediamtx_process = QtCore.QProcess(self)
        self.mediamtx_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)

        self.mediamtx_process.readyReadStandardOutput.connect(
            lambda: self._log_process_output("mediamtx", self.mediamtx_process)
        )

        self.mediamtx_process.finished.connect(
            lambda code, status: self._process_finished("mediamtx", code, status)
        )

        self.mediamtx_process.start(config.mediamtx_bin, [str(config_path)])

        if not self.mediamtx_process.waitForStarted(2500):
            error_text = self.mediamtx_process.errorString()
            self.mediamtx_process.deleteLater()
            self.mediamtx_process = None
            return f"mediamtx gagal start: {error_text}"

        def start_ffmpeg_publishers() -> None:
            if not self.mediamtx_process:
                return

            if self.mediamtx_process.state() == QtCore.QProcess.NotRunning:
                self.message.emit("MediaMTX stopped before ffmpeg publishers started")
                self.stop()
                return

            self.ffmpeg_processes = []

            for source in active_sources:
                out_path = self._normalize_path(source.out_path)
                publish_url = f"rtsp://127.0.0.1:{int(config.out_port)}/{out_path}"

                args = build_ffmpeg_args(
                    source=source,
                    publish_url=publish_url,
                    bitrate_kbps=int(config.global_bitrate_kbps),
                    webcam_res=config.webcam_res,
                    webcam_fps=int(config.webcam_fps),
                )

                process = QtCore.QProcess(self)
                process.setProcessChannelMode(QtCore.QProcess.MergedChannels)

                process.readyReadStandardOutput.connect(
                    lambda p=process: self._log_process_output("ffmpeg", p)
                )

                process.finished.connect(
                    lambda code, status, path=out_path: self._process_finished(
                        f"ffmpeg:{path}",
                        code,
                        status,
                    )
                )

                self.message.emit(
                    f"Starting ffmpeg publisher: {source.input_text.strip()} -> {publish_url}"
                )

                process.start("ffmpeg", args)

                if not process.waitForStarted(2500):
                    self.message.emit(
                        f"ffmpeg gagal start untuk {out_path}: {process.errorString()}"
                    )
                    try:
                        process.deleteLater()
                    except RuntimeError:
                        pass
                    self.stop()
                    return

                self.ffmpeg_processes.append(process)

            self.watchdog.start()
            self.status_changed.emit()

        QtCore.QTimer.singleShot(700, start_ffmpeg_publishers)

        self.status_changed.emit()
        return None

    def stop(self) -> None:
        if self._stopping:
            return

        self._stopping = True
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
        self._stopping = False

        self.message.emit("Video manager stopped")
        self.status_changed.emit()

    def _watch(self) -> None:
        if self._stopping:
            return

        if self.mediamtx_process and self.mediamtx_process.state() == QtCore.QProcess.NotRunning:
            self.message.emit("Watchdog: MediaMTX is not running")
            self.stop()
            return

        for process in list(self.ffmpeg_processes):
            if process.state() == QtCore.QProcess.NotRunning:
                self.message.emit("Watchdog: ffmpeg publisher is not running")
                self.stop()
                return

    def _process_finished(self, name: str, code: int, status) -> None:
        if self._stopping:
            return

        self.message.emit(f"{name} stopped unexpectedly, exit code={code}, status={status}")
        self.stop()

    def _log_process_output(self, name: str, process: Optional[QtCore.QProcess]) -> None:
        if process is None:
            return

        try:
            output = bytes(process.readAllStandardOutput()).decode(
                "utf-8",
                errors="replace",
            ).strip()

            if output:
                self.message.emit(f"{name}: {output}")

        except RuntimeError:
            pass

    def _write_mediamtx_cfg(self, paths: List[str], out_port: int) -> Path:
        config_dir = Path.home() / ".config" / "mediamtx"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "mediamtx.yml"

        lines: List[str] = [
            f"rtspAddress: :{int(out_port)}",
            "paths:",
        ]

        for stream_path in paths:
            clean_path = self._normalize_path(stream_path)
            lines.append(f"  {clean_path}:")
            lines.append("    source: publisher")

        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config_path

    def _stop_process(self, process: QtCore.QProcess) -> None:
        try:
            if process.state() == QtCore.QProcess.NotRunning:
                return

            process.terminate()

            if not process.waitForFinished(1200):
                process.kill()
                process.waitForFinished(1200)

        except RuntimeError:
            pass

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path.strip().lstrip("/")