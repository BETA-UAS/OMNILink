INPUT_STYLES = """
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QComboBox {
        color: #142033;
        background: #ffffff;
        border: 1px solid #c5d0dc;
        border-radius: 7px;
        padding: 6px 8px;
        min-height: 27px;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }

    QPlainTextEdit {
        padding: 8px;
    }

    QLineEdit:focus,
    QPlainTextEdit:focus,
    QSpinBox:focus,
    QComboBox:focus {
        border: 1px solid #2563eb;
        background: #fbfdff;
    }

    QLineEdit:disabled,
    QPlainTextEdit:disabled,
    QSpinBox:disabled,
    QComboBox:disabled {
        color: #8996a4;
        background: #edf2f7;
        border-color: #d8e2ec;
    }

    QCheckBox,
    QRadioButton {
        background: transparent;
        spacing: 0px;
        font-weight: 700;
    }

    QCheckBox::indicator,
    QRadioButton::indicator {
        width: 16px;
        height: 16px;
    }
"""
