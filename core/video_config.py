from pathlib import Path
from typing import List, Optional

from core.config_models import VideoConfig, VideoSource
from core.network_utils import command_exists, is_valid_network_port

VIDEO_TYPE_RTSP = "RTSP"
VIDEO_TYPE_WEBCAM = "Webcam"
RES_CHOICES = ["640x480", "1280x720", "1920x1080"]
FPS_CHOICES = ["10", "15", "20", "25", "30", "60"]

X264_PARAMS = (
    "nal-hrd=none:force-cfr=1:sliced-threads=1:sync-lookahead=0:rc-lookahead=0:bframes=0:ref=1"
)
RTSP_IO_TIMEOUT_US = 5_000_000
FFMPEG_PROGRESS_INTERVAL_SEC = 1


def looks_like_rtsp(url: str) -> bool:
    normalized_url = url.strip()
    return normalized_url.startswith("rtsp://") or normalized_url.startswith("rtsps://")


def active_video_sources(sources: List[VideoSource]) -> List[VideoSource]:
    return [source for source in sources if source.enabled]


def validate_video_config(config: VideoConfig, check_tools: bool = True) -> Optional[str]:
    if check_tools:
        if not Path(config.mediamtx_bin).exists():
            return f"mediamtx tidak ditemukan: {config.mediamtx_bin}"
        if not command_exists("ffmpeg"):
            return "ffmpeg tidak ditemukan"

    if not is_valid_network_port(config.out_port):
        return "Port RTSP invalid"

    active_sources = active_video_sources(config.sources)
    if not active_sources:
        return "Tidak ada source yang aktif"

    used_paths = set()
    for source in active_sources:
        if not source.out_path or any(character.isspace() for character in source.out_path):
            return "Output path wajib dan tidak boleh ada spasi"
        if source.out_path in used_paths:
            return f"Output path duplikat: {source.out_path}"
        used_paths.add(source.out_path)

        if source.vtype == VIDEO_TYPE_RTSP:
            input_text = source.input_text.strip()
            if not input_text:
                return f"RTSP input kosong untuk {source.out_path}"
            if not looks_like_rtsp(input_text):
                return f"RTSP input harus rtsp:// untuk {source.out_path}"
        else:
            device_path = source.input_text.strip()
            if not device_path or not Path(device_path).exists():
                return f"Webcam device tidak valid untuk {source.out_path}"

    if config.webcam_res not in RES_CHOICES:
        return "Resolusi webcam invalid"
    if str(config.webcam_fps) not in FPS_CHOICES:
        return "FPS webcam invalid"
    if not (200 <= int(config.global_bitrate_kbps) <= 20000):
        return "Bitrate invalid"

    return None


def build_ffmpeg_args(
    source: VideoSource,
    publish_url: str,
    bitrate_kbps: int,
    webcam_res: str,
    webcam_fps: int,
) -> List[str]:
    args: List[str] = [
        "-loglevel",
        "error",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-an",
    ]

    if source.vtype == VIDEO_TYPE_RTSP:
        gop = 30
        args += [
            "-rtsp_transport",
            "tcp",
            "-i",
            source.input_text.strip(),
        ]
    else:
        gop = int(webcam_fps)
        args += [
            "-f",
            "v4l2",
            "-input_format",
            "mjpeg",
            "-framerate",
            str(webcam_fps),
            "-video_size",
            webcam_res,
            "-i",
            source.input_text.strip(),
        ]

    args += [
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "baseline",
        "-g",
        str(gop),
        "-keyint_min",
        str(gop),
        "-sc_threshold",
        "0",
        "-bf",
        "0",
        "-b:v",
        f"{bitrate_kbps}k",
        "-maxrate",
        f"{bitrate_kbps}k",
        "-bufsize",
        f"{bitrate_kbps * 2}k",
        "-x264-params",
        X264_PARAMS,
        "-f",
        "rtsp",
        "-rtsp_transport",
        "tcp",
        publish_url,
    ]
    return args
