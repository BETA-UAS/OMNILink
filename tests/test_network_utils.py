from core.network_utils import (
    find_available_tcp_port,
    is_valid_ipv4_address,
    is_valid_network_port,
    noninteractive_sudo_error,
    socket_status_has_listener,
)


def test_ip_validation_accepts_ipv4_only():
    assert is_valid_ipv4_address("192.168.144.10")
    assert not is_valid_ipv4_address("999.168.144.10")
    assert not is_valid_ipv4_address("example.com")
    assert not is_valid_ipv4_address("::1")


def test_port_validation_accepts_valid_tcp_udp_range():
    assert is_valid_network_port(1)
    assert is_valid_network_port(65535)
    assert not is_valid_network_port(0)
    assert not is_valid_network_port(65536)
    assert not is_valid_network_port("bad")


def test_socket_status_matches_exact_local_port_only():
    ss_text = "\n".join(
        [
            "Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port Process",
            "tcp LISTEN 0 4096 0.0.0.0:57601 0.0.0.0:*",
            "udp UNCONN 0 0 0.0.0.0:14550 0.0.0.0:*",
        ]
    )

    assert not socket_status_has_listener(ss_text, "tcp", 5760)
    assert socket_status_has_listener(ss_text, "tcp", 57601)
    assert not socket_status_has_listener(ss_text, "tcp", 14550)
    assert socket_status_has_listener(ss_text, "udp", 14550)


def test_socket_status_matches_ipv6_listener_port():
    ss_text = "tcp LISTEN 0 4096 [::]:5760 [::]:*"

    assert socket_status_has_listener(ss_text, "tcp", 5760)


def test_find_available_tcp_port_uses_exact_port_matching(monkeypatch):
    monkeypatch.setattr(
        "core.network_utils.get_socket_status_output",
        lambda: "tcp LISTEN 0 4096 0.0.0.0:57601 0.0.0.0:*",
    )

    assert find_available_tcp_port(5760) == 5760


def test_find_available_tcp_port_skips_occupied_preferred(monkeypatch):
    monkeypatch.setattr(
        "core.network_utils.get_socket_status_output",
        lambda: "tcp LISTEN 0 4096 0.0.0.0:5760 0.0.0.0:*",
    )

    assert find_available_tcp_port(5760) == 5761


def test_noninteractive_sudo_reports_missing_sudo(monkeypatch):
    monkeypatch.setattr("core.network_utils.command_exists", lambda cmd: cmd != "sudo")

    assert noninteractive_sudo_error() == "sudo tidak ditemukan"


def test_noninteractive_sudo_reports_password_prompt(monkeypatch):
    class Result:
        returncode = 1

    monkeypatch.setattr("core.network_utils.command_exists", lambda _cmd: True)
    monkeypatch.setattr("core.network_utils.subprocess.run", lambda *_args, **_kwargs: Result())

    assert "password interaktif" in noninteractive_sudo_error()


def test_noninteractive_sudo_accepts_success(monkeypatch):
    class Result:
        returncode = 0

    monkeypatch.setattr("core.network_utils.command_exists", lambda _cmd: True)
    monkeypatch.setattr("core.network_utils.subprocess.run", lambda *_args, **_kwargs: Result())

    assert noninteractive_sudo_error() is None
