SCROLLBAR_STYLES = """
    QScrollBar:vertical {
        background: transparent;
        width: 11px;
        margin: 2px;
    }

    QScrollBar::handle:vertical {
        background: #3a4242;
        border-radius: 4px;
        min-height: 24px;
    }

    QScrollBar::handle:vertical:hover {
        background: #d7dbdb;
    }

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""
