"""Диалог настроек: пути к программам и поведение лаунчера."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from .. import winapi
from ..actions import ACTIONS
from ..config import Settings, app_data_dir
from ..engine import Engine


class PathRow:
    def __init__(self, dialog: "SettingsDialog", grid: QGridLayout, row: int, action) -> None:
        self.dialog = dialog
        self.action = action
        title = QLabel(action.title)
        title.setStyleSheet("font-weight: 600;")
        self.edit = QLineEdit(dialog.settings.get_path(action.id))
        self.edit.setClearButtonEnabled(True)
        browse = QPushButton("Обзор…")
        browse.setObjectName("secondary")
        browse.setCursor(Qt.PointingHandCursor)
        auto = QPushButton("Авто")
        auto.setObjectName("secondary")
        auto.setCursor(Qt.PointingHandCursor)
        auto.setToolTip("Очистить ручной путь и заново найти программу автоматически")
        self.state = QLabel()
        self.state.setWordWrap(True)

        grid.addWidget(title, row * 2, 0)
        grid.addWidget(self.edit, row * 2, 1)
        grid.addWidget(browse, row * 2, 2)
        grid.addWidget(auto, row * 2, 3)
        grid.addWidget(self.state, row * 2 + 1, 1, 1, 3)

        browse.clicked.connect(self.browse)
        auto.clicked.connect(self.auto)
        self.edit.textChanged.connect(self.validate)
        self._update_placeholder()
        self.validate()

    def _update_placeholder(self) -> None:
        detected = self.dialog.engine.detected_path(self.action.id)
        self.edit.setPlaceholderText(f"Авто: {detected}" if detected else f"Авто: не найдено — укажите {self.action.exe_name}")

    def browse(self) -> None:
        current = self.edit.text().strip() or self.dialog.engine.detected_path(self.action.id) or ""
        start = str(Path(current).parent) if current else os.environ.get("ProgramFiles", "")
        path, _ = QFileDialog.getOpenFileName(
            self.dialog, f"Укажите {self.action.exe_name}", start,
            "Программы (*.exe);;Все файлы (*)",
        )
        if path:
            self.edit.setText(os.path.normpath(path))

    def auto(self) -> None:
        self.dialog.engine.redetect(self.action.id)
        self.edit.clear()
        self._update_placeholder()
        self.validate()

    def validate(self) -> bool:
        text = self.edit.text().strip()
        if not text:
            detected = self.dialog.engine.detected_path(self.action.id)
            if detected:
                self._set("info", f"Будет использован найденный путь: {detected}")
            else:
                self._set("bad", "Программа не найдена автоматически — укажите путь вручную")
            return True
        if not os.path.isfile(text):
            self._set("bad", "✖ Файл не существует")
            return False
        if not text.lower().endswith(".exe"):
            self._set("bad", "✖ Нужен исполняемый файл .exe")
            return False
        if Path(text).name.lower() != self.action.exe_name:
            self._set("info", f"✔ Файл найден (ожидался {self.action.exe_name}, статус будет проверяться по имени выбранного файла)")
        else:
            self._set("ok", "✔ Файл найден")
        return True

    def _set(self, kind: str, text: str) -> None:
        self.state.setObjectName(kind)
        self.state.setText(text)
        self.state.style().unpolish(self.state)
        self.state.style().polish(self.state)


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, engine: Engine, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.engine = engine
        self.setWindowTitle("Настройки — ProSetup Launcher")
        self.setMinimumWidth(680)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        # --- пути
        paths_title = QLabel("ПУТИ К ПРОГРАММАМ")
        paths_title.setObjectName("sectionTitle")
        root.addWidget(paths_title)
        hint = QLabel("Оставьте поле пустым — путь будет определён автоматически "
                      "(реестр только читается, ничего не изменяется).")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        paths_panel = QFrame()
        paths_panel.setObjectName("panel")
        grid = QGridLayout(paths_panel)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(1, 1)
        self.rows = [PathRow(self, grid, i, a) for i, a in enumerate(x for x in ACTIONS if x.kind == "exe")]
        root.addWidget(paths_panel)

        # --- поведение
        behaviour_title = QLabel("ПОВЕДЕНИЕ")
        behaviour_title.setObjectName("sectionTitle")
        root.addWidget(behaviour_title)
        panel = QFrame()
        panel.setObjectName("panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(10)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Пауза между действиями сетапа:"))
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.0, 10.0)
        self.delay.setSingleStep(0.5)
        self.delay.setDecimals(1)
        self.delay.setSuffix(" с")
        self.delay.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.delay.setMinimumWidth(80)
        self.delay.setToolTip("От 0 до 10 секунд; колесо мыши или стрелки клавиатуры меняют значение")
        self.delay.setValue(float(settings["launch_delay"]))
        delay_row.addWidget(self.delay)
        delay_row.addStretch(1)
        box.addLayout(delay_row)

        self.close_to_tray = QCheckBox("Кнопка закрытия окна сворачивает приложение в трей")
        self.close_to_tray.setChecked(settings["close_to_tray"])
        self.notifications = QCheckBox("Показывать уведомление об успешном запуске каждого действия")
        self.notifications.setChecked(settings["notifications"])
        self.minimize_after = QCheckBox("Сворачивать в трей после «ЗАПУСТИТЬ МОЙ СЕТАП», если всё прошло без ошибок")
        self.minimize_after.setChecked(settings["minimize_after_launch"])
        for cb in (self.close_to_tray, self.notifications, self.minimize_after):
            cb.setCursor(Qt.PointingHandCursor)
            box.addWidget(cb)
        root.addWidget(panel)

        # --- кнопки
        bottom = QHBoxLayout()
        open_dir = QPushButton("Папка настроек и журнала")
        open_dir.setObjectName("secondary")
        open_dir.setCursor(Qt.PointingHandCursor)
        open_dir.clicked.connect(self._open_data_dir)
        bottom.addWidget(open_dir)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        bottom.addWidget(buttons)
        root.addLayout(bottom)

    def _open_data_dir(self) -> None:
        try:
            winapi.shell_open(str(app_data_dir()))
        except winapi.ShellLaunchError as exc:
            QMessageBox.warning(self, "Не удалось открыть папку", str(exc))

    def accept(self) -> None:
        bad = [row.action.title for row in self.rows if not row.validate()]
        if bad:
            QMessageBox.warning(
                self, "Проверьте пути",
                "Указанный файл не найден или не является .exe:\n• " + "\n• ".join(bad)
                + "\n\nИсправьте путь или очистите поле для автоопределения.",
            )
            return
        for row in self.rows:
            self.settings.set_path(row.action.id, row.edit.text().strip())
        self.settings["launch_delay"] = float(self.delay.value())
        self.settings["close_to_tray"] = self.close_to_tray.isChecked()
        self.settings["notifications"] = self.notifications.isChecked()
        self.settings["minimize_after_launch"] = self.minimize_after.isChecked()
        if not self.settings.save():
            QMessageBox.warning(self, "Ошибка сохранения",
                                f"Не удалось записать файл настроек:\n{self.settings.path}")
        super().accept()
