#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="OMNILink"
BINARY_NAME="omnilink"
PYTHON_BIN="${PYTHON:-python3}"
VENV_DIR="${ROOT_DIR}/.venv-appimage"
APPIMAGE_BUILD_DIR="${ROOT_DIR}/build/appimage"
APPDIR="${APPIMAGE_BUILD_DIR}/${APP_NAME}.AppDir"
APPIMAGETOOL_DIR="${APPIMAGE_BUILD_DIR}/tools"

case "$(uname -m)" in
  x86_64|amd64)
    APPIMAGE_ARCH="x86_64"
    ;;
  aarch64|arm64)
    APPIMAGE_ARCH="aarch64"
    ;;
  *)
    echo "Unsupported AppImage architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

VERSION="${VERSION:-$(git -C "${ROOT_DIR}" describe --tags --always --dirty 2>/dev/null || echo dev)}"
OUTPUT="${ROOT_DIR}/dist/${APP_NAME}-${VERSION}-${APPIMAGE_ARCH}.AppImage"
APPIMAGETOOL="${APPIMAGETOOL_DIR}/appimagetool-${APPIMAGE_ARCH}.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${APPIMAGE_ARCH}.AppImage"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python command not found: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "${ROOT_DIR}/requirements.txt" pyinstaller

rm -rf "${ROOT_DIR}/build/pyinstaller" "${ROOT_DIR}/dist/${BINARY_NAME}" "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPIMAGETOOL_DIR}" "${ROOT_DIR}/dist"

pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "${BINARY_NAME}" \
  --distpath "${ROOT_DIR}/dist" \
  --workpath "${ROOT_DIR}/build/pyinstaller" \
  --specpath "${ROOT_DIR}/build/pyinstaller" \
  --add-data "${ROOT_DIR}/config/settings.json:config" \
  --add-data "${ROOT_DIR}/ui/assets:ui/assets" \
  "${ROOT_DIR}/main.py"

cp -a "${ROOT_DIR}/dist/${BINARY_NAME}" "${APPDIR}/usr/bin/${BINARY_NAME}"
cp "${ROOT_DIR}/packaging/appimage/AppRun" "${APPDIR}/AppRun"
cp "${ROOT_DIR}/packaging/appimage/omnilink.desktop" "${APPDIR}/omnilink.desktop"
cp "${ROOT_DIR}/packaging/appimage/omnilink.svg" "${APPDIR}/omnilink.svg"
chmod +x "${APPDIR}/AppRun"

for tool in ffmpeg mavlink-routerd; do
  if command -v "${tool}" >/dev/null 2>&1; then
    cp "$(command -v "${tool}")" "${APPDIR}/usr/bin/${tool}"
  else
    echo "Warning: ${tool} not found; the AppImage will use the host ${tool} if available." >&2
  fi
done

if [[ ! -x "${APPIMAGETOOL}" ]]; then
  if command -v curl >/dev/null 2>&1; then
    curl -L "${APPIMAGETOOL_URL}" -o "${APPIMAGETOOL}"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "${APPIMAGETOOL}" "${APPIMAGETOOL_URL}"
  else
    echo "Install curl or wget to download appimagetool." >&2
    exit 1
  fi
  chmod +x "${APPIMAGETOOL}"
fi

rm -f "${OUTPUT}"
ARCH="${APPIMAGE_ARCH}" VERSION="${VERSION}" APPIMAGE_EXTRACT_AND_RUN=1 \
  "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT}"

chmod +x "${OUTPUT}"
echo "Created ${OUTPUT}"
