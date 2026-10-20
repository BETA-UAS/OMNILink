APP_STYLES = """
    QWidget {
        color: #f2f2ef;
        background: transparent;
        font-family: "Liberation Sans", "Inter", "Segoe UI", Arial, sans-serif;
        font-size: 15px;
    }

    QMainWindow {
        background: #0f171c;
    }

    QWidget#mainSurface {
        background: #0f171c;
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
        background: #111c23;
        border-top: 1px solid #2a3030;
        font-weight: 700;
        min-height: 46px;
    }

    QTabWidget#mainTabs::pane {
        background: transparent;
        border: none;
        border-top: 1px solid #2a3438;
        top: -1px;
    }

    QTabBar::tab {
        color: #9eafb7;
        background: transparent;
        border: none;
        border-bottom: 3px solid transparent;
        min-width: 108px;
        padding: 12px 14px 11px 14px;
        font-size: 18px;
        font-weight: 800;
    }

    QTabBar::tab:selected {
        color: #ffffff;
        border-bottom-color: #1bc4c8;
    }

    QTabBar::tab:hover:!selected {
        color: #d7e5e8;
    }
"""
