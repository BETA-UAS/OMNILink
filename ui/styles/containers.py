CONTAINER_STYLES = """
    QWidget#toolbar {
        background: rgba(5, 8, 9, 185);
        border: 1px solid rgba(77, 105, 104, 90);
        border-radius: 8px;
    }

    QScrollArea {
        background: transparent;
        border: none;
    }

    QGroupBox {
        color: #f2f2ef;
        background: rgba(7, 10, 11, 205);
        border: 1px solid rgba(77, 105, 104, 105);
        border-radius: 7px;
        font-weight: 900;
        margin-top: 18px;
        padding-top: 12px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0px 7px;
        color: #ffffff;
        background: #000000;
        border: none;
        border-radius: 3px;
        font-size: 12px;
    }

    QGroupBox#innerPanel {
        background: rgba(9, 13, 14, 170);
        border-color: rgba(77, 105, 104, 90);
        margin-top: 15px;
        padding-top: 10px;
    }

    QFrame#compactPanel {
        background: rgba(9, 13, 14, 170);
        border: 1px solid rgba(77, 105, 104, 90);
        border-radius: 6px;
    }

    QFrame#statusCard {
        background: rgba(9, 13, 14, 170);
        border: 1px solid rgba(77, 105, 104, 90);
        border-radius: 6px;
    }

    QFrame#statusCard[state="ok"] {
        background: #101715;
        border-color: #2e7d66;
    }

    QFrame#statusCard[state="error"] {
        background: #171211;
        border-color: #7e3b35;
    }

    QFrame#sourceCard {
        background: rgba(6, 9, 10, 190);
        border: 1px solid rgba(105, 128, 127, 105);
        border-radius: 6px;
    }

    QFrame#sourceCard[active="true"] {
        background: rgba(11, 17, 18, 205);
        border-color: rgba(178, 205, 202, 130);
    }

    QFrame#sourceCard[active="false"] {
        background: #0b0d0d;
        border-color: #262c2c;
    }
"""
