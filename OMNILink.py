#!/usr/bin/env python3
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", message="sipPyTypeDict\\(\\) is deprecated.*", category=DeprecationWarning)

import os
import re
import sys
import socket
import struct
import subprocess
import tempfile
import time
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets


# =========================
# Helpers
# =========================

def which(cmd: str) -> Optional[str]:
    for p in os.environ.get("PATH", "").split(os.pathsep):
        full = os.path.join(p, cmd)
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
    return None


def has_cmd(cmd: str) -> bool:
    return subprocess.call(["bash", "-lc", f"command -v {cmd} >/dev/null 2>&1"]) == 0


def is_valid_ip(ip: str) -> bool:
    parts = ip.strip().split(".")
    if len(parts) != 4:
        return False
    try:
        nums = [int(x) for x in parts]
    except ValueError:
        return False
    return all(0 <= n <= 255 for n in nums)


def is_valid_port(p: int) -> bool:
    return 1 <= p <= 65535


def looks_like_rtsp(url: str) -> bool:
    u = url.strip()
    return u.startswith("rtsp://") or u.startswith("rtsps://")


def list_video_devices() -> List[str]:
    devs: List[str] = []
    for p in sorted(Path("/dev").glob("video*"), key=lambda x: int(re.sub(r"\D", "", x.name) or "9999")):
        devs.append(f"/dev/{p.name}")
    return devs


def parse_ss() -> str:
    ss_bin = which("ss")
    if not ss_bin:
        return ""
    try:
        return subprocess.check_output([ss_bin, "-lunpt"], stderr=subprocess.STDOUT, text=True)
    except Exception:
        return ""


def port_listening(ss_text: str, proto: str, port: int) -> bool:
    if not ss_text:
        return False
    needle = f":{port}"
    low = ss_text.lower()
    if proto.lower() == "tcp":
        return ("tcp" in low) and (needle in ss_text)
    if proto.lower() == "udp":
        return ("udp" in low) and (needle in ss_text)
    return False


def find_free_tcp_port(preferred: int, tries: int = 40) -> int:
    if preferred == 0:
        return 0
    ss_text = parse_ss()
    port = preferred
    for _ in range(max(1, tries)):
        if not port_listening(ss_text, "tcp", port):
            return port
        port += 1
    return preferred


def set_status_label(lbl: QtWidgets.QLabel, text: str, ok: bool) -> None:
    lbl.setText(text)
    if ok:
        lbl.setStyleSheet("font-weight:800; color: rgb(0, 150, 0);")
    else:
        lbl.setStyleSheet("font-weight:800; color: rgb(180, 60, 60);")


def ping_host(ip: str, timeout_sec: int = 1) -> bool:
    ping_bin = which("ping")
    if not ping_bin:
        return False

    try:
        r = subprocess.run(
            [ping_bin, "-c", "1", "-W", str(timeout_sec), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_sec + 1,
        )
        return r.returncode == 0
    except Exception:
        return False


def get_ip_addr_output() -> str:
    ip_bin = which("ip")
    if not ip_bin:
        return ""
    try:
        return subprocess.check_output([ip_bin, "-4", "addr", "show"], stderr=subprocess.STDOUT, text=True)
    except Exception:
        return ""


def get_preferred_ethernet_ip() -> str:
    """
    Pilih IP dari interface ethernet yang berada di subnet 192.168.144.x.
    Jangan ambil dari wifi.
    """
    txt = get_ip_addr_output()
    if not txt:
        return "127.0.0.1"

    current_if = ""
    candidates_144: List[Tuple[str, str]] = []
    candidates_eth: List[Tuple[str, str]] = []

    for line in txt.splitlines():
        if re.match(r"^\d+:\s", line):
            m = re.match(r"^\d+:\s*([^:]+):", line)
            current_if = m.group(1) if m else ""
            continue

        m_ip = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/\d+", line)
        if not m_ip or not current_if:
            continue

        ip = m_ip.group(1)
        if ip.startswith("127."):
            continue

        low_if = current_if.lower()
        is_wifi = (
            low_if.startswith("wl")
            or "wifi" in low_if
            or "wlan" in low_if
            or "wireless" in low_if
        )
        is_eth_like = (
            low_if.startswith("en")
            or low_if.startswith("eth")
            or "ether" in low_if
        )

        if is_wifi:
            continue

        if ip.startswith("192.168.144."):
            candidates_144.append((current_if, ip))
        elif is_eth_like:
            candidates_eth.append((current_if, ip))

    if candidates_144:
        return candidates_144[0][1]
    if candidates_eth:
        return candidates_eth[0][1]
    return "127.0.0.1"


# =========================
# Video (MediaMTX + FFmpeg)
# =========================

MEDIAMTX_BIN_DEFAULT = "/usr/local/bin/mediamtx"

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

VIDEO_TYPE_RTSP = "RTSP"
VIDEO_TYPE_WEBCAM = "Webcam"


@dataclass
class VideoSource:
    enabled: bool
    vtype: str
    input_text: str
    out_path: str


class VideoManager(QtCore.QObject):
    status_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mt: Optional[QtCore.QProcess] = None
        self.ff_procs: List[QtCore.QProcess] = []
        self.watchdog = QtCore.QTimer(self)
        self.watchdog.setInterval(700)
        self.watchdog.timeout.connect(self._watch)

    def is_running(self) -> bool:
        return bool(self.mt or self.ff_procs)

    def _watch(self) -> None:
        if self.mt and self.mt.state() == QtCore.QProcess.NotRunning:
            self.stop()
            return
        for ff in list(self.ff_procs):
            if ff.state() == QtCore.QProcess.NotRunning:
                self.stop()
                return

    def _write_mediamtx_cfg(self, paths: List[str]) -> Path:
        cfg_dir = Path.home() / ".config" / "mediamtx"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "mediamtx.yml"

        lines: List[str] = ["paths:"]
        for p in paths:
            lines.append(f"  {p}:")
            lines.append("    source: publisher")
        cfg_path.write_text("\n".join(lines) + "\n")
        return cfg_path

    def start(
        self,
        mediamtx_bin: str,
        out_port: int,
        sources: List[VideoSource],
        global_bitrate_kbps: int,
        webcam_res: str,
        webcam_fps: int,
    ) -> Optional[str]:
        if self.mt or self.ff_procs:
            return None

        if not Path(mediamtx_bin).exists():
            return f"mediamtx tidak ditemukan: {mediamtx_bin}"
        if not has_cmd("ffmpeg"):
            return "ffmpeg tidak ditemukan"
        if not is_valid_port(out_port):
            return "Port RTSP invalid"

        active = [s for s in sources if s.enabled]
        if not active:
            return "Tidak ada source yang aktif"

        used = set()
        for s in active:
            if not s.out_path or any(c.isspace() for c in s.out_path):
                return "Output path wajib dan tidak boleh ada spasi"
            if s.out_path in used:
                return f"Output path duplikat: {s.out_path}"
            used.add(s.out_path)

            if s.vtype == VIDEO_TYPE_RTSP:
                if not s.input_text.strip():
                    return f"RTSP input kosong untuk {s.out_path}"
                if not looks_like_rtsp(s.input_text.strip()):
                    return f"RTSP input harus rtsp:// untuk {s.out_path}"
            else:
                dev = s.input_text.strip()
                if not dev or not Path(dev).exists():
                    return f"Webcam device tidak valid untuk {s.out_path}"

        if webcam_res not in RES_CHOICES:
            return "Resolusi webcam invalid"
        if str(webcam_fps) not in FPS_CHOICES:
            return "FPS webcam invalid"
        if not (200 <= global_bitrate_kbps <= 20000):
            return "Bitrate invalid"

        cfg_path = self._write_mediamtx_cfg([s.out_path for s in active])

        self.mt = QtCore.QProcess(self)
        self.mt.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.mt.finished.connect(lambda _c, _s: self.stop())
        self.mt.start(mediamtx_bin, [str(cfg_path)])

        if not self.mt.waitForStarted(2500):
            self.mt = None
            return "mediamtx gagal start"

        def start_ff_all():
            if not self.mt:
                return

            self.ff_procs = []
            for s in active:
                publish_url = f"rtsp://127.0.0.1:{out_port}/{s.out_path}"
                ff = QtCore.QProcess(self)
                ff.setProcessChannelMode(QtCore.QProcess.MergedChannels)
                ff.finished.connect(lambda _c, _st: self.stop())

                args: List[str] = [
                    "-loglevel", "error",
                    "-fflags", "nobuffer",
                    "-flags", "low_delay",
                    "-an",
                ]

                if s.vtype == VIDEO_TYPE_RTSP:
                    gop = 30
                    args += [
                        "-rtsp_transport", "tcp",
                        "-i", s.input_text.strip(),
                    ]
                else:
                    gop = int(webcam_fps)
                    args += [
                        "-f", "v4l2",
                        "-input_format", "mjpeg",
                        "-framerate", str(webcam_fps),
                        "-video_size", webcam_res,
                        "-i", s.input_text.strip(),
                    ]

                br = int(global_bitrate_kbps)
                args += [
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "zerolatency",
                    "-pix_fmt", "yuv420p",
                    "-profile:v", "baseline",
                    "-g", str(gop),
                    "-keyint_min", str(gop),
                    "-sc_threshold", "0",
                    "-bf", "0",
                    "-b:v", f"{br}k",
                    "-maxrate", f"{br}k",
                    "-bufsize", f"{br * 2}k",
                    "-x264-params", X264_PARAMS,
                    "-f", "rtsp",
                    "-rtsp_transport", "tcp",
                    publish_url,
                ]

                ff.start("ffmpeg", args)
                self.ff_procs.append(ff)

            self.watchdog.start()
            self.status_changed.emit()

        QtCore.QTimer.singleShot(700, start_ff_all)
        self.status_changed.emit()
        return None

    def stop(self) -> None:
        self.watchdog.stop()

        for ff in list(self.ff_procs):
            try:
                ff.terminate()
                if not ff.waitForFinished(1200):
                    ff.kill()
                    ff.waitForFinished(1200)
            except Exception:
                pass

        if self.mt:
            try:
                self.mt.terminate()
                if not self.mt.waitForFinished(1200):
                    self.mt.kill()
                    self.mt.waitForFinished(1200)
            except Exception:
                pass

        for ff in list(self.ff_procs):
            try:
                ff.deleteLater()
            except Exception:
                pass
        self.ff_procs = []

        if self.mt:
            try:
                self.mt.deleteLater()
            except Exception:
                pass
        self.mt = None
        self.status_changed.emit()


# =========================
# MAVLink Router
# =========================

def x25_crc_init() -> int:
    return 0xFFFF


def x25_crc_accumulate(crc: int, b: int) -> int:
    tmp = (b ^ (crc & 0xFF)) & 0xFF
    tmp = (tmp ^ ((tmp << 4) & 0xFF)) & 0xFF
    crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF
    return crc


def x25_crc_accumulate_buf(crc: int, data: bytes) -> int:
    for bb in data:
        crc = x25_crc_accumulate(crc, bb)
    return crc


def mavlink_v1_heartbeat_packet(seq: int) -> bytes:
    stx = 0xFE
    payload_len = 9
    msgid = 0
    sysid = 255
    compid = 190
    mav_type = 6
    autopilot = 8
    base_mode = 0
    system_status = 0

    payload = struct.pack("<I", 0)
    payload += struct.pack("<BBBBB", mav_type, autopilot, base_mode, system_status, 3)
    header = struct.pack("<BBBBB", payload_len, seq & 0xFF, sysid, compid, msgid)

    crc = x25_crc_init()
    crc = x25_crc_accumulate_buf(crc, header)
    crc = x25_crc_accumulate_buf(crc, payload)
    crc = x25_crc_accumulate(crc, 50)

    return bytes([stx]) + header + payload + struct.pack("<H", crc)


class UdpPrimer(QtCore.QThread):
    def __init__(self, listen_port: int, upstream_ip: str, upstream_port: int, parent=None):
        super().__init__(parent)
        self.listen_port = int(listen_port)
        self.upstream_ip = upstream_ip
        self.upstream_port = int(upstream_port)

    def run(self):
        s: Optional[socket.socket] = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", self.listen_port))
            seq = 0
            for _ in range(3):
                s.sendto(mavlink_v1_heartbeat_packet(seq), (self.upstream_ip, self.upstream_port))
                seq = (seq + 1) & 0xFF
                time.sleep(0.2)
        except Exception:
            pass
        finally:
            try:
                if s:
                    s.close()
            except Exception:
                pass


class RouterManager(QtCore.QObject):
    status_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.router_bin = which("mavlink-routerd") or "mavlink-routerd"
        self.proc = QtCore.QProcess(self)
        self.proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.proc.stateChanged.connect(lambda _st: self.status_changed.emit())

        self._effective_tcp_port = 5760
        self._primer: Optional[UdpPrimer] = None

    def is_running(self) -> bool:
        return self.proc.state() == QtCore.QProcess.Running

    def effective_tcp_port(self) -> int:
        return int(self._effective_tcp_port)

    def _parse_targets(self, text: str) -> List[Tuple[str, int]]:
        items: List[Tuple[str, int]] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if ":" not in line:
                raise ValueError(f"Target invalid: {line} (gunakan IP:PORT)")
            ip, ps = line.rsplit(":", 1)
            ip = ip.strip()
            ps = ps.strip()
            if not is_valid_ip(ip):
                raise ValueError(f"Target IP invalid: {ip}")
            if not ps.isdigit():
                raise ValueError(f"Target port invalid: {line}")
            port = int(ps)
            if not is_valid_port(port):
                raise ValueError(f"Target port invalid: {line}")
            items.append((ip, port))
        if not items:
            raise ValueError("Target kosong")
        return items

    def _build_config_text(
        self,
        tcp_server_port_ui: int,
        in_mode: str,
        listen_udp_port: int,
        tcp_up_ip: str,
        tcp_up_port: int,
        targets_text: str,
        espusr_enabled: bool,
        espusr_mode: str,
        espusr_ip: str,
        espusr_port: int,
    ) -> str:
        tcp_port = find_free_tcp_port(int(tcp_server_port_ui))
        self._effective_tcp_port = tcp_port

        targets = self._parse_targets(targets_text)

        lines: List[str] = []
        lines.append("[General]")
        lines.append(f"TcpServerPort={tcp_port}")
        lines.append("ReportStats=false")
        lines.append("")

        if in_mode == "UDP":
            if not is_valid_port(listen_udp_port):
                raise ValueError("Listen UDP port invalid")
            lines += ["[UdpEndpoint input]", "Mode=Server", "Address=0.0.0.0", f"Port={listen_udp_port}", ""]
        else:
            if not is_valid_ip(tcp_up_ip):
                raise ValueError("TCP upstream IP invalid")
            if not is_valid_port(tcp_up_port):
                raise ValueError("TCP upstream port invalid")
            lines += ["[TcpEndpoint input]", "Mode=Client", f"Address={tcp_up_ip}", f"Port={tcp_up_port}", ""]

        seen = set()
        i = 1
        for ip, port in targets:
            key = (ip, port)
            if key in seen:
                continue
            seen.add(key)
            lines += [f"[UdpEndpoint gcs{i}]", "Mode=Normal", f"Address={ip}", f"Port={port}", ""]
            i += 1

        if espusr_enabled:
            if not is_valid_ip(espusr_ip):
                raise ValueError("ESP/USR IP invalid")
            if not is_valid_port(espusr_port):
                raise ValueError("ESP/USR port invalid")

            if espusr_mode == "TCP":
                lines += ["[TcpEndpoint espusr]", "Mode=Client", f"Address={espusr_ip}", f"Port={espusr_port}", ""]
            else:
                lines += ["[UdpEndpoint espusr]", "Mode=Normal", f"Address={espusr_ip}", f"Port={espusr_port}", ""]

        return "\n".join(lines)

    def start(
        self,
        in_mode: str,
        listen_udp_port: int,
        tcp_up_ip: str,
        tcp_up_port: int,
        tcp_server_port_ui: int,
        targets_text: str,
        primer_enabled: bool,
        primer_up_ip: str,
        primer_up_port: int,
        use_sudo: bool,
        espusr_enabled: bool,
        espusr_mode: str,
        espusr_ip: str,
        espusr_port: int,
    ) -> Optional[str]:
        if self.proc.state() == QtCore.QProcess.Running:
            return None

        if not which("mavlink-routerd") and self.router_bin == "mavlink-routerd":
            return "mavlink-routerd tidak ditemukan"

        try:
            conf_text = self._build_config_text(
                tcp_server_port_ui=tcp_server_port_ui,
                in_mode=in_mode,
                listen_udp_port=listen_udp_port,
                tcp_up_ip=tcp_up_ip,
                tcp_up_port=tcp_up_port,
                targets_text=targets_text,
                espusr_enabled=espusr_enabled,
                espusr_mode=espusr_mode,
                espusr_ip=espusr_ip,
                espusr_port=espusr_port,
            )
        except Exception as e:
            return str(e)

        fd, conf_path = tempfile.mkstemp(prefix="omni-link-router-", suffix=".conf")
        os.close(fd)
        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(conf_text)

        if in_mode == "UDP" and primer_enabled:
            if is_valid_ip(primer_up_ip) and is_valid_port(primer_up_port) and is_valid_port(listen_udp_port):
                self._primer = UdpPrimer(listen_port=listen_udp_port, upstream_ip=primer_up_ip, upstream_port=primer_up_port)
                self._primer.start()
                self._primer.wait(1200)
                self._primer = None

        cmd = self.router_bin
        args = ["-c", conf_path]
        if use_sudo:
            cmd = "sudo"
            args = [self.router_bin] + args

        self.proc.start(cmd, args)
        if not self.proc.waitForStarted(1500):
            return "Gagal menjalankan mavlink-routerd"

        self.status_changed.emit()
        return None

    def stop(self) -> None:
        if self.proc.state() != QtCore.QProcess.Running:
            return
        self.proc.terminate()
        if not self.proc.waitForFinished(1500):
            self.proc.kill()
            self.proc.waitForFinished(1500)
        self.status_changed.emit()


# =========================
# Ping Worker
# =========================

class PingWorker(QtCore.QObject):
    result_ready = QtCore.pyqtSignal(dict)
    finished = QtCore.pyqtSignal()

    def __init__(self, devices: List[Tuple[str, str]], parent=None):
        super().__init__(parent)
        self.devices = devices

    @QtCore.pyqtSlot()
    def run(self) -> None:
        results: Dict[str, bool] = {}
        for name, ip in self.devices:
            results[name] = ping_host(ip, timeout_sec=1)
        self.result_ready.emit(results)
        self.finished.emit()


# =========================
# Preset Constants
# =========================

TEL_TARGETS = {
    "Instructor": "192.168.144.120",
    "Student": "192.168.144.125",
    "Instrument-1": "192.168.144.200",
}
TEL_DEFAULT_TARGET_PORT = 14550

TEL_INPUT_PRESETS = {
    "HM30": {
        "mode": "UDP",
        "listen_udp": 19856,
        "primer_enabled": True,
        "primer_ip": "192.168.144.12",
        "primer_port": 19856,
        "tcp_up_ip": "",
        "tcp_up_port": 0,
    },
    "IVCAN": {
        "mode": "TCP",
        "listen_udp": 19856,
        "primer_enabled": False,
        "primer_ip": "0.0.0.0",
        "primer_port": 1,
        "tcp_up_ip": "192.168.144.11",
        "tcp_up_port": 20001,
    },
}

PING_DEVICES = [
    ("Instructor", "192.168.144.120"),
    ("Student", "192.168.144.125"),
    ("Instrument-1", "192.168.144.200"),
    ("GDT", "192.168.144.12"),
    ("ADT", "192.168.144.11"),
    ("Main-Cam", "192.168.144.25"),
    ("Tail-Cam", "192.168.144.26"),
]


# =========================
# UI
# =========================

class MainWindow(QtWidgets.QMainWindow):

    def _build_status_dot(self, name: str, ip: str) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("statusCard")
        card.setMinimumHeight(46)
        card.setMaximumHeight(46)
        card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        lay = QtWidgets.QHBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        dot = QtWidgets.QLabel("●")
        dot.setAlignment(QtCore.Qt.AlignCenter)
        dot.setFixedWidth(18)
        dot.setStyleSheet("font-size: 16px; font-weight: 900; color: rgb(180, 60, 60);")

        text_box = QtWidgets.QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(0)

        name_lbl = QtWidgets.QLabel(name)
        name_lbl.setStyleSheet("font-weight: 800; font-size: 12px;")

        ip_lbl = QtWidgets.QLabel(ip)
        ip_lbl.setStyleSheet("color: rgb(110,110,110); font-size: 10px;")

        text_box.addWidget(name_lbl)
        text_box.addWidget(ip_lbl)

        lay.addWidget(dot)
        lay.addLayout(text_box, 1)

        self.ping_labels[name] = dot
        self.ping_texts[name] = name_lbl
        return card
    
    def resizeEvent(self, e: QtGui.QResizeEvent):
        super().resizeEvent(e)
        if hasattr(self, "pg_status"):
            self._relayout_ping_cards()
        
    def _update_video_table_height(self) -> None:
        header_h = self.tbl.horizontalHeader().height()
        row_h_total = 0
        for r in range(self.tbl.rowCount()):
            row_h_total += self.tbl.rowHeight(r)

        frame = self.tbl.frameWidth() * 2
        extra = 6

        desired = header_h + row_h_total + frame + extra

        min_h = header_h + 3 * self.tbl.verticalHeader().defaultSectionSize() + frame + extra
        max_h = header_h + 8 * self.tbl.verticalHeader().defaultSectionSize() + frame + extra

        desired = max(min_h, min(desired, max_h))

        self.tbl.setMinimumHeight(desired)
        self.tbl.setMaximumHeight(desired)        

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OMNI-Link")
        self.resize(1600, 900)
        self.setMinimumSize(1360, 820)

        self.video = VideoManager(self)
        self.router = RouterManager(self)
        self.video.status_changed.connect(self._refresh_status)
        self.router.status_changed.connect(self._refresh_status)

        self._out_ip = get_preferred_ethernet_ip()
        self._targets_generated = ""
        self._ping_thread = None
        self._ping_worker = None
        self._ping_running = False

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # =========================
        # Top toolbar
        # =========================
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(8)
        root.addLayout(top)

        title = QtWidgets.QLabel("OMNI-Link")
        title.setStyleSheet("font-size: 22px; font-weight: 900;")
        top.addWidget(title)

        top.addStretch(1)

        self.btn_refresh_ip = QtWidgets.QPushButton("Refresh Ethernet IP")
        self.btn_start_all = QtWidgets.QPushButton("Start All")
        self.btn_stop_all = QtWidgets.QPushButton("Stop All")
        self.btn_stop_all.setEnabled(False)

        top.addWidget(self.btn_refresh_ip)
        top.addWidget(self.btn_start_all)
        top.addWidget(self.btn_stop_all)

        # =========================
        # Main split
        # =========================
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        # =========================
        # LEFT SIDE
        # =========================
        left = QtWidgets.QWidget()
        split.addWidget(left)
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)

        # ---- Video output
        gb_out = QtWidgets.QGroupBox("Video Output")
        lv.addWidget(gb_out)
        og = QtWidgets.QGridLayout(gb_out)
        og.setContentsMargins(12, 10, 12, 10)
        og.setHorizontalSpacing(10)
        og.setVerticalSpacing(8)

        self.lbl_out_ip = QtWidgets.QLabel(self._out_ip)
        self.lbl_out_ip.setStyleSheet("font-weight: 900; font-size: 13px;")

        btn_copy_ip = QtWidgets.QPushButton("Copy IP")
        btn_copy_ip.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self._out_ip))

        self.sp_rtsp_port = QtWidgets.QSpinBox()
        self.sp_rtsp_port.setRange(1, 65535)
        self.sp_rtsp_port.setValue(8554)

        self.lbl_out_hint = QtWidgets.QLabel("RTSP Base: -")
        self.lbl_out_hint.setStyleSheet("font-weight: 700; color: rgb(90,90,90);")

        btn_copy_base = QtWidgets.QPushButton("Copy Base")
        btn_copy_base.clicked.connect(self._copy_video_base)

        og.addWidget(QtWidgets.QLabel("Ethernet Output IP"), 0, 0)
        og.addWidget(self.lbl_out_ip, 0, 1)
        og.addWidget(btn_copy_ip, 0, 2)
        og.addWidget(QtWidgets.QLabel("RTSP Port"), 0, 3)
        og.addWidget(self.sp_rtsp_port, 0, 4)
        og.addWidget(self.lbl_out_hint, 1, 0, 1, 4)
        og.addWidget(btn_copy_base, 1, 4)

        og.setColumnStretch(1, 1)
        og.setColumnStretch(4, 0)

        self.sp_rtsp_port.valueChanged.connect(lambda _v: self._update_video_base_hint())
        self._update_video_base_hint()

        gb_sources = QtWidgets.QGroupBox("Video Sources")
        gb_sources.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        lv.addWidget(gb_sources)

        sg = QtWidgets.QVBoxLayout(gb_sources)
        sg.setContentsMargins(12, 10, 12, 10)
        sg.setSpacing(8)

        self.tbl = QtWidgets.QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["On", "Camera", "Address", "Path"])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setShowGrid(False)
        self.tbl.setWordWrap(False)
        self.tbl.setTextElideMode(QtCore.Qt.ElideRight)
        self.tbl.verticalHeader().setDefaultSectionSize(38)
        self.tbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sg.addWidget(self.tbl, 0)

        hdr = self.tbl.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        self.tbl.setColumnWidth(0, 52)
        self.tbl.setColumnHidden(2, True)
        self.tbl.setColumnHidden(3, True)

        manual_box = QtWidgets.QFrame()
        manual_box.setObjectName("compactPanel")
        manual_box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        manual_lay = QtWidgets.QVBoxLayout(manual_box)
        manual_lay.setContentsMargins(0, 0, 0, 0)
        manual_lay.setSpacing(4)

        manual_row = QtWidgets.QHBoxLayout()
        manual_row.setSpacing(8)
        self.cb_manual_cam = QtWidgets.QCheckBox("Enable Manual Camera Address")
        self.ed_manual_cam = QtWidgets.QLineEdit("")
        self.ed_manual_cam.setPlaceholderText("rtsp://192.168.144.xx:554")
        manual_row.addWidget(self.cb_manual_cam)
        manual_row.addWidget(self.ed_manual_cam, 1)
        manual_lay.addLayout(manual_row)

        sg.addWidget(manual_box, 0)

        # ---- Video bottom controls compact
        video_bottom = QtWidgets.QHBoxLayout()
        video_bottom.setSpacing(8)

        self.btn_toggle_vsettings = QtWidgets.QToolButton()
        self.btn_toggle_vsettings.setText("Show Video Settings")
        self.btn_toggle_vsettings.setCheckable(True)
        self.btn_toggle_vsettings.setChecked(False)
        self.btn_toggle_vsettings.clicked.connect(self._toggle_video_settings)

        self.btn_video_start = QtWidgets.QPushButton("Start Video")
        self.btn_video_stop = QtWidgets.QPushButton("Stop Video")
        self.btn_video_stop.setEnabled(False)

        self.lbl_video = QtWidgets.QLabel("STOPPED")
        set_status_label(self.lbl_video, "STOPPED", False)

        video_bottom.addWidget(self.btn_toggle_vsettings)
        video_bottom.addWidget(self.btn_video_start)
        video_bottom.addWidget(self.btn_video_stop)
        video_bottom.addStretch(1)
        video_bottom.addWidget(QtWidgets.QLabel("Status"))
        video_bottom.addWidget(self.lbl_video)
        lv.addLayout(video_bottom)

        # ---- Video settings collapsible
        self.gb_vctl = QtWidgets.QGroupBox("Video Settings")
        lv.addWidget(self.gb_vctl)
        vg = QtWidgets.QGridLayout(self.gb_vctl)
        vg.setContentsMargins(12, 10, 12, 10)
        vg.setHorizontalSpacing(10)
        vg.setVerticalSpacing(8)

        self.ed_mediamtx = QtWidgets.QLineEdit(MEDIAMTX_BIN_DEFAULT)
        self.sp_bitrate = QtWidgets.QSpinBox()
        self.sp_bitrate.setRange(200, 20000)
        self.sp_bitrate.setValue(2500)

        self.cb_res = QtWidgets.QComboBox()
        self.cb_res.addItems(RES_CHOICES)
        self.cb_res.setCurrentText("1280x720")

        self.cb_fps = QtWidgets.QComboBox()
        self.cb_fps.addItems(FPS_CHOICES)
        self.cb_fps.setCurrentText("30")

        vg.addWidget(QtWidgets.QLabel("mediamtx"), 0, 0)
        vg.addWidget(self.ed_mediamtx, 0, 1, 1, 3)
        vg.addWidget(QtWidgets.QLabel("Bitrate (kbps)"), 1, 0)
        vg.addWidget(self.sp_bitrate, 1, 1)
        vg.addWidget(QtWidgets.QLabel("Webcam Res"), 1, 2)
        vg.addWidget(self.cb_res, 1, 3)
        vg.addWidget(QtWidgets.QLabel("Webcam FPS"), 2, 0)
        vg.addWidget(self.cb_fps, 2, 1)

        self.gb_vctl.setVisible(False)
        lv.addStretch(1)

        # =========================
        # RIGHT SIDE
        # =========================
        right = QtWidgets.QWidget()
        split.addWidget(right)
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)

        gb_tel = QtWidgets.QGroupBox("Telemetry Router")
        rv.addWidget(gb_tel)
        tg = QtWidgets.QGridLayout(gb_tel)
        tg.setContentsMargins(12, 10, 12, 10)
        tg.setHorizontalSpacing(10)
        tg.setVerticalSpacing(8)

        self.rb_hm30 = QtWidgets.QRadioButton("HM30")
        self.rb_ivcan = QtWidgets.QRadioButton("LambdaLink-3SS")
        self.rb_manual = QtWidgets.QRadioButton("Manual")
        self.rb_ivcan.setChecked(True)
        self.rb_hm30.setVisible(True)
        self.rb_manual.setVisible(False)


        preset_box = QtWidgets.QGroupBox("Input Preset")
        pv = QtWidgets.QVBoxLayout(preset_box)
        pv.setContentsMargins(10, 8, 10, 8)
        pv.setSpacing(6)
        pv.addWidget(self.rb_hm30)
        pv.addWidget(self.rb_ivcan)
        pv.addWidget(self.rb_manual)
        tg.addWidget(preset_box, 0, 0, 1, 4)

        targets_box = QtWidgets.QGroupBox("Targets / Client")
        tv = QtWidgets.QGridLayout(targets_box)
        tv.setContentsMargins(10, 8, 10, 8)
        tv.setHorizontalSpacing(10)
        tv.setVerticalSpacing(8)

        self.cb_t_pc1 = QtWidgets.QCheckBox(f"Instructor ({TEL_TARGETS['Instructor']})")
        self.cb_t_pc2 = QtWidgets.QCheckBox(f"Student ({TEL_TARGETS['Student']})")
        #self.cb_t_inst = QtWidgets.QCheckBox(f"Instrument-1 ({TEL_TARGETS['Instrument-1']})")

        self.cb_t_pc1.setChecked(True)
        self.cb_t_pc2.setChecked(True)
        #self.cb_t_inst.setChecked(False)

        self.sp_target_port = QtWidgets.QSpinBox()
        self.sp_target_port.setRange(1, 65535)
        self.sp_target_port.setValue(TEL_DEFAULT_TARGET_PORT)

        self.btn_copy_targets = QtWidgets.QPushButton("Copy Targets")

        tv.addWidget(self.cb_t_pc1, 0, 0)
        tv.addWidget(self.cb_t_pc2, 0, 1)
        #tv.addWidget(self.cb_t_inst, 0, 2)
        tv.addWidget(QtWidgets.QLabel("Port"), 1, 0)
        tv.addWidget(self.sp_target_port, 1, 1)
        tv.addWidget(self.btn_copy_targets, 1, 2)

        tg.addWidget(targets_box, 1, 0, 1, 4)

        tap_box = QtWidgets.QGroupBox("Instrument Light")
        tapg = QtWidgets.QGridLayout(tap_box)
        tapg.setContentsMargins(10, 8, 10, 8)
        tapg.setHorizontalSpacing(10)
        tapg.setVerticalSpacing(8)

        self.cb_espusr_enable = QtWidgets.QCheckBox("Enable")
        self.cb_espusr_enable.setChecked(True)

        self.cb_espusr_mode = QtWidgets.QComboBox()
        self.cb_espusr_mode.addItems(["TCP", "UDP"])
        self.cb_espusr_mode.setCurrentText("TCP")

        self.ed_espusr_ip = QtWidgets.QLineEdit("192.168.144.200")
        self.sp_espusr_port = QtWidgets.QSpinBox()
        self.sp_espusr_port.setRange(1, 65535)
        self.sp_espusr_port.setValue(14600)

        tapg.addWidget(self.cb_espusr_enable, 0, 0, 1, 2)
        tapg.addWidget(QtWidgets.QLabel("Mode"), 1, 0)
        tapg.addWidget(self.cb_espusr_mode, 1, 1)
        tapg.addWidget(QtWidgets.QLabel("IP"), 1, 2)
        tapg.addWidget(self.ed_espusr_ip, 1, 3)
        tapg.addWidget(QtWidgets.QLabel("Port"), 1, 4)
        tapg.addWidget(self.sp_espusr_port, 1, 5)

        tapg.setColumnStretch(3, 1)

        tg.addWidget(tap_box, 2, 0, 1, 4)

        self.manual_box = QtWidgets.QGroupBox("Manual Advanced")
        mv = QtWidgets.QGridLayout(self.manual_box)
        mv.setContentsMargins(10, 8, 10, 8)
        mv.setHorizontalSpacing(10)
        mv.setVerticalSpacing(8)

        self.rb_m_udp = QtWidgets.QRadioButton("UDP")
        self.rb_m_tcp = QtWidgets.QRadioButton("TCP")
        self.rb_m_udp.setChecked(True)

        mode_row = QtWidgets.QHBoxLayout()
        mode_row.setSpacing(10)
        mode_row.addWidget(self.rb_m_udp)
        mode_row.addWidget(self.rb_m_tcp)
        mode_row.addStretch(1)
        w_mode = QtWidgets.QWidget()
        w_mode.setLayout(mode_row)

        self.sp_listen_udp = QtWidgets.QSpinBox()
        self.sp_listen_udp.setRange(1, 65535)
        self.sp_listen_udp.setValue(19856)

        self.ed_tcp_ip = QtWidgets.QLineEdit("192.168.144.11")
        self.sp_tcp_port = QtWidgets.QSpinBox()
        self.sp_tcp_port.setRange(1, 65535)
        self.sp_tcp_port.setValue(20001)

        self.sp_tcp_server = QtWidgets.QSpinBox()
        self.sp_tcp_server.setRange(0, 65535)
        self.sp_tcp_server.setValue(5760)

        self.cb_primer = QtWidgets.QCheckBox("Primer (UDP only)")
        self.cb_primer.setChecked(True)

        self.ed_primer_ip = QtWidgets.QLineEdit("192.168.144.12")
        self.sp_primer_port = QtWidgets.QSpinBox()
        self.sp_primer_port.setRange(1, 65535)
        self.sp_primer_port.setValue(19856)

        self.cb_sudo = QtWidgets.QCheckBox("Administrator")
        self.cb_sudo.setChecked(False)

        self.txt_targets = QtWidgets.QPlainTextEdit()
        self.txt_targets.setPlaceholderText("Targets, one per line: IP:PORT")
        self.txt_targets.setMinimumHeight(100)
        self.txt_targets.setMaximumHeight(140)

        mv.addWidget(QtWidgets.QLabel("Input Mode"), 0, 0)
        mv.addWidget(w_mode, 0, 1, 1, 3)
        mv.addWidget(QtWidgets.QLabel("Listen UDP"), 1, 0)
        mv.addWidget(self.sp_listen_udp, 1, 1)
        mv.addWidget(QtWidgets.QLabel("TCP Server Port"), 1, 2)
        mv.addWidget(self.sp_tcp_server, 1, 3)
        mv.addWidget(QtWidgets.QLabel("TCP Upstream IP"), 2, 0)
        mv.addWidget(self.ed_tcp_ip, 2, 1)
        mv.addWidget(QtWidgets.QLabel("Port"), 2, 2)
        mv.addWidget(self.sp_tcp_port, 2, 3)
        mv.addWidget(self.cb_primer, 3, 0, 1, 2)
        mv.addWidget(self.cb_sudo, 3, 2, 1, 2)
        mv.addWidget(QtWidgets.QLabel("Primer Upstream IP"), 4, 0)
        mv.addWidget(self.ed_primer_ip, 4, 1)
        mv.addWidget(QtWidgets.QLabel("Port"), 4, 2)
        mv.addWidget(self.sp_primer_port, 4, 3)
        mv.addWidget(QtWidgets.QLabel("Targets (Manual)"), 5, 0, 1, 4)
        mv.addWidget(self.txt_targets, 6, 0, 1, 4)

        tg.addWidget(self.manual_box, 3, 0, 1, 4)
        self.manual_box.setVisible(False)

        # router controls compact
        router_control_box = QtWidgets.QGroupBox("Router Control")
        rv.addWidget(router_control_box)
        rcg = QtWidgets.QGridLayout(router_control_box)
        rcg.setContentsMargins(12, 10, 12, 10)
        rcg.setHorizontalSpacing(10)
        rcg.setVerticalSpacing(8)

        self.btn_router_start = QtWidgets.QPushButton("Start Router")
        self.btn_router_stop = QtWidgets.QPushButton("Stop Router")
        self.btn_router_stop.setEnabled(False)

        self.lbl_router = QtWidgets.QLabel("STOPPED")
        set_status_label(self.lbl_router, "STOPPED", False)

        self.lbl_tcp_info = QtWidgets.QLabel("TCP Server: -")
        self.lbl_tcp_info.setStyleSheet("font-weight: 700; color: rgb(100,100,100);")

        rcg.addWidget(self.btn_router_start, 0, 0)
        rcg.addWidget(self.btn_router_stop, 0, 1)
        rcg.addWidget(QtWidgets.QLabel("Status"), 0, 2)
        rcg.addWidget(self.lbl_router, 0, 3)
        rcg.addWidget(self.lbl_tcp_info, 1, 0, 1, 4)
        rcg.setColumnStretch(4, 1)

        gb_ping = QtWidgets.QGroupBox("Network Status")
        gb_ping.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        rv.addWidget(gb_ping)

        pg_root = QtWidgets.QVBoxLayout(gb_ping)
        pg_root.setContentsMargins(12, 10, 12, 10)
        pg_root.setSpacing(8)

        ping_top = QtWidgets.QHBoxLayout()
        ping_top.setSpacing(8)

        self.lbl_ping_summary = QtWidgets.QLabel("Devices: -")
        self.lbl_ping_summary.setStyleSheet("font-weight: 700; color: rgb(90,90,90);")

        ping_top.addWidget(self.lbl_ping_summary)
        ping_top.addStretch(1)

        self.btn_ping_refresh = QtWidgets.QPushButton("Refresh")
        ping_top.addWidget(self.btn_ping_refresh)
        pg_root.addLayout(ping_top)

        self.pg_status = QtWidgets.QGridLayout()
        self.pg_status.setHorizontalSpacing(10)
        self.pg_status.setVerticalSpacing(8)
        self.pg_status.setContentsMargins(0, 0, 0, 0)
        pg_root.addLayout(self.pg_status)

        self.ping_labels = {}
        self.ping_texts = {}
        self.ping_cards = []

        for name, ip in PING_DEVICES:
            card = self._build_status_dot(name, ip)
            self.ping_cards.append(card)

        self._relayout_ping_cards()

        rv.addStretch(1)

        split.setSizes([780, 820])

        # Wiring
        self.btn_refresh_ip.clicked.connect(self._refresh_ethernet_ip)
        self.btn_video_start.clicked.connect(self._start_video_clicked)
        self.btn_video_stop.clicked.connect(self.video.stop)

        self.btn_router_start.clicked.connect(self._start_router_clicked)
        self.btn_router_stop.clicked.connect(self.router.stop)

        self.btn_start_all.clicked.connect(self._start_all)
        self.btn_stop_all.clicked.connect(self._stop_all)

        self.rb_hm30.toggled.connect(self._apply_tel_profile_ui)
        self.rb_ivcan.toggled.connect(self._apply_tel_profile_ui)
        self.rb_manual.toggled.connect(self._apply_tel_profile_ui)

        self.cb_t_pc1.toggled.connect(self._sync_targets_from_checkboxes)
        self.cb_t_pc2.toggled.connect(self._sync_targets_from_checkboxes)
        #self.cb_t_inst.toggled.connect(self._sync_targets_from_checkboxes)
        self.sp_target_port.valueChanged.connect(lambda _v: self._sync_targets_from_checkboxes())
        self.btn_copy_targets.clicked.connect(self._copy_targets)

        self.rb_m_udp.toggled.connect(self._apply_manual_mode_ui)
        self.rb_m_tcp.toggled.connect(self._apply_manual_mode_ui)

        self.btn_ping_refresh.clicked.connect(self._request_ping_refresh)

        self._add_fixed_camera_row(True, "Main Camera", "rtsp://192.168.144.25:554", "cam1")
        self._add_fixed_camera_row(True, "Tail Camera", "rtsp://192.168.144.26:554", "cam2")
        self._update_video_table_height()

        self._sync_espusr_ui()
        self.cb_espusr_enable.toggled.connect(self._sync_espusr_ui)

        self._sync_targets_from_checkboxes()
        self._apply_tel_profile_ui()

        self.ping_timer = QtCore.QTimer(self)
        self.ping_timer.setInterval(120000)
        self.ping_timer.timeout.connect(self._request_ping_refresh)
        self.ping_timer.start()

        self.statusBar().showMessage("Ready")
        self._refresh_status()
        self._request_ping_refresh()

    def _relayout_ping_cards(self) -> None:
        while self.pg_status.count():
            item = self.pg_status.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        if not hasattr(self, "ping_cards"):
            return

        # adaptif: jika panel kanan cukup lebar pakai 2 kolom, kalau sempit jadi 1 kolom
        available_w = max(1, self.width() // 2)
        cols = 2 if available_w >= 700 else 1

        for i, card in enumerate(self.ping_cards):
            row = i // cols
            col = i % cols
            self.pg_status.addWidget(card, row, col)

        for c in range(cols):
            self.pg_status.setColumnStretch(c, 1)

    # ---------- Ethernet IP ----------
    def _refresh_ethernet_ip(self) -> None:
        self._out_ip = get_preferred_ethernet_ip()
        self.lbl_out_ip.setText(self._out_ip)
        self._update_video_base_hint()

    # ---------- Video settings toggle ----------
    def _toggle_video_settings(self) -> None:
        on = self.btn_toggle_vsettings.isChecked()
        self.gb_vctl.setVisible(on)
        self.btn_toggle_vsettings.setText("Hide Video Settings" if on else "Show Video Settings")

    # ---------- Video output helpers ----------
    def _update_video_base_hint(self) -> None:
        port = int(self.sp_rtsp_port.value())
        self.lbl_out_hint.setText(f"RTSP Base: rtsp://{self._out_ip}:{port}/")

    def _copy_video_base(self) -> None:
        port = int(self.sp_rtsp_port.value())
        QtWidgets.QApplication.clipboard().setText(f"rtsp://{self._out_ip}:{port}/")

    # ---------- Video sources ----------
    def _add_fixed_camera_row(self, enabled: bool, display_name: str, address: str, out_path: str) -> None:
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)

        chk = QtWidgets.QCheckBox()
        chk.setChecked(bool(enabled))
        w = QtWidgets.QWidget()
        l = QtWidgets.QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setAlignment(QtCore.Qt.AlignCenter)
        l.addWidget(chk)
        self.tbl.setCellWidget(r, 0, w)

        name_item = QtWidgets.QTableWidgetItem(display_name)
        self.tbl.setItem(r, 1, name_item)

        addr_item = QtWidgets.QTableWidgetItem(address)
        self.tbl.setItem(r, 2, addr_item)

        path_item = QtWidgets.QTableWidgetItem(out_path)
        self.tbl.setItem(r, 3, path_item)

        if hasattr(self, "_update_video_table_height"):
            self._update_video_table_height()

    def _collect_sources(self) -> List[VideoSource]:
        out: List[VideoSource] = []

        for r in range(self.tbl.rowCount()):
            enabled = True
            w0 = self.tbl.cellWidget(r, 0)
            if w0:
                cbx = w0.findChild(QtWidgets.QCheckBox)
                if cbx:
                    enabled = cbx.isChecked()

            addr = self.tbl.item(r, 2).text().strip() if self.tbl.item(r, 2) else ""
            path = self.tbl.item(r, 3).text().strip().lstrip("/") if self.tbl.item(r, 3) else ""
            if addr and path:
                out.append(VideoSource(enabled=enabled, vtype=VIDEO_TYPE_RTSP, input_text=addr, out_path=path))

        if self.cb_manual_cam.isChecked():
            addr = self.ed_manual_cam.text().strip()
            out.append(VideoSource(enabled=True, vtype=VIDEO_TYPE_RTSP, input_text=addr, out_path="cam3"))

        return out

    # ---------- Video ----------
    def _start_video_clicked(self) -> None:
        self._refresh_ethernet_ip()
        err = self.video.start(
            mediamtx_bin=self.ed_mediamtx.text().strip() or MEDIAMTX_BIN_DEFAULT,
            out_port=int(self.sp_rtsp_port.value()),
            sources=self._collect_sources(),
            global_bitrate_kbps=int(self.sp_bitrate.value()),
            webcam_res=self.cb_res.currentText().strip(),
            webcam_fps=int(self.cb_fps.currentText().strip()),
        )
        if err:
            QtWidgets.QMessageBox.critical(self, "OMNI-Link", err)
        self._refresh_status()

    # ---------- Telemetry ----------
    def _selected_profile(self) -> str:
        if self.rb_ivcan.isChecked():
            return "IVCAN"
        if self.rb_manual.isChecked():
            return "MANUAL"
        return "HM30"

    def _sync_targets_from_checkboxes(self) -> None:
        port = int(self.sp_target_port.value())
        lines: List[str] = []
        if self.cb_t_pc1.isChecked():
            lines.append(f"{TEL_TARGETS['Instructor']}:{port}")
        if self.cb_t_pc2.isChecked():
            lines.append(f"{TEL_TARGETS['Student']}:{port}")
        #if self.cb_t_inst.isChecked():
            #lines.append(f"{TEL_TARGETS['Instrument-1']}:{port}")

        txt = "\n".join(lines).strip()
        if not self.rb_manual.isChecked():
            self.txt_targets.blockSignals(True)
            self.txt_targets.setPlainText(txt if txt else "")
            self.txt_targets.blockSignals(False)

        self._targets_generated = txt

    def _copy_targets(self) -> None:
        QtWidgets.QApplication.clipboard().setText((self._targets_generated or "").strip())

    def _sync_espusr_ui(self) -> None:
        on = self.cb_espusr_enable.isChecked()
        self.cb_espusr_mode.setEnabled(on)
        self.ed_espusr_ip.setEnabled(on)
        self.sp_espusr_port.setEnabled(on)

    def _apply_manual_mode_ui(self) -> None:
        udp = self.rb_m_udp.isChecked()

        self.sp_listen_udp.setEnabled(udp)
        self.cb_primer.setEnabled(udp)
        self.ed_primer_ip.setEnabled(udp)
        self.sp_primer_port.setEnabled(udp)

        self.ed_tcp_ip.setEnabled(not udp)
        self.sp_tcp_port.setEnabled(not udp)

    def _apply_tel_profile_ui(self) -> None:
        prof = self._selected_profile()
        manual = (prof == "MANUAL")

        self.manual_box.setVisible(manual)
        self.txt_targets.setReadOnly(not manual)

        if prof in TEL_INPUT_PRESETS:
            p = TEL_INPUT_PRESETS[prof]
            if p["mode"] == "UDP":
                self.rb_m_udp.setChecked(True)
            else:
                self.rb_m_tcp.setChecked(True)

            self.sp_listen_udp.setValue(int(p["listen_udp"]))
            self.cb_primer.setChecked(bool(p["primer_enabled"]))
            self.ed_primer_ip.setText(str(p["primer_ip"]))
            self.sp_primer_port.setValue(int(p["primer_port"]))

            if p["mode"] == "TCP":
                self.ed_tcp_ip.setText(str(p["tcp_up_ip"]))
                self.sp_tcp_port.setValue(int(p["tcp_up_port"]))

            self._apply_manual_mode_ui()

        self._sync_targets_from_checkboxes()

    def _start_router_clicked(self) -> None:
        prof = self._selected_profile()

        if prof == "MANUAL":
            in_mode = "UDP" if self.rb_m_udp.isChecked() else "TCP"
            targets_text = self.txt_targets.toPlainText().strip()
        else:
            in_mode = TEL_INPUT_PRESETS[prof]["mode"]
            targets_text = (self._targets_generated or "").strip()

        err = self.router.start(
            in_mode=in_mode,
            listen_udp_port=int(self.sp_listen_udp.value()),
            tcp_up_ip=self.ed_tcp_ip.text().strip(),
            tcp_up_port=int(self.sp_tcp_port.value()),
            tcp_server_port_ui=int(self.sp_tcp_server.value()),
            targets_text=targets_text,
            primer_enabled=self.cb_primer.isChecked(),
            primer_up_ip=self.ed_primer_ip.text().strip(),
            primer_up_port=int(self.sp_primer_port.value()),
            use_sudo=self.cb_sudo.isChecked(),
            espusr_enabled=self.cb_espusr_enable.isChecked(),
            espusr_mode=self.cb_espusr_mode.currentText().strip(),
            espusr_ip=self.ed_espusr_ip.text().strip(),
            espusr_port=int(self.sp_espusr_port.value()),
        )
        if err:
            QtWidgets.QMessageBox.critical(self, "OMNI-Link", err)
        self._refresh_status()

    # ---------- Ping ----------
    def _request_ping_refresh(self) -> None:
        if self._ping_running:
            return

        self._ping_running = True
        self.btn_ping_refresh.setEnabled(False)
        self.btn_ping_refresh.setText("Refreshing...")

        self._ping_thread = QtCore.QThread(self)
        self._ping_worker = PingWorker(PING_DEVICES)
        self._ping_worker.moveToThread(self._ping_thread)

        self._ping_thread.started.connect(self._ping_worker.run)
        self._ping_worker.result_ready.connect(self._apply_ping_results)
        self._ping_worker.finished.connect(self._ping_thread.quit)
        self._ping_worker.finished.connect(self._ping_worker.deleteLater)
        self._ping_thread.finished.connect(self._on_ping_finished)
        self._ping_thread.finished.connect(self._ping_thread.deleteLater)

        self._ping_thread.start()

    def _apply_ping_results(self, results: Dict[str, bool]) -> None:
        connected = 0
        total = len(PING_DEVICES)

        for name, ip in PING_DEVICES:
            ok = bool(results.get(name, False))
            lbl = self.ping_labels.get(name)
            txt = self.ping_texts.get(name)
            if not lbl or not txt:
                continue

            if ok:
                connected += 1
                lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: rgb(0, 170, 0);")
                txt.setToolTip(f"{name} {ip} connected")
            else:
                lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: rgb(180, 60, 60);")
                txt.setToolTip(f"{name} {ip} disconnected")

        if hasattr(self, "lbl_ping_summary"):
            self.lbl_ping_summary.setText(f"Devices online: {connected}/{total}")

    def _on_ping_finished(self) -> None:
        self._ping_running = False
        self.btn_ping_refresh.setEnabled(True)
        self.btn_ping_refresh.setText("Refresh")
        self._ping_thread = None
        self._ping_worker = None

    # ---------- All ----------
    def _start_all(self) -> None:
        self._refresh_ethernet_ip()
        self._start_router_clicked()
        self._start_video_clicked()
        self._request_ping_refresh()
        self._refresh_status()

    def _stop_all(self) -> None:
        self.video.stop()
        self.router.stop()
        self._refresh_status()

    def _refresh_status(self) -> None:
        v_on = self.video.is_running()
        r_on = self.router.is_running()

        set_status_label(self.lbl_video, "RUNNING" if v_on else "STOPPED", v_on)
        set_status_label(self.lbl_router, "RUNNING" if r_on else "STOPPED", r_on)

        if r_on:
            self.lbl_tcp_info.setText(f"TCP Server: 127.0.0.1:{self.router.effective_tcp_port()}")
        else:
            self.lbl_tcp_info.setText("TCP Server: -")

        self.btn_video_start.setEnabled(not v_on)
        self.btn_video_stop.setEnabled(v_on)

        self.btn_router_start.setEnabled(not r_on)
        self.btn_router_stop.setEnabled(r_on)

        any_on = v_on or r_on
        self.btn_start_all.setEnabled(not any_on)
        self.btn_stop_all.setEnabled(any_on)

        self.statusBar().showMessage(f"Video: {'ON' if v_on else 'OFF'} | Router: {'ON' if r_on else 'OFF'}")

    def closeEvent(self, e: QtGui.QCloseEvent):
        try:
            self._stop_all()
        finally:
            e.accept()


def apply_simple_style(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet("""
    QWidget {
        font-size: 13px;
    }
    QGroupBox {
        font-weight: 800;
        border: 1px solid rgba(120,120,120,0.30);
        border-radius: 10px;
        margin-top: 10px;
        padding: 8px;
        background: rgba(255,255,255,1.0);
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px 0 6px;
        color: rgb(60,60,60);
    }
    QFrame#statusCard {
        border: 1px solid rgba(120,120,120,0.18);
        border-radius: 9px;
        background: rgba(248,248,248,1.0);
    QFrame#compactPanel {
        background: transparent;
        border: none;
}
    }
    QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {
        border: 1px solid rgba(120,120,120,0.30);
        border-radius: 8px;
        padding: 6px;
        background: white;
        min-height: 28px;
    }
    QPushButton, QToolButton {  
        border: 1px solid rgba(120,120,120,0.30);
        border-radius: 10px;
        padding: 7px 12px;
        background: rgba(245,245,245,1.0);
        font-weight: 800;
        min-height: 30px;
    }
    QPushButton:hover, QToolButton:hover {
        background: rgba(235,235,235,1.0);
    }
    QPushButton:disabled {
        color: rgba(120,120,120,0.8);
        background: rgba(245,245,245,0.6);
    }
    QTableWidget {
        border: 1px solid rgba(120,120,120,0.22);
        border-radius: 10px;
        background: white;
        selection-background-color: rgba(210,210,210,0.55);
        selection-color: rgb(20,20,20);
    }
    QHeaderView::section {
        background: rgba(245,245,245,1.0);
        border: none;
        padding: 8px;
        font-weight: 900;
        color: rgb(60,60,60);
    }
    QTableWidget::item {
        padding: 6px;
    }
    """)


def main():
    if sys.platform.startswith("linux"):
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtWidgets.QApplication([])
    apply_simple_style(app)

    w = MainWindow()
    w.show()
    app.exec_()


if __name__ == "__main__":
    main()