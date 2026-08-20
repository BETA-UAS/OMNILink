from typing import List, Tuple

from core.config_models import RouterConfig
from core.network_utils import find_available_tcp_port, is_valid_ipv4_address, is_valid_network_port


def parse_router_targets(targets_text: str) -> List[Tuple[str, int]]:
    targets: List[Tuple[str, int]] = []
    seen = set()

    for raw_line in targets_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Target invalid: {line} (gunakan IP:PORT)")

        ip_address, port_text = line.rsplit(":", 1)
        ip_address = ip_address.strip()
        port_text = port_text.strip()

        if not is_valid_ipv4_address(ip_address):
            raise ValueError(f"Target IP invalid: {ip_address}")
        if not port_text.isdigit() or not is_valid_network_port(int(port_text)):
            raise ValueError(f"Target port invalid: {line}")

        target = (ip_address, int(port_text))
        if target in seen:
            continue

        seen.add(target)
        targets.append(target)

    if not targets:
        raise ValueError("Target kosong")

    return targets


def build_router_config(config: RouterConfig) -> Tuple[str, int]:
    effective_tcp_port = find_available_tcp_port(int(config.tcp_server_port_ui))
    targets = parse_router_targets(config.targets_text)
    input_mode = config.in_mode.strip().upper()

    lines: List[str] = [
        "[General]",
        f"TcpServerPort={effective_tcp_port}",
        "ReportStats=false",
        "",
    ]

    if input_mode == "UDP":
        if not is_valid_network_port(config.listen_udp_port):
            raise ValueError("Listen UDP port invalid")
        lines += [
            "[UdpEndpoint input]",
            "Mode=Server",
            "Address=0.0.0.0",
            f"Port={config.listen_udp_port}",
            "",
        ]
    elif input_mode == "TCP":
        if not is_valid_ipv4_address(config.tcp_up_ip):
            raise ValueError("TCP upstream IP invalid")
        if not is_valid_network_port(config.tcp_up_port):
            raise ValueError("TCP upstream port invalid")
        lines += [
            "[TcpEndpoint input]",
            "Mode=Client",
            f"Address={config.tcp_up_ip}",
            f"Port={config.tcp_up_port}",
            "",
        ]
    else:
        raise ValueError("Input mode invalid")

    for index, (ip_address, port) in enumerate(targets, start=1):
        lines += [
            f"[UdpEndpoint gcs{index}]",
            "Mode=Normal",
            f"Address={ip_address}",
            f"Port={port}",
            "",
        ]

    if config.espusr_enabled:
        if not is_valid_ipv4_address(config.espusr_ip) or not is_valid_network_port(
            config.espusr_port
        ):
            raise ValueError("ESP/USR IP atau Port invalid")

        espusr_mode = config.espusr_mode.strip().upper()
        if espusr_mode == "TCP":
            lines += [
                "[TcpEndpoint espusr]",
                "Mode=Client",
                f"Address={config.espusr_ip}",
                f"Port={config.espusr_port}",
                "",
            ]
        elif espusr_mode == "UDP":
            lines += [
                "[UdpEndpoint espusr]",
                "Mode=Normal",
                f"Address={config.espusr_ip}",
                f"Port={config.espusr_port}",
                "",
            ]
        else:
            raise ValueError("ESP/USR mode invalid")

    return "\n".join(lines), effective_tcp_port
