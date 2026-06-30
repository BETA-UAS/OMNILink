#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON_BIN="${PYTHON:-python3}"
INSTALL_MEDIAMTX="${INSTALL_MEDIAMTX:-1}"
MEDIAMTX_BIN="${MEDIAMTX_BIN:-/usr/local/bin/mediamtx}"

log() {
  printf '\n[OMNI-Link setup] %s\n' "$*"
}

warn() {
  printf '\n[OMNI-Link setup] Warning: %s\n' "$*" >&2
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

require_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    SUDO=()
  elif need_cmd sudo; then
    SUDO=(sudo)
  else
    echo "This setup needs root privileges for system packages. Install sudo or run as root." >&2
    exit 1
  fi
}

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64)
      echo "amd64"
      ;;
    aarch64|arm64)
      echo "arm64"
      ;;
    armv7l|armhf)
      echo "armv7"
      ;;
    *)
      echo "unsupported"
      ;;
  esac
}

install_apt_packages() {
  if ! need_cmd apt-get; then
    warn "apt-get not found. Install Python 3, PyQt5 runtime libraries, ffmpeg, iproute2, iputils-ping, and mavlink-routerd manually."
    return
  fi

  require_sudo

  local packages=(
    ca-certificates
    curl
    ffmpeg
    iproute2
    iputils-ping
    python3
    python3-pip
    python3-venv
    tar
  )

  local qt_runtime_packages=(
    libegl1
    libfontconfig1
    libgl1
    libglib2.0-0
    libx11-6
    libxcb1
    libxcb-cursor0
    libxcb-icccm4
    libxcb-image0
    libxcb-keysyms1
    libxcb-randr0
    libxcb-render-util0
    libxcb-render0
    libxcb-shape0
    libxcb-shm0
    libxcb-sync1
    libxcb-xfixes0
    libxcb-xinerama0
    libxcb-xkb1
    libxkbcommon-x11-0
  )

  log "Installing system packages"
  "${SUDO[@]}" apt-get update
  "${SUDO[@]}" apt-get install -y "${packages[@]}" "${qt_runtime_packages[@]}"

  if apt-cache show mavlink-router >/dev/null 2>&1; then
    "${SUDO[@]}" apt-get install -y mavlink-router
  elif apt-cache show mavlink-routerd >/dev/null 2>&1; then
    "${SUDO[@]}" apt-get install -y mavlink-routerd
  else
    warn "mavlink-router package was not found in apt repositories. Install mavlink-routerd manually before using telemetry routing."
  fi
}

install_python_packages() {
  if ! need_cmd "${PYTHON_BIN}"; then
    echo "Python command not found: ${PYTHON_BIN}" >&2
    exit 1
  fi

  log "Creating Python virtual environment at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"

  # shellcheck source=/dev/null
  source "${VENV_DIR}/bin/activate"

  log "Installing Python dependencies"
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install -r "${ROOT_DIR}/requirements.txt"
}

latest_mediamtx_url() {
  local arch="$1"
  python3 - "$arch" <<'PY'
import json
import sys
import urllib.request

arch = sys.argv[1]
api_url = "https://api.github.com/repos/bluenviron/mediamtx/releases/latest"
with urllib.request.urlopen(api_url, timeout=30) as response:
    release = json.load(response)

needle = f"linux_{arch}.tar.gz"
for asset in release.get("assets", []):
    url = asset.get("browser_download_url", "")
    if needle in url:
        print(url)
        raise SystemExit(0)

raise SystemExit(f"No mediamtx asset found for {needle}")
PY
}

install_mediamtx() {
  if [[ "${INSTALL_MEDIAMTX}" != "1" ]]; then
    log "Skipping MediaMTX install because INSTALL_MEDIAMTX=${INSTALL_MEDIAMTX}"
    return
  fi

  if need_cmd mediamtx || [[ -x "${MEDIAMTX_BIN}" ]]; then
    log "MediaMTX already installed"
    return
  fi

  require_sudo

  local arch
  arch="$(detect_arch)"
  if [[ "${arch}" == "unsupported" ]]; then
    warn "Unsupported architecture for automatic MediaMTX install: $(uname -m). Install mediamtx manually."
    return
  fi

  local url
  local tmpdir=""

  cleanup_mediamtx_tmpdir() {
    if [[ -n "${tmpdir:-}" && -d "${tmpdir}" ]]; then
      rm -rf "${tmpdir}"
    fi
  }

  log "Resolving latest MediaMTX release for linux_${arch}"
  url="$(latest_mediamtx_url "${arch}")"
  tmpdir="$(mktemp -d)"
  trap cleanup_mediamtx_tmpdir RETURN

  log "Downloading MediaMTX"
  curl -L "${url}" -o "${tmpdir}/mediamtx.tar.gz"
  tar -xzf "${tmpdir}/mediamtx.tar.gz" -C "${tmpdir}"
  "${SUDO[@]}" install -m 0755 "${tmpdir}/mediamtx" "${MEDIAMTX_BIN}"

  cleanup_mediamtx_tmpdir
  trap - RETURN
}

print_summary() {
  local mediamtx_path
  mediamtx_path="$(command -v mediamtx || true)"
  if [[ -z "${mediamtx_path}" && -x "${MEDIAMTX_BIN}" ]]; then
    mediamtx_path="${MEDIAMTX_BIN}"
  fi

  cat <<EOF

OMNI-Link setup complete.

Run the app with:
  source "${VENV_DIR}/bin/activate"
  python "${ROOT_DIR}/main.py"

Runtime checks:
  ffmpeg:           $(command -v ffmpeg || true)
  mediamtx:         ${mediamtx_path}
  mavlink-routerd:  $(command -v mavlink-routerd || true)
  ip:               $(command -v ip || true)
  ping:             $(command -v ping || true)

EOF
}

main() {
  install_apt_packages
  install_python_packages
  install_mediamtx
  print_summary
}

main "$@"
