from pathlib import Path

from core.config_models import VideoConfig, VideoSource
from core.video_config import (
    VIDEO_TYPE_RTSP,
    VIDEO_TYPE_WEBCAM,
    validate_video_config,
)


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
