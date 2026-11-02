from pathlib import Path
from typing import List, Optional

from core.config_models import VideoConfig, VideoSource
from core.network_utils import command_exists, is_valid_network_port

VIDEO_TYPE_RTSP = "RTSP"
MAIN_CAMERA_URLS = (
    "rtsp://192.168.144.25:8554/video1",  # MT11
    "rtsp://192.168.144.25:554/",  # Viewpro
)

X264_PARAMS = (
    "nal-hrd=none:force-cfr=1:sliced-threads=1:sync-lookahead=0:rc-lookahead=0:bframes=0:ref=1"
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

        else:
            return f"Tipe video tidak valid untuk {out_path}: {source.vtype}"

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
    passthrough: bool = False,
) -> List[str]:
    args: List[str] = [
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostats",
        "-progress",
        "pipe:1",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-an",
    ]

    if source.vtype != VIDEO_TYPE_RTSP:
        raise ValueError(f"Unsupported video source type: {source.vtype}")
    gop = 30
    args += [
        "-rtsp_transport",
        "tcp",
        "-timeout",
        str(RTSP_IO_TIMEOUT_US),
        "-i",
        source.input_text.strip(),
    ]

    if passthrough and source.vtype == VIDEO_TYPE_RTSP:
        args += ["-c:v", "copy"]
    else:
        args += [
            "-c:v",
            "libx264",
            "-threads",
            "2",
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
        ]

    args += [
        "-f",
        "rtsp",
        "-rtsp_transport",
        "tcp",
        publish_url,
    ]

    return args
