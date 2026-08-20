from pathlib import Path
from typing import List, Optional

from core.config_models import VideoConfig, VideoSource
from core.network_utils import command_exists, is_valid_network_port

VIDEO_TYPE_RTSP = "RTSP"
VIDEO_TYPE_WEBCAM = "Webcam"

RES_CHOICES = ["640x480", "1280x720", "1920x1080"]
FPS_CHOICES = ["10", "15", "20", "25", "30", "60"]

X264_PARAMS = (
    "nal-hrd=none:"
    "force-cfr=1:"
    "sliced-threads=1:"
    "sync-lookahead=0:"
    "rc-lookahead=0:"
    "bframes=0:"
    "ref=1"
)

RTSP_IO_TIMEOUT_US = 5_000_000
FFMPEG_PROGRESS_INTERVAL_SEC = 1


def looks_like_rtsp(url: str) -> bool:
    normalized_url = url.strip().lower()
    return normalized_url.startswith("rtsp://") or normalized_url.startswith("rtsps://")


def normalize_output_path(path: str) -> str:
    return path.strip().lstrip("/")


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
        out_path = normalize_output_path(source.out_path)

        if not out_path:
            return "Output path wajib diisi"

        if any(character.isspace() for character in out_path):
            return f"Output path tidak boleh ada spasi: {out_path}"

        if "/" in out_path:
            return f"Output path tidak boleh memakai slash: {out_path}"

        if out_path in used_paths:
            return f"Output path duplikat: {out_path}"

        used_paths.add(out_path)

        if source.vtype == VIDEO_TYPE_RTSP:
            input_text = source.input_text.strip()

            if not input_text:
                return f"RTSP input kosong untuk {out_path}"

            if not looks_like_rtsp(input_text):
                return f"RTSP input harus rtsp:// untuk {out_path}"

        elif source.vtype == VIDEO_TYPE_WEBCAM:
            device_path = source.input_text.strip()

            if not device_path:
                return f"Webcam device kosong untuk {out_path}"

            if not Path(device_path).exists():
                return f"Webcam device tidak valid untuk {out_path}"

        else:
            return f"Tipe video tidak valid untuk {out_path}: {source.vtype}"

    if config.webcam_res not in RES_CHOICES:
        return "Resolusi webcam invalid"

    if str(config.webcam_fps) not in FPS_CHOICES:
        return "FPS webcam invalid"

    try:
        bitrate_kbps = int(config.global_bitrate_kbps)
    except (TypeError, ValueError):
        return "Bitrate invalid"

    if not (200 <= bitrate_kbps <= 20000):
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
        "-hide_banner",
        "-loglevel",
        "warning",
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
            "-timeout",
            str(RTSP_IO_TIMEOUT_US),
            "-i",
            source.input_text.strip(),
        ]

    elif source.vtype == VIDEO_TYPE_WEBCAM:
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

    else:
        raise ValueError(f"Unsupported video source type: {source.vtype}")

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
        f"{int(bitrate_kbps)}k",
        "-maxrate",
        f"{int(bitrate_kbps)}k",
        "-bufsize",
        f"{int(bitrate_kbps) * 2}k",
        "-x264-params",
        X264_PARAMS,
        "-f",
        "rtsp",
        "-rtsp_transport",
        "tcp",
        publish_url,
    ]

    return args