from pathlib import Path

from core.config_models import VideoConfig, VideoSource
from core.video_config import (
    RTSP_IO_TIMEOUT_US,
    VIDEO_TYPE_RTSP,
    VIDEO_TYPE_WEBCAM,
    build_ffmpeg_args,
    validate_video_config,
)
from core.video_manager import StreamRuntime, VideoManager
from PyQt5 import QtCore


class FakeProcess:
    def __init__(self, state):
        self._state = state

    def state(self):
        return self._state


def ensure_qt_app():
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QtCore.QCoreApplication([])
    return app


def video_config(**overrides):
    values = {
        "mediamtx_bin": "/usr/local/bin/mediamtx",
        "out_port": 8554,
        "sources": [
            VideoSource(
                enabled=True,
                vtype=VIDEO_TYPE_RTSP,
                input_text="rtsp://192.168.144.25:554",
                out_path="cam1",
            )
        ],
        "global_bitrate_kbps": 2500,
        "webcam_res": "1280x720",
        "webcam_fps": 30,
    }
    values.update(overrides)
    return VideoConfig(**values)


def test_validate_video_config_accepts_valid_rtsp_without_tool_checks():
    assert validate_video_config(video_config(), check_tools=False) is None


def test_validate_video_config_reports_missing_tools(monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda _path: False)

    assert (
        validate_video_config(video_config()) == "mediamtx tidak ditemukan: /usr/local/bin/mediamtx"
    )


def test_validate_video_config_reports_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda _path: True)
    monkeypatch.setattr("core.video_config.command_exists", lambda _cmd: False)

    assert validate_video_config(video_config()) == "ffmpeg tidak ditemukan"


def test_validate_video_config_rejects_duplicate_paths():
    config = video_config(
        sources=[
            VideoSource(True, VIDEO_TYPE_RTSP, "rtsp://192.168.144.25:554", "cam1"),
            VideoSource(True, VIDEO_TYPE_RTSP, "rtsp://192.168.144.26:554", "cam1"),
        ]
    )

    assert validate_video_config(config, check_tools=False) == "Output path duplikat: cam1"


def test_validate_video_config_rejects_bad_rtsp_url():
    config = video_config(
        sources=[VideoSource(True, VIDEO_TYPE_RTSP, "http://192.168.144.25:554", "cam1")]
    )

    assert validate_video_config(config, check_tools=False) == "RTSP input harus rtsp:// untuk cam1"


def test_validate_video_config_rejects_bad_webcam_path():
    config = video_config(
        sources=[VideoSource(True, VIDEO_TYPE_WEBCAM, "/dev/does-not-exist", "cam1")]
    )

    assert (
        validate_video_config(config, check_tools=False) == "Webcam device tidak valid untuk cam1"
    )


def test_validate_video_config_rejects_invalid_options():
    assert validate_video_config(video_config(out_port=0), check_tools=False) == "Port RTSP invalid"
    assert (
        validate_video_config(video_config(webcam_res="800x600"), check_tools=False)
        == "Resolusi webcam invalid"
    )
    assert (
        validate_video_config(video_config(webcam_fps=7), check_tools=False) == "FPS webcam invalid"
    )
    assert (
        validate_video_config(video_config(global_bitrate_kbps=100), check_tools=False)
        == "Bitrate invalid"
    )


def test_build_ffmpeg_args_adds_rtsp_timeout_and_progress_heartbeat():
    args = build_ffmpeg_args(
        source=video_config().sources[0],
        publish_url="rtsp://127.0.0.1:8554/cam1",
        bitrate_kbps=2500,
        webcam_res="1280x720",
        webcam_fps=30,
    )

    assert args[args.index("-progress") + 1] == "pipe:1"
    assert args[args.index("-stats_period") + 1] == "1"
    assert args[args.index("-stimeout") + 1] == str(RTSP_IO_TIMEOUT_US)


def test_progress_line_marks_stream_healthy_and_resets_backoff(monkeypatch):
    ensure_qt_app()
    manager = VideoManager()
    runtime = StreamRuntime(
        source=video_config().sources[0],
        restart_count=3,
        last_started_at=1.0,
        last_progress_at=1.0,
    )
    monkeypatch.setattr("core.video_manager.time.monotonic", lambda: 42.0)

    manager._handle_ffmpeg_progress_line("cam1", runtime, "frame=1")

    assert runtime.last_frame_count == 1
    assert runtime.last_progress_at == 42.0
    assert runtime.restart_count == 0


def test_watchdog_replaces_only_stalled_running_stream(monkeypatch):
    ensure_qt_app()
    manager = VideoManager()
    monkeypatch.setattr("core.video_manager.time.monotonic", lambda: 100.0)
    manager.mediamtx_process = FakeProcess(QtCore.QProcess.Running)
    manager._ffmpeg_stall_timeout_sec = 5.0
    manager.streams = {
        "cam1": StreamRuntime(
            source=VideoSource(True, VIDEO_TYPE_RTSP, "rtsp://192.168.144.25:554", "cam1"),
            process=FakeProcess(QtCore.QProcess.Running),
            last_started_at=80.0,
            last_progress_at=80.0,
            last_frame_count=10,
        ),
        "cam2": StreamRuntime(
            source=VideoSource(True, VIDEO_TYPE_RTSP, "rtsp://192.168.144.26:554", "cam2"),
            process=FakeProcess(QtCore.QProcess.Running),
            last_started_at=80.0,
            last_progress_at=99.0,
            last_frame_count=10,
        ),
    }
    replaced = []
    monkeypatch.setattr(
        manager,
        "_replace_unhealthy_ffmpeg_stream",
        lambda key, reason: replaced.append((key, reason)),
    )

    manager._watch()

    assert replaced == [("cam1", "progress timeout")]


def test_watchdog_schedules_dead_stream_without_stopping_manager(monkeypatch):
    ensure_qt_app()
    manager = VideoManager()
    manager.mediamtx_process = FakeProcess(QtCore.QProcess.Running)
    manager.streams = {
        "cam1": StreamRuntime(
            source=VideoSource(True, VIDEO_TYPE_RTSP, "rtsp://192.168.144.25:554", "cam1"),
            process=FakeProcess(QtCore.QProcess.NotRunning),
        ),
        "cam2": StreamRuntime(
            source=VideoSource(True, VIDEO_TYPE_RTSP, "rtsp://192.168.144.26:554", "cam2"),
            process=FakeProcess(QtCore.QProcess.Running),
        ),
    }
    scheduled = []
    monkeypatch.setattr(manager, "_schedule_ffmpeg_restart", lambda key: scheduled.append(key))
    monkeypatch.setattr(
        manager,
        "stop",
        lambda: (_ for _ in ()).throw(AssertionError("VideoManager.stop should not run")),
    )

    manager._watch()

    assert scheduled == ["cam1"]
