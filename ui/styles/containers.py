CONTAINER_STYLES = """
    QWidget#toolbar {
        background: #ffffff;
        border: 1px solid #d9e1ea;
        border-radius: 8px;
    }

    QScrollArea {
        background: transparent;
        border: none;
    }

    QGroupBox {
        color: #142033;
        background: #ffffff;
        border: 1px solid #d7e0ea;
        border-radius: 8px;
        font-weight: 900;
        margin-top: 18px;
        padding-top: 13px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 11px;
        padding: 3px 9px;
        color: #10233f;
        background: #eef4fb;
        border: 1px solid #d7e0ea;
        border-radius: 6px;
        font-size: 12px;
    }

    QGroupBox#innerPanel {
        background: #f9fbfd;
        border-color: #e0e7ef;
        margin-top: 15px;
        padding-top: 11px;
    }

    QFrame#compactPanel {
        background: #f9fbfd;
        border: 1px solid #e0e7ef;
        border-radius: 8px;
    }

    QFrame#statusCard {
        background: #f9fbfd;
        border: 1px solid #dde6ef;
        border-radius: 8px;
    }

    QFrame#statusCard[state="ok"] {
        background: #f0fbf5;
        border-color: #9fd5b7;
    }

    QFrame#statusCard[state="error"] {
        background: #fff6f4;
        border-color: #e6b3ae;
    }
"""
