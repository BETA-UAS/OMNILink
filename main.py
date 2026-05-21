#!/usr/bin/env python3
import json
import logging
import signal
import sys
from pathlib import Path

from PyQt5 import QtWidgets
from ui.main_window import MainWindow
from ui.styles import apply_styles


def app_base_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def load_config(config_path: str = "config/settings.json") -> dict:
    try:
        path = Path(config_path)
        if not path.is_absolute():
            path = app_base_path() / path
        if not path.exists():
            logging.warning(f"Config file not found at {path}.")
            return {}  # Fallback to empty dict for the default config

        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        sys.exit(1)


def main():
    setup_logging()
    logging.info("Starting OMNI-Link Router Application")

    # Allow graceful exit on Linux via Ctrl+C
    if sys.platform.startswith("linux"):
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    config = load_config()

    app = QtWidgets.QApplication(sys.argv)
    apply_styles(app)

    window = MainWindow(config)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
