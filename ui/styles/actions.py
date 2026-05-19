ACTION_STYLES = """
    QPushButton,
    QToolButton {
        color: #172336;
        background: #ffffff;
        border: 1px solid #c3cedb;
        border-radius: 7px;
        padding: 7px 13px;
        font-weight: 800;
        min-height: 29px;
    }

    QPushButton:hover,
    QToolButton:hover {
        color: #0f2240;
        background: #f1f6fb;
        border-color: #8fa2b8;
    }

    QPushButton:pressed,
    QToolButton:pressed {
        background: #e2ebf5;
        border-color: #70869f;
        padding-top: 8px;
        padding-bottom: 6px;
    }

    QPushButton:focus,
    QToolButton:focus {
        border: 1px solid #2563eb;
    }

    QPushButton:disabled,
    QToolButton:disabled {
        color: #9ba7b4;
        background: #edf2f7;
        border-color: #d8e2ec;
    }

    QPushButton[role="primary"] {
        color: #ffffff;
        background: #176b4c;
        border-color: #11583e;
    }

    QPushButton[role="primary"]:hover {
        background: #1d7d59;
        border-color: #146044;
    }

    QPushButton[role="primary"]:pressed {
        background: #11583e;
        border-color: #0d4632;
    }

    QPushButton[role="danger"] {
        color: #ffffff;
        background: #bd2d22;
        border-color: #9f241b;
    }

    QPushButton[role="danger"]:hover {
        background: #d23a2e;
        border-color: #ae2a20;
    }

    QPushButton[role="danger"]:pressed {
        background: #9f241b;
        border-color: #842018;
    }

    QPushButton[role="primary"]:disabled,
    QPushButton[role="danger"]:disabled {
        color: #9ba7b4;
        background: #edf2f7;
        border-color: #d8e2ec;
    }

    QPushButton[role="secondary"],
    QToolButton[role="secondary"] {
        color: #1d334c;
        background: #f9fbfd;
    }

    QPushButton[role="secondary"]:hover,
    QToolButton[role="secondary"]:hover {
        background: #edf5fc;
        border-color: #8faac4;
    }

    QToolButton[role="toggle"]:checked {
        color: #17426b;
        background: #dcecff;
        border-color: #79a9d8;
    }

    QToolButton[role="toggle"]:checked:hover {
        background: #d2e6fc;
        border-color: #5f93c6;
    }
"""
