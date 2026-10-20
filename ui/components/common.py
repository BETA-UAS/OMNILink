from PyQt5 import QtWidgets


def refresh_style(widget: QtWidgets.QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_button_role(button: QtWidgets.QAbstractButton, role: str) -> None:
    button.setProperty("role", role)
    refresh_style(button)


def set_service_state(widget: QtWidgets.QWidget, state: str) -> None:
    widget.setProperty("serviceState", state)
    refresh_style(widget)


def set_muted_label(lbl: QtWidgets.QLabel) -> None:
    lbl.setObjectName("mutedInfo")
    refresh_style(lbl)


def set_field_value_label(lbl: QtWidgets.QLabel) -> None:
    lbl.setObjectName("fieldValue")
    refresh_style(lbl)


def set_device_name_label(lbl: QtWidgets.QLabel) -> None:
    lbl.setObjectName("deviceName")
    refresh_style(lbl)


def set_status_label(lbl: QtWidgets.QLabel, text: str, ok=False, state: str = "") -> None:
    lbl.setText(text)
    lbl.setObjectName("statusPill")
    lbl.setProperty("state", state or ("ok" if ok else "error"))
    refresh_style(lbl)


def set_status_dot(lbl: QtWidgets.QLabel, ok=False, state: str = "") -> None:
    lbl.setObjectName("statusDot")
    lbl.setProperty("state", state or ("ok" if ok else "error"))
    refresh_style(lbl)


def set_status_card(card: QtWidgets.QFrame, ok=False, state: str = "") -> None:
    card.setProperty("state", state or ("ok" if ok else "error"))
    refresh_style(card)
