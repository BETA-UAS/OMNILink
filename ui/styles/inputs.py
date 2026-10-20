INPUT_STYLES = """
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QComboBox {
        color: #f2f2ef;
        background: rgba(5, 8, 9, 215);
        border: 1px solid rgba(76, 98, 98, 120);
        border-radius: 6px;
        padding: 5px 8px;
        min-height: 25px;
        selection-background-color: #ffffff;
        selection-color: #070909;
    }

    QPlainTextEdit {
        padding: 7px;
    }

    QLineEdit:focus,
    QPlainTextEdit:focus,
    QSpinBox:focus,
    QComboBox:focus {
        border: 1px solid #f2f2ef;
        background: #0f1515;
    }

    QLineEdit:disabled,
    QPlainTextEdit:disabled,
    QSpinBox:disabled,
    QComboBox:disabled {
        color: #6f7777;
        background: #151919;
        border-color: #2a3030;
    }

    QCheckBox,
    QRadioButton {
        background: transparent;
        spacing: 7px;
        font-weight: 700;
        color: #e4e7e7;
    }

    QCheckBox::indicator,
    QRadioButton::indicator {
        width: 20px;
        height: 20px;
        border: 1px solid #6f7777;
        background: #070909;
    }

    QCheckBox::indicator {
        border-radius: 4px;
    }

    QRadioButton::indicator {
        border-radius: 9px;
    }

    QCheckBox::indicator:hover,
    QRadioButton::indicator:hover {
        border-color: #ffffff;
        background: #151919;
    }

    QCheckBox::indicator:checked {
        image: __CHECKMARK_IMAGE__;
        color: #070909;
        background: #18c9cd;
        border: 1px solid #30e0e3;
    }

    QCheckBox::indicator:checked:hover {
        background: #ffffff;
        border-color: #ffffff;
    }

    QCheckBox::indicator:checked:disabled,
    QRadioButton::indicator:checked:disabled {
        background: #6f7777;
        border-color: #6f7777;
    }

    QCheckBox::indicator:unchecked:disabled,
    QRadioButton::indicator:unchecked:disabled {
        background: #151919;
        border-color: #2a3030;
    }

    QRadioButton::indicator:checked {
        image: __RADIO_DOT_IMAGE__;
        background: #070909;
        border: 1px solid #f2f2ef;
    }

    QCheckBox::indicator:checked {
        border-image: none;
    }
"""
