"""Главное окно лаунчера."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import QByteArray, QThread, QTimer, Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QStackedWidget, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from .. import APP_NAME, winapi
from ..actions import ACTIONS, ACTIONS_BY_ID
from ..config import Settings
from ..engine import Engine
from ..worker import LaunchWorker
from . import theme
from .icon import app_icon, draw_icon
from .gaming_page import GamingPage
from .settings_dialog import SettingsDialog
from .toast import ToastManager
from .widgets import ActionCard, GlowButton

log = logging.getLogger(__name__)

STATUS_INTERVAL_MS = 2000
TWO_COLUMN_MIN_WIDTH = 900   # ширина окна для 2 колонок карточек
COMPACT_MAX_WIDTH = 760      # уже этого — компактная шапка
LAUNCH_TEXT = "▶   ЗАПУСТИТЬ МОЙ СЕТАП"


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, engine: Engine) -> None:
        super().__init__()
        self.settings = settings
        self.engine = engine
        self.cards: dict[str, ActionCard] = {}
        self._thread: QThread | None = None
        self._worker: LaunchWorker | None = None
        self._minimize_after_run = False
        self._really_quit = False
        self._columns = 0

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(560, 600)
        self.resize(1040, 760)
        self._restore_geometry()

        self._build_ui()
        self._build_tray()
        self.toasts = ToastManager(self.centralWidget())

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(STATUS_INTERVAL_MS)
        self._status_timer.timeout.connect(self.refresh_statuses)
        self.refresh_statuses()
        self._status_timer.start()
        self._update_selection_label()

    # ================================================================== UI
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 18, 22, 16)
        outer.setSpacing(14)

        # --- шапка
        header = QHBoxLayout()
        header.setSpacing(12)
        logo_icon = QLabel()
        logo_icon.setPixmap(draw_icon(44))
        logo_icon.setFixedSize(44, 44)
        header.addWidget(logo_icon)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        logo = QLabel(f'<span style="color:#ffffff">PRO</span><span style="color:{theme.ACCENT}">SETUP</span>')
        logo.setObjectName("logo")
        tagline = QLabel("LAUNCHER  ·  CS2  ·  FACEIT")
        tagline.setObjectName("tagline")
        font = tagline.font()
        font.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        tagline.setFont(font)
        brand.addWidget(logo)
        brand.addWidget(tagline)
        header.addLayout(brand)
        header.addStretch(1)

        self.open_all_btn = QPushButton()
        self.open_all_btn.setObjectName("accentOutline")
        self.open_all_btn.setToolTip("Запустить все включённые действия")
        self.open_all_btn.clicked.connect(lambda: self.launch_selected(minimize_after=False))
        settings_btn = QPushButton()
        settings_btn.setObjectName("secondary")
        settings_btn.setToolTip("Пути к программам и поведение лаунчера")
        settings_btn.clicked.connect(self.open_settings)
        tray_btn = QPushButton()
        tray_btn.setObjectName("secondary")
        tray_btn.setToolTip("Свернуть приложение в системный трей")
        tray_btn.clicked.connect(self.hide_to_tray)
        # (кнопка, полный текст, компактный текст)
        self._header_buttons = [
            (self.open_all_btn, "⚡ Открыть всё", "⚡ Всё"),
            (settings_btn, "⚙ Настройки", "⚙"),
            (tray_btn, "⤓ В трей", "⤓"),
        ]
        self._compact: bool | None = None
        for btn, _full, _short in self._header_buttons:
            btn.setCursor(Qt.PointingHandCursor)
            header.addWidget(btn)
        outer.addLayout(header)

        # --- главный блок с большой кнопкой
        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 20, 22, 16)
        hero_layout.setSpacing(12)
        self.launch_btn = GlowButton(LAUNCH_TEXT)
        self.launch_btn.setObjectName("launchButton")
        self.launch_btn.setMinimumHeight(70)
        self.launch_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        launch_font = self.launch_btn.font()
        launch_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        self.launch_btn.setFont(launch_font)
        self.launch_btn.clicked.connect(lambda: self.launch_selected(minimize_after=True))
        hero_layout.addWidget(self.launch_btn)

        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        hero_layout.addWidget(self.progress)

        status_row = QHBoxLayout()
        self.hero_status = QLabel("Готово к запуску")
        self.hero_status.setObjectName("heroStatus")
        self.selection_label = QLabel()
        self.selection_label.setObjectName("selection")
        status_row.addWidget(self.hero_status, 1)
        status_row.addWidget(self.selection_label)
        hero_layout.addLayout(status_row)
        outer.addWidget(hero)

        # --- вкладки: действия сетапа / My Gaming Setup
        section = QHBoxLayout()
        section.setSpacing(6)
        self.tab_buttons: list[QPushButton] = []
        for index, text in enumerate(("ДЕЙСТВИЯ СЕТАПА", "MY GAMING SETUP")):
            tab = QPushButton(text)
            tab.setObjectName("tab")
            tab.setCheckable(True)
            tab.setCursor(Qt.PointingHandCursor)
            f = tab.font()
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
            tab.setFont(f)
            tab.clicked.connect(lambda _=False, i=index: self.show_tab(i))
            section.addWidget(tab)
            self.tab_buttons.append(tab)
        self.section_hint = QLabel("Переключатель — включить в сетап  ·  статусы обновляются автоматически")
        self.section_hint.setObjectName("hint")
        section.addStretch(1)
        section.addWidget(self.section_hint)
        outer.addLayout(section)

        # --- карточки
        self.cards_host = QWidget()
        self.cards_host.setObjectName("cardsHost")
        self.grid = QGridLayout(self.cards_host)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(14)
        for action in ACTIONS:
            card = ActionCard(action, self.settings.is_enabled(action.id))
            card.toggled.connect(self._on_card_toggled)
            card.launch_requested.connect(self.launch_single)
            card.browse_requested.connect(self.browse_path)
            self.cards[action.id] = card
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.cards_host)

        self.gaming_page = GamingPage(self.engine)
        self.gaming_page.notify.connect(self.notify)
        self.gaming_page.launch_requested.connect(self.launch_single)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.scroll)
        self.pages.addWidget(self.gaming_page)
        outer.addWidget(self.pages, 1)
        self.show_tab(0)
        self._reflow(force=True)

    def show_tab(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for i, tab in enumerate(self.tab_buttons):
            tab.setChecked(i == index)
        self.section_hint.setText(
            "Переключатель — включить в сетап  ·  статусы обновляются автоматически" if index == 0
            else "Мышь и клавиатура Logitech · CS2")
        if index == 1:
            self.gaming_page.refresh()

    def _reflow(self, force: bool = False) -> None:
        """2 колонки на широком окне, 1 — на узком; компактная шапка на маленьком."""
        width = self.width()
        compact = width < COMPACT_MAX_WIDTH
        if compact != self._compact:
            self._compact = compact
            for btn, full, short in self._header_buttons:
                btn.setText(short if compact else full)
            self.section_hint.setVisible(not compact)
        columns = 2 if width >= TWO_COLUMN_MIN_WIDTH else 1
        if columns == self._columns and not force:
            return
        self._columns = columns
        for card in self.cards.values():
            self.grid.removeWidget(card)
        for i in range(self.grid.rowCount()):
            self.grid.setRowStretch(i, 0)
        for i, action in enumerate(ACTIONS):
            self.grid.addWidget(self.cards[action.id], i // columns, i % columns)
        for c in range(2):
            self.grid.setColumnStretch(c, 1 if c < columns else 0)
        self.grid.setRowStretch((len(ACTIONS) + columns - 1) // columns, 1)

    def _build_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("Системный трей недоступен")
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu(self)
        show_action = QAction("Показать окно", self)
        show_action.triggered.connect(self.show_from_tray)
        self.tray_launch_action = QAction("▶ Запустить мой сетап", self)
        self.tray_launch_action.triggered.connect(lambda: self.launch_selected(minimize_after=False))
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(self.tray_launch_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ============================================================= статусы
    def refresh_statuses(self) -> None:
        try:
            statuses = self.engine.statuses()
            for aid, status in statuses.items():
                self.cards[aid].set_status(status, self.engine.describe_target(aid))
            for aid in self.engine.pop_timeouts():
                action = ACTIONS_BY_ID[aid]
                self.notify(f"{action.title} не появился в процессах",
                            "Программа была запущена, но её процесс не обнаружен в течение минуты. "
                            "Возможно, она закрылась или запросила обновление.", "warning")
            if self.tray:
                running = sum(1 for s in statuses.values() if s.state == "running")
                self.tray.setToolTip(f"{APP_NAME} — активно: {running} из {len(statuses)}")
        except Exception:
            log.exception("Ошибка обновления статусов")

    def _update_selection_label(self) -> None:
        count = sum(1 for a in ACTIONS if self.settings.is_enabled(a.id))
        self.selection_label.setText(f"Выбрано: {count} из {len(ACTIONS)}")

    def _on_card_toggled(self, action_id: str, checked: bool) -> None:
        self.settings.set_enabled(action_id, checked)
        self.settings.save()
        self._update_selection_label()

    # ============================================================== запуск
    def launch_selected(self, minimize_after: bool = False) -> None:
        ids = [a.id for a in ACTIONS if self.settings.is_enabled(a.id)]
        if not ids:
            self.notify("Ничего не выбрано", "Включите переключатели у нужных действий.", "warning")
            return
        self._start_run(ids, float(self.settings["launch_delay"]), minimize_after)

    def launch_single(self, action_id: str) -> None:
        self._start_run([action_id], 0.0, False)

    def _start_run(self, ids: list[str], delay: float, minimize_after: bool) -> None:
        if self._thread is not None:
            self.notify("Запуск уже выполняется", "Дождитесь окончания текущего сетапа.", "info")
            return
        self._minimize_after_run = minimize_after
        self._run_total = len(ids)
        self._set_busy(True)
        self.progress.setRange(0, len(ids))
        self.progress.setValue(0)

        self._thread = QThread(self)
        self._worker = LaunchWorker(self.engine, ids, delay)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_finished.connect(self._on_step_finished)
        self._worker.finished.connect(self._on_run_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _set_busy(self, busy: bool) -> None:
        self.launch_btn.setEnabled(not busy)
        self.launch_btn.setText("ЗАПУСК…" if busy else LAUNCH_TEXT)
        self.open_all_btn.setEnabled(not busy)
        if self.tray:
            self.tray_launch_action.setEnabled(not busy)
        for card in self.cards.values():
            card.set_busy(busy)

    def _on_step_started(self, action_id: str, index: int, total: int) -> None:
        title = ACTIONS_BY_ID[action_id].title
        self.hero_status.setText(f"Запуск: {title}  ({index + 1}/{total})…")
        self.refresh_statuses()

    def _on_step_finished(self, action_id: str, ok: bool, skipped: bool, message: str) -> None:
        self.progress.setValue(self.progress.value() + 1)
        title = ACTIONS_BY_ID[action_id].title
        if not ok:
            self.notify(f"{title}: ошибка", message, "error")
        elif self.settings["notifications"]:
            self.notify(message if not skipped else f"{title}: пропущено",
                        "" if not skipped else message,
                        "success" if not skipped else "info")
        self.refresh_statuses()

    def _on_run_finished(self, ok: int, skipped: int, failed: int) -> None:
        parts = [f"запущено: {ok}", f"уже работало: {skipped}", f"ошибок: {failed}"]
        summary = ", ".join(parts)
        self.hero_status.setText(("Готово — " if not failed else "Завершено с ошибками — ") + summary)
        if self._run_total > 1:
            kind = "success" if not failed else "warning"
            self.notify("Сетап готов" if not failed else "Сетап выполнен частично", summary.capitalize(), kind)
        if self._minimize_after_run and self.settings["minimize_after_launch"] and not failed:
            QTimer.singleShot(900, self.hide_to_tray)

    def _cleanup_thread(self) -> None:
        if self._worker:
            self._worker.deleteLater()
        if self._thread:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self._set_busy(False)
        self.refresh_statuses()
        if self.pages.currentIndex() == 1:
            self.gaming_page.refresh()

    # =========================================================== настройки
    def browse_path(self, action_id: str) -> None:
        action = ACTIONS_BY_ID[action_id]
        current = self.engine.resolve_path(action_id).path or ""
        start = str(Path(current).parent) if current else os.environ.get("ProgramFiles", "")
        path, _ = QFileDialog.getOpenFileName(
            self, f"Укажите {action.exe_name} ({action.title})", start,
            "Программы (*.exe);;Все файлы (*)",
        )
        if not path:
            return
        path = os.path.normpath(path)
        if not os.path.isfile(path) or not path.lower().endswith(".exe"):
            self.notify("Неверный файл", "Нужно выбрать существующий исполняемый файл .exe.", "error")
            return
        self.settings.set_path(action_id, path)
        self.settings.save()
        if Path(path).name.lower() != action.exe_name:
            self.notify(f"Путь для {action.title} сохранён",
                        f"Выбран {Path(path).name} вместо {action.exe_name} — статус будет "
                        "проверяться по имени выбранного файла.", "warning")
        else:
            self.notify(f"Путь для {action.title} сохранён", path, "success")
        self.refresh_statuses()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.engine, self)
        winapi.enable_dark_title_bar(int(dialog.winId()))
        if dialog.exec():
            self.notify("Настройки сохранены", "", "success")
        self.refresh_statuses()

    # =========================================================== уведомления
    def notify(self, title: str, text: str = "", kind: str = "info") -> None:
        log.info("[%s] %s %s", kind, title, text)
        if self.isVisible() and not self.isMinimized():
            self.toasts.show(title, text, kind)
        elif self.tray and self.tray.supportsMessages():
            icon = {
                "error": QSystemTrayIcon.Critical,
                "warning": QSystemTrayIcon.Warning,
            }.get(kind, QSystemTrayIcon.Information)
            self.tray.showMessage(title, text or APP_NAME, icon, 4000)

    # ================================================================ трей
    def hide_to_tray(self) -> None:
        if not self.tray:
            self.showMinimized()
            return
        self.hide()
        if not self.settings["tray_hint_shown"]:
            self.tray.showMessage(APP_NAME, "Приложение работает в трее. Нажмите на значок, чтобы открыть окно.",
                                  QSystemTrayIcon.Information, 4000)
            self.settings["tray_hint_shown"] = True
            self.settings.save()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                self.hide_to_tray()
            else:
                self.show_from_tray()

    def quit_app(self) -> None:
        self._really_quit = True
        self.close()

    # ============================================================ события
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        winapi.enable_dark_title_bar(int(self.winId()))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "grid"):
            self._reflow()
        if hasattr(self, "toasts"):
            self.toasts.reposition()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._really_quit and self.settings["close_to_tray"] and self.tray:
            event.ignore()
            self.hide_to_tray()
            return
        self._save_geometry()
        self._status_timer.stop()
        if self._worker:
            self._worker.cancel()
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
        if self.tray:
            self.tray.hide()
        event.accept()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def _save_geometry(self) -> None:
        self.settings["window_geometry"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.settings.save()

    def _restore_geometry(self) -> None:
        data = self.settings["window_geometry"]
        if data:
            try:
                self.restoreGeometry(QByteArray.fromBase64(data.encode("ascii")))
            except Exception:
                log.warning("Не удалось восстановить положение окна")

    def show_error(self, title: str, text: str) -> None:
        QMessageBox.critical(self, title, text)
