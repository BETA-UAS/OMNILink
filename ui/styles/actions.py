ACTION_STYLES = """
    QPushButton,
    QToolButton {
        color: #f2f2ef;
        background: rgba(10, 14, 15, 190);
        border: 1px solid rgba(98, 122, 122, 105);
        border-radius: 6px;
        padding: 7px 12px;
        font-weight: 800;
        min-height: 28px;
    }

    QPushButton:hover,
    QToolButton:hover {
        color: #ffffff;
        background: #1a1f1f;
        border-color: #d7dbdb;
    }

    QPushButton:pressed,
    QToolButton:pressed {
        color: #070909;
        background: #ffffff;
        border-color: #ffffff;
        padding-top: 8px;
        padding-bottom: 6px;
    }

    QPushButton:focus,
    QToolButton:focus {
        border: 1px solid #ffffff;
    }

    QPushButton:disabled,
    QToolButton:disabled {
        color: #6f7777;
        background: #151919;
        border-color: #2a3030;
    }

    QPushButton[role="primary"] {
        color: #070909;
        background: #f2f2ef;
        border-color: #f2f2ef;
    }

    QPushButton[role="primary"]:hover {
        color: #070909;
        background: #ffffff;
        border-color: #ffffff;
    }

    QPushButton[role="primary"]:pressed {
        color: #ffffff;
        background: #343a3a;
        border-color: #f2f2ef;
    }

    QPushButton[role="danger"] {
        color: #ffffff;
        background: #8f241f;
        border-color: #c24038;
    }

    QPushButton[role="danger"]:hover {
        background: #b52d27;
        border-color: #e2564d;
    }

    QPushButton[role="danger"]:pressed {
        background: #7f1d19;
        border-color: #c24038;
    }

    QPushButton[role="primary"]:disabled,
    QPushButton[role="danger"]:disabled {
        color: #6f7777;
        background: #151919;
        border-color: #2a3030;
    }

    QPushButton[role="secondary"],
    QToolButton[role="secondary"] {
        color: #f2f2ef;
        background: rgba(13, 16, 16, 215);
    }

    QPushButton[role="secondary"]:hover,
    QToolButton[role="secondary"]:hover {
        background: #1a1f1f;
        border-color: #d7dbdb;
    }

    QToolButton[role="toggle"]:checked {
        color: #070909;
        background: #f2f2ef;
        border-color: #f2f2ef;
    }

    QToolButton[role="toggle"]:checked:hover {
        color: #070909;
        background: #ffffff;
        border-color: #ffffff;
    }
"""
