"""FACEFUNNY entry point.

A standalone joke radar simulator. It does not interact with Counter-Strike 2
in any way: no process access, no memory reading, no game data, no network.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import traceback

LOG_PATH = os.path.join(tempfile.gettempdir(), "facefunny.log")


def _setup_logging() -> None:
    handlers = [logging.StreamHandler(sys.stderr)] if sys.stderr else []
    try:
        handlers.append(logging.FileHandler(LOG_PATH, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    _setup_logging()
    log = logging.getLogger("facefunny")

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print("PySide6 is not installed. Run:  pip install -r requirements.txt", file=sys.stderr)
        return 1

    from app import __version__, theme
    from app.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("FACEFUNNY")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.stylesheet())

    def excepthook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.error("Unhandled error:\n%s", text)
        QMessageBox.critical(None, "FACEFUNNY — error",
                             f"An unexpected error occurred:\n\n{exc}\n\nDetails were written to:\n{LOG_PATH}")

    sys.excepthook = excepthook

    window = MainWindow()
    window.show()
    log.info("FACEFUNNY %s started", __version__)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
