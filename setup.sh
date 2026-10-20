#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON_BIN="${PYTHON:-python3}"

INSTALL_MEDIAMTX="${INSTALL_MEDIAMTX:-1}"
MEDIAMTX_BIN="${MEDIAMTX_BIN:-/usr/local/bin/mediamtx}"

INSTALL_MAVLINK_ROUTER="${INSTALL_MAVLINK_ROUTER:-1}"
BUILD_MAVLINK_ROUTER_FROM_SOURCE="${BUILD_MAVLINK_ROUTER_FROM_SOURCE:-0}"
# System-wide package/binary changes are opt-in. A virtualenv is still created.
ALLOW_SYSTEM_CHANGES="${ALLOW_SYSTEM_CHANGES:-0}"

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

safe_apt_install() {
  local simulation
  # --no-remove is enforced again during the real transaction: the simulation
  # alone cannot protect against repository changes between the two commands.
  if ! simulation="$(LC_ALL=C apt-get -s --no-remove --no-upgrade \
    --no-install-recommends install "$@" 2>&1)"; then
    printf '%s\n' "${simulation}" >&2
    echo "APT cannot install these packages without changing existing packages; nothing was installed." >&2
    return 1
  fi
  if printf '%s\n' "${simulation}" | grep -Eq '^Remv '; then
    printf '%s\n' "${simulation}" >&2
    echo "APT proposed removing packages; refusing to continue." >&2
    return 1
  fi
  "${SUDO[@]}" apt-get install -y --no-remove --no-upgrade \
    --no-install-recommends "$@"
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
  if [[ "${ALLOW_SYSTEM_CHANGES}" != "1" ]]; then
    log "Skipping system packages (set ALLOW_SYSTEM_CHANGES=1 to opt in)"
    return
  fi
  if ! need_cmd apt-get; then
    warn "apt-get not found. Install Python 3, PyQt5 runtime libraries, ffmpeg, iproute2, iputils-ping, and mavlink-routerd manually."
    return
  fi

  require_sudo

  local packages=(
    ca-certificates
    curl
    ffmpeg
    git
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

  local mavlink_router_build_packages=(
    build-essential
    libsystemd-dev
    meson
    ninja-build
    pkg-config
  )

  log "Installing system packages"
  "${SUDO[@]}" apt-get update
  safe_apt_install \
    "${packages[@]}" \
    "${qt_runtime_packages[@]}" \
    "${mavlink_router_build_packages[@]}"
}

install_mavlink_router() {
  if [[ "${INSTALL_MAVLINK_ROUTER}" != "1" ]]; then
    log "Skipping mavlink-router install because INSTALL_MAVLINK_ROUTER=${INSTALL_MAVLINK_ROUTER}"
    return
  fi

  if need_cmd mavlink-routerd; then
    log "mavlink-routerd already installed: $(command -v mavlink-routerd)"
    return
  fi

  if [[ "${ALLOW_SYSTEM_CHANGES}" != "1" ]]; then
    warn "mavlink-routerd is missing; system installation is disabled. Set ALLOW_SYSTEM_CHANGES=1 to opt in."
    return
  fi

  require_sudo

  if need_cmd apt-get; then
    log "Trying to install mavlink-router from apt"

    if apt-cache show mavlink-router >/dev/null 2>&1; then
      safe_apt_install mavlink-router
    elif apt-cache show mavlink-routerd >/dev/null 2>&1; then
      safe_apt_install mavlink-routerd
    else
      warn "mavlink-router package was not found in apt repositories. Building from source."
    fi
  fi

  if need_cmd mavlink-routerd; then
    log "mavlink-routerd installed from apt: $(command -v mavlink-routerd)"
    return
  fi

  if [[ "${BUILD_MAVLINK_ROUTER_FROM_SOURCE}" != "1" ]]; then
    warn "mavlink-routerd is unavailable; automatic source builds are disabled. Set BUILD_MAVLINK_ROUTER_FROM_SOURCE=1 to opt in."
    return
  fi

  if ! need_cmd git || ! need_cmd meson || ! need_cmd ninja; then
    warn "Cannot build mavlink-routerd because git/meson/ninja is missing."
    return
  fi

  local tmpdir=""

  cleanup_mavlink_router_tmpdir() {
    if [[ -n "${tmpdir:-}" && -d "${tmpdir}" ]]; then
      rm -rf "${tmpdir}"
    fi
  }

  tmpdir="$(mktemp -d)"
  trap cleanup_mavlink_router_tmpdir RETURN

  log "Building mavlink-router from source"
  git clone https://github.com/mavlink-router/mavlink-router.git "${tmpdir}/mavlink-router"

  cd "${tmpdir}/mavlink-router"
  git submodule update --init --recursive

  meson setup build .
  ninja -C build
  "${SUDO[@]}" ninja -C build install
  "${SUDO[@]}" ldconfig || true

  cd "${ROOT_DIR}"

  cleanup_mavlink_router_tmpdir
  trap - RETURN

  if need_cmd mavlink-routerd; then
    log "mavlink-routerd installed successfully: $(command -v mavlink-routerd)"
  else
    warn "mavlink-routerd build completed but binary was not found in PATH."
  fi
}

validate_venv_dir() {
  if ! need_cmd realpath; then
    echo "realpath is required to validate VENV_DIR safely" >&2
    exit 1
  fi
  local resolved_venv_dir
  resolved_venv_dir="$(realpath -m -- "${VENV_DIR}")"
  if [[ "${resolved_venv_dir}" != "${ROOT_DIR}/"* ]]; then
    echo "Refusing VENV_DIR outside the OMNI-Link repository: ${VENV_DIR}" >&2
    exit 2
  fi
  if [[ -e "${VENV_DIR}" && ! -f "${VENV_DIR}/pyvenv.cfg" ]]; then
    echo "Refusing to reuse a directory that is not a Python virtualenv: ${VENV_DIR}" >&2
    exit 2
  fi
}

install_python_packages() {
  if ! need_cmd "${PYTHON_BIN}"; then
    echo "Python command not found: ${PYTHON_BIN}" >&2
    exit 1
  fi
  validate_venv_dir

  log "Creating Python virtual environment at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"

  # shellcheck source=/dev/null
  source "${VENV_DIR}/bin/activate"

  log "Installing Python dependencies"
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install -r "${ROOT_DIR}/requirements.txt"
}

verify_runtime_dependencies() {
  local missing=()
  local tool
  for tool in ffmpeg mavlink-routerd ip ping ss; do
    if ! need_cmd "${tool}"; then
      missing+=("${tool}")
    fi
  done
  if [[ ! -x "${MEDIAMTX_BIN}" ]]; then
    missing+=("MediaMTX at ${MEDIAMTX_BIN}")
  fi
  if (( ${#missing[@]} > 0 )); then
    warn "Setup is incomplete; missing runtime dependencies: ${missing[*]}"
    warn "No desktop packages were removed. Install the missing tools separately or opt in with ALLOW_SYSTEM_CHANGES=1."
    return 1
  fi
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

  if [[ -x "${MEDIAMTX_BIN}" ]]; then
    log "MediaMTX already installed at ${MEDIAMTX_BIN}"
    return
  fi

  if [[ "${ALLOW_SYSTEM_CHANGES}" != "1" ]]; then
    warn "MediaMTX is missing; system installation is disabled. Set ALLOW_SYSTEM_CHANGES=1 to opt in."
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

Optional environment flags:
  ALLOW_SYSTEM_CHANGES=1 ./setup.sh  # opt in to guarded system installation
  ALLOW_SYSTEM_CHANGES=1 BUILD_MAVLINK_ROUTER_FROM_SOURCE=1 ./setup.sh
  INSTALL_MEDIAMTX=0 ./setup.sh
  INSTALL_MAVLINK_ROUTER=0 ./setup.sh

EOF
}

main() {
  if [[ "${ALLOW_SYSTEM_CHANGES}" != "0" && "${ALLOW_SYSTEM_CHANGES}" != "1" ]] ||
    [[ "${BUILD_MAVLINK_ROUTER_FROM_SOURCE}" != "0" && "${BUILD_MAVLINK_ROUTER_FROM_SOURCE}" != "1" ]]; then
    echo "ALLOW_SYSTEM_CHANGES and BUILD_MAVLINK_ROUTER_FROM_SOURCE must be 0 or 1" >&2
    exit 2
  fi
  validate_venv_dir
  install_apt_packages
  install_mavlink_router
  install_python_packages
  install_mediamtx
  verify_runtime_dependencies
  print_summary
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
