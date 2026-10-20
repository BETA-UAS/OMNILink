from pathlib import Path

from core.config_models import VideoConfig, VideoSource
from core.video_config import (
    VIDEO_TYPE_RTSP,
    build_ffmpeg_args,
    validate_video_config,
)
from core.video_manager import VideoManager
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


def test_validate_video_config_rejects_invalid_options():
    assert validate_video_config(video_config(out_port=0), check_tools=False) == "Port RTSP invalid"
    assert (
        validate_video_config(video_config(global_bitrate_kbps=100), check_tools=False)
        == "Bitrate invalid"
    )


def test_build_ffmpeg_args_matches_working_rtsp_pipeline():
    args = build_ffmpeg_args(
        source=video_config().sources[0],
        publish_url="rtsp://127.0.0.1:8554/cam1",
        bitrate_kbps=2500,
    )

    assert args[args.index("-progress") + 1] == "pipe:1"
    assert args[args.index("-threads") + 1] == "2"
    assert "-stimeout" not in args
    assert args[args.index("-rtsp_transport") + 1] == "tcp"
    assert args[-2:] == ["tcp", "rtsp://127.0.0.1:8554/cam1"]


def test_watchdog_does_not_stop_service_when_one_publisher_exits(monkeypatch):
    ensure_qt_app()
    manager = VideoManager()
    manager.mediamtx_process = FakeProcess(QtCore.QProcess.Running)
    manager.ffmpeg_processes = [
        FakeProcess(QtCore.QProcess.Running),
        FakeProcess(QtCore.QProcess.NotRunning),
    ]
    stopped = []
    monkeypatch.setattr(manager, "stop", lambda: stopped.append(True))

    manager._watch()

    assert stopped == []


def test_write_mediamtx_cfg_uses_simple_publisher_paths(tmp_path, monkeypatch):
    ensure_qt_app()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    manager = VideoManager()

    path = manager._write_mediamtx_cfg(["cam1", "cam2"])

    assert path.read_text(encoding="utf-8") == (
        "rtspAddress: :8554\n"
        "paths:\n  cam1:\n    source: publisher\n  cam2:\n    source: publisher\n"
    )
