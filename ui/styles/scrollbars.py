SCROLLBAR_STYLES = """
    QScrollBar:vertical {
        background: transparent;
        width: 11px;
        margin: 2px;
    }

    QScrollBar::handle:vertical {
        background: #b7c4d2;
        border-radius: 5px;
        min-height: 24px;
    }

    QScrollBar::handle:vertical:hover {
        background: #94a5b8;
    }

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""
