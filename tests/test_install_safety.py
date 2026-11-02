"""Regression checks for installers that must not remove desktop packages."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"
BUILD = ROOT / "scripts" / "build_appimage.sh"


def run_setup_function(body: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", f'source "{SETUP}"\n{body}'],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_setup_skips_apt_by_default():
    result = run_setup_function(
        'apt-get() { echo "apt was called" >&2; return 1; }\n'
        "install_apt_packages"
    )
    assert result.returncode == 0
    assert "Skipping system packages" in result.stdout
    assert "apt was called" not in result.stderr


def test_apt_refuses_a_removal_plan():
    result = run_setup_function(
        'SUDO=()\n'
        'apt-get() { if [[ "$1" == "-s" ]]; then echo "Remv cinnamon [6.0]"; '
        'else echo "real install called" >&2; fi; }\n'
        "safe_apt_install ffmpeg"
    )
    assert result.returncode != 0
    assert "refusing to continue" in result.stderr
    assert "real install called" not in result.stderr


def test_apt_real_transaction_keeps_removal_and_upgrade_guards():
    result = run_setup_function(
        'SUDO=()\n'
        'apt-get() { printf "%s\\n" "$*"; }\n'
        "safe_apt_install ffmpeg"
    )
    assert result.returncode == 0
    assert "install -y --no-remove --no-upgrade --no-install-recommends ffmpeg" in result.stdout


def test_appimage_build_rejects_path_like_version_before_cleanup():
    env = os.environ.copy()
    env["VERSION"] = "../../desktop"
    result = subprocess.run(
        ["bash", str(BUILD)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Invalid VERSION" in result.stderr


def test_setup_refuses_virtualenv_outside_repository():
    result = run_setup_function('VENV_DIR="/usr/local"\ninstall_python_packages')
    assert result.returncode == 2
    assert "Refusing VENV_DIR outside" in result.stderr


def test_setup_reports_missing_runtime_instead_of_claiming_completion():
    result = run_setup_function(
        'MEDIAMTX_BIN="/nonexistent/mediamtx"\n'
        'need_cmd() { return 1; }\n'
        "verify_runtime_dependencies"
    )
    assert result.returncode != 0
    assert "Setup is incomplete" in result.stderr
    assert "mavlink-routerd" in result.stderr


def test_single_system_opt_in_enables_router_source_fallback():
    env = os.environ.copy()
    env["ALLOW_SYSTEM_CHANGES"] = "1"
    env.pop("BUILD_MAVLINK_ROUTER_FROM_SOURCE", None)
    result = subprocess.run(
        ["bash", "-c", f'source "{SETUP}"; printf "%s" "$BUILD_MAVLINK_ROUTER_FROM_SOURCE"'],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == "1"


def test_router_uses_source_fallback_when_apt_package_is_unavailable():
    result = run_setup_function(
        'ALLOW_SYSTEM_CHANGES=1\n'
        'BUILD_MAVLINK_ROUTER_FROM_SOURCE=1\n'
        'need_cmd() { return 1; }\n'
        'require_sudo() { SUDO=(); }\n'
        'build_mavlink_router_from_source() { echo "router source fallback called"; }\n'
        'install_mavlink_router'
    )
    assert result.returncode == 0
    assert "router source fallback called" in result.stdout


def test_setup_attempts_mediamtx_before_optional_router_and_python():
    result = run_setup_function(
        'validate_venv_dir() { :; }\n'
        'install_apt_packages() { echo apt; }\n'
        'install_mediamtx() { echo mediamtx; }\n'
        'install_mavlink_router() { echo router; }\n'
        'install_python_packages() { echo python; }\n'
        'verify_runtime_dependencies() { echo verify; }\n'
        'print_summary() { echo summary; }\n'
        'main'
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "apt", "mediamtx", "router", "python", "verify", "summary"
    ]
