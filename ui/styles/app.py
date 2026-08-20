APP_STYLES = """
    QWidget {
        color: #f2f2ef;
        background: transparent;
        font-family: "Liberation Sans", "Inter", "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }

    QMainWindow {
        background: #000000;
    }

    QWidget#mainSurface {
        background: qradialgradient(
            cx: 0.20,
            cy: 0.98,
            radius: 1.05,
            fx: 0.10,
            fy: 1.08,
            stop: 0 rgba(0, 92, 86, 112),
            stop: 0.24 rgba(0, 58, 68, 84),
            stop: 0.50 rgba(0, 24, 38, 56),
            stop: 0.76 rgba(0, 8, 17, 34),
            stop: 1 rgba(0, 0, 0, 255)
        );
    }

    QSplitter::handle {
        background: rgba(33, 43, 43, 120);
        margin: 0px 5px;
        border: none;
        border-radius: 3px;
    }

    QSplitter::handle:hover {
        background: #353d3d;
    }

    QStatusBar {
        color: #9ca3a3;
        background: #000000;
        border-top: 1px solid #2a3030;
        font-weight: 700;
    }
"""
