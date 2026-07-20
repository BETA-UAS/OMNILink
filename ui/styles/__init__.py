import sys
from pathlib import Path

from PyQt5 import QtGui, QtWidgets
from ui.styles.actions import ACTION_STYLES
from ui.styles.app import APP_STYLES
from ui.styles.containers import CONTAINER_STYLES
from ui.styles.inputs import INPUT_STYLES
from ui.styles.labels import LABEL_STYLES
from ui.styles.scrollbars import SCROLLBAR_STYLES
from ui.styles.tables import TABLE_STYLES

STYLE_PARTS = (
    APP_STYLES,
    LABEL_STYLES,
    CONTAINER_STYLES,
    INPUT_STYLES,
    ACTION_STYLES,
    TABLE_STYLES,
    SCROLLBAR_STYLES,
)


def _app_base_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def _qss_image_url(path: Path) -> str:
    return f'url("{path.as_posix()}")'


def build_stylesheet() -> str:
    assets_dir = _app_base_path() / "ui" / "assets"
    stylesheet = "\n".join(part.strip() for part in STYLE_PARTS)
    return (
        stylesheet.replace("__CHECKMARK_IMAGE__", _qss_image_url(assets_dir / "checkmark.svg"))
        .replace("__RADIO_DOT_IMAGE__", _qss_image_url(assets_dir / "radio-dot.svg"))
    )


def apply_styles(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Liberation Sans", 10))
    app.setStyleSheet(build_stylesheet())
