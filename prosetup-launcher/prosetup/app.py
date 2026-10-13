"""Точка сборки приложения: логирование, единственный экземпляр, обработка ошибок."""

from __future__ import annotations

import getpass
import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_ID, APP_NAME, __version__, winapi
from .config import Settings, app_data_dir
from .engine import Engine
from .ui.icon import app_icon
from .ui.main_window import MainWindow
from .ui.theme import STYLESHEET

log = logging.getLogger("prosetup")


def _setup_logging() -> None:
    handlers: list[logging.Handler] = []
    try:
        handlers.append(RotatingFileHandler(app_data_dir() / "launcher.log", maxBytes=512_000,
                                            backupCount=2, encoding="utf-8"))
    except OSError:
        pass
    if sys.stderr is not None:  # в собранном .exe без консоли stderr отсутствует
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return f"{APP_ID}-{user}"


def _activate_existing_instance() -> bool:
    """Если лаунчер уже открыт — показать его окно и вернуть True."""
    socket = QLocalSocket()
    socket.connectToServer(_server_name())
    if socket.waitForConnected(300):
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def run() -> int:
    _setup_logging()
    log.info("%s %s запускается", APP_NAME, __version__)
    winapi.set_app_user_model_id(f"{APP_ID}.App")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_ID)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)  # окно может жить в трее
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    if _activate_existing_instance():
        log.info("Лаунчер уже запущен — активировано существующее окно")
        return 0

    server = QLocalServer()
    QLocalServer.removeServer(_server_name())  # остаток после аварийного завершения
    server.listen(_server_name())

    try:
        settings = Settings()
        engine = Engine(settings)
        window = MainWindow(settings, engine)
    except Exception as exc:
        log.exception("Не удалось запустить приложение")
        QMessageBox.critical(None, APP_NAME, f"Не удалось запустить приложение:\n{exc}")
        return 1

    def _on_new_connection() -> None:
        conn = server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(lambda: (conn.readAll(), window.show_from_tray()))
            conn.disconnected.connect(conn.deleteLater)

    server.newConnection.connect(_on_new_connection)

    def _excepthook(exc_type, exc, tb) -> None:
        log.error("Необработанная ошибка:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        try:
            window.notify("Произошла ошибка", f"{exc_type.__name__}: {exc}. Подробности в журнале.", "error")
        except Exception:
            pass

    sys.excepthook = _excepthook

    if "--minimized" in sys.argv and window.tray:
        QTimer.singleShot(0, window.hide_to_tray)
    else:
        window.show()
    code = app.exec()
    server.close()
    log.info("Завершение работы (код %s)", code)
    return code
