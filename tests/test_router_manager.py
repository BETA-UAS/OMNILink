import pytest
from core.config_models import RouterConfig
from core.router_config import build_router_config, parse_router_targets


def router_config(**overrides):
    values = {
        "in_mode": "UDP",
        "listen_udp_port": 19856,
        "tcp_up_ip": "192.168.144.11",
        "tcp_up_port": 20001,
        "tcp_server_port_ui": 5760,
        "targets_text": "192.168.144.20:14550\n192.168.144.20:14550\n192.168.144.21:14550",
        "primer_enabled": True,
        "primer_up_ip": "192.168.144.12",
        "primer_up_port": 19856,
        "use_sudo": False,
        "espusr_enabled": False,
        "espusr_mode": "TCP",
        "espusr_ip": "192.168.144.200",
        "espusr_port": 14600,
    }
    values.update(overrides)
    return RouterConfig(**values)


def test_parse_router_targets_normalizes_and_deduplicates():
    assert parse_router_targets(" 192.168.144.20:14550 \n\n192.168.144.20:14550") == [
        ("192.168.144.20", 14550)
    ]


@pytest.mark.parametrize(
    "targets_text, message",
    [
        ("", "Target kosong"),
        ("192.168.144.20", "Target invalid"),
        ("999.168.144.20:14550", "Target IP invalid"),
        ("192.168.144.20:99999", "Target port invalid"),
    ],
)
def test_parse_router_targets_rejects_invalid_input(targets_text, message):
    with pytest.raises(ValueError, match=message):
        parse_router_targets(targets_text)


def test_build_router_config_udp(monkeypatch):
    monkeypatch.setattr("core.router_config.find_available_tcp_port", lambda preferred: 5761)

    config_text, effective_port = build_router_config(router_config())

    assert effective_port == 5761
    assert "[UdpEndpoint input]" in config_text
    assert "Port=19856" in config_text
    assert config_text.count("[UdpEndpoint gcs") == 2
    assert "TcpServerPort=5761" in config_text


def test_build_router_config_tcp_with_espusr_tcp(monkeypatch):
    monkeypatch.setattr("core.router_config.find_available_tcp_port", lambda preferred: preferred)

    config_text, effective_port = build_router_config(
        router_config(in_mode="TCP", espusr_enabled=True, espusr_mode="TCP")
    )

    assert effective_port == 5760
    assert "[TcpEndpoint input]" in config_text
    assert "Address=192.168.144.11" in config_text
    assert "[TcpEndpoint espusr]" in config_text


def test_build_router_config_with_espusr_udp(monkeypatch):
    monkeypatch.setattr("core.router_config.find_available_tcp_port", lambda preferred: preferred)

    config_text, _effective_port = build_router_config(
        router_config(espusr_enabled=True, espusr_mode="UDP")
    )

    assert "[UdpEndpoint espusr]" in config_text
    assert "Address=192.168.144.200" in config_text
