import ipaddress
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def command_exists(cmd: str) -> bool:
    """Check if a command exists in the system path."""
    return shutil.which(cmd) is not None


def noninteractive_sudo_error() -> Optional[str]:
    if not command_exists("sudo"):
        return "sudo tidak ditemukan"
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "sudo non-interaktif gagal"
    if result.returncode != 0:
        return "sudo membutuhkan password interaktif; aktifkan NOPASSWD atau matikan Administrator"
    return None


def is_valid_ipv4_address(ip: str) -> bool:
    try:
        parsed_ip = ipaddress.ip_address(ip.strip())
        return parsed_ip.version == 4
    except ValueError:
        return False


def is_valid_network_port(port: int) -> bool:
    try:
        numeric_port = int(port)
    except (TypeError, ValueError):
        return False
    return 1 <= numeric_port <= 65535


def list_video_devices() -> List[str]:
    devices: List[str] = []
    for device_path in sorted(
        Path("/dev").glob("video*"),
        key=lambda path: int(re.sub(r"\D", "", path.name) or "9999"),
    ):
        devices.append(f"/dev/{device_path.name}")
    return devices


def get_socket_status_output() -> str:
    if not command_exists("ss"):
        return ""
    try:
        return subprocess.check_output(["ss", "-lunpt"], stderr=subprocess.STDOUT, text=True)
    except (OSError, subprocess.SubprocessError):
        return ""


def _ss_local_port(line: str) -> Optional[int]:
    parts = line.split()
    if len(parts) < 5:
        return None

    endpoint = parts[4]
    if ":" not in endpoint:
        return None

    port_text = endpoint.rsplit(":", 1)[1]
    if not port_text.isdigit():
        return None
    return int(port_text)


def socket_status_has_listener(ss_text: str, proto: str, port: int) -> bool:
    if not ss_text:
        return False

    normalized_proto = proto.lower()
    if normalized_proto not in {"tcp", "udp"}:
        return False
    try:
        expected_port = int(port)
    except (TypeError, ValueError):
        return False

    for line in ss_text.splitlines():
        parts = line.split()
        if not parts or not parts[0].lower().startswith(normalized_proto):
            continue
        if _ss_local_port(line) == expected_port:
            return True
    return False


def find_available_tcp_port(preferred: int, tries: int = 40) -> int:
    if preferred == 0:
        return 0
    ss_text = get_socket_status_output()
    port = preferred
    for _ in range(max(1, tries)):
        if not socket_status_has_listener(ss_text, "tcp", port):
            return port
        port += 1
    return preferred


def host_responds_to_ping(ip: str, timeout_sec: int = 1) -> bool:
    if not command_exists("ping"):
        return False
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_sec), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_sec + 1,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def get_ipv4_address_output() -> str:
    if not command_exists("ip"):
        return ""
    try:
        return subprocess.check_output(
            ["ip", "-4", "addr", "show"], stderr=subprocess.STDOUT, text=True
        )
    except (OSError, subprocess.SubprocessError):
        return ""


def select_preferred_ethernet_ipv4() -> str:
    """Selects an IP from an ethernet interface in the 192.168.144.x subnet."""
    ip_addr_output = get_ipv4_address_output()
    if not ip_addr_output:
        return "127.0.0.1"

    current_if = ""
    candidates_144: List[Tuple[str, str]] = []
    candidates_eth: List[Tuple[str, str]] = []

    for line in ip_addr_output.splitlines():
        if re.match(r"^\d+:\s", line):
            interface_match = re.match(r"^\d+:\s*([^:]+):", line)
            current_if = interface_match.group(1) if interface_match else ""
            continue

        ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/\d+", line)
        if not ip_match or not current_if:
            continue

        ip = ip_match.group(1)
        if ip.startswith("127."):
            continue

        low_if = current_if.lower()
        is_wifi = any(w in low_if for w in ("wl", "wifi", "wlan", "wireless"))
        is_eth_like = any(e in low_if for e in ("en", "eth", "ether"))

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
