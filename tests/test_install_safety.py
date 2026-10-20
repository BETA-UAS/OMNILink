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
