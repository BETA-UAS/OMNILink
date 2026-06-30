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

STYLESHEET = "\n".join(part.strip() for part in STYLE_PARTS)


def apply_styles(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Liberation Sans", 10))
    app.setStyleSheet(STYLESHEET)
