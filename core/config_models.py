from dataclasses import dataclass
from typing import List


@dataclass
class RouterConfig:
    in_mode: str
    listen_udp_port: int
    tcp_up_ip: str
    tcp_up_port: int
    tcp_server_port_ui: int
    targets_text: str
    primer_enabled: bool
    primer_up_ip: str
    primer_up_port: int
    use_sudo: bool
    espusr_enabled: bool
    espusr_mode: str
    espusr_ip: str
    espusr_port: int


@dataclass
class VideoSource:
    enabled: bool
    vtype: str
    input_text: str
    out_path: str


@dataclass
class VideoConfig:
    mediamtx_bin: str
    out_port: int
    sources: List[VideoSource]
    global_bitrate_kbps: int
