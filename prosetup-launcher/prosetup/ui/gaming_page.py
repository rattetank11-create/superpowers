"""Страница My Gaming Setup."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .. import gaming, winapi
from ..devices import Device, list_devices
from ..engine import Engine
from .widgets import StatusBadge

log = logging.getLogger(__name__)


def _button(text: str, name: str = "cardTool", tip: str = "") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(name)
    btn.setCursor(Qt.PointingHandCursor)
    if tip:
        btn.setToolTip(tip)
    return btn


def _label(text: str, name: str = "", wrap: bool = True) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


class SettingRow(QFrame):
    marked = Signal(str, object)   # id настройки, состояние (applied / unsupported / None)

    def __init__(self, setting: gaming.SettingDef) -> None:
        super().__init__()
        self.setting = setting
        self.setObjectName("settingRow")
        self.device: Device | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(_label(setting.title, "rowTitle", wrap=False))
        names.addWidget(_label("Цель: " + setting.target, "cardSubtitle"))
        top.addLayout(names, 1)
        self.badge = StatusBadge()
        top.addWidget(self.badge, 0, Qt.AlignTop)
        layout.addLayout(top)

        self.detail = _label("", "hint")
        layout.addWidget(self.detail)

        self.steps = _label(
            "<ol style='margin-left:-20px'>" + "".join(f"<li>{s}</li>" for s in setting.steps) + "</ol>"
            f"<p><b>Поддержка:</b> {setting.support_hint}</p>",
            "steps",
        )
        self.steps.setTextFormat(Qt.RichText)
        self.steps.setVisible(False)
        layout.addWidget(self.steps)

        buttons = QHBoxLayout()
        self.toggle_steps = _button("Как настроить ▾")
        self.toggle_steps.clicked.connect(self._toggle_steps)
        buttons.addWidget(self.toggle_steps)
        buttons.addStretch(1)
        self.applied_btn = _button("✔ Применено", "cardLaunch", "Я выполнил шаги и проверил в G HUB")
        self.unsupported_btn = _button("Не поддерживается", tip="В G HUB этой настройки для устройства нет")
        self.reset_btn = _button("↺", tip="Сбросить отметку")
        self.applied_btn.clicked.connect(lambda: self._confirm(gaming.APPLIED))
        self.unsupported_btn.clicked.connect(lambda: self._confirm(gaming.UNSUPPORTED))
        self.reset_btn.clicked.connect(lambda: self.marked.emit(self.setting.id, None))
        for b in (self.unsupported_btn, self.applied_btn, self.reset_btn):
            buttons.addWidget(b)
        layout.addLayout(buttons)

    def _toggle_steps(self) -> None:
        visible = not self.steps.isVisible()
        self.steps.setVisible(visible)
        self.toggle_steps.setText("Скрыть шаги ▴" if visible else "Как настроить ▾")

    def _confirm(self, state: str) -> None:
        if not self.device:
            return
        question = (
            f"Подтвердите, что в G HUB для «{self.device.display_name}» установлено:\n\n"
            f"{self.setting.title}: {self.setting.target}\n\nЛаунчер не может проверить это сам."
            if state == gaming.APPLIED else
            f"Подтвердите, что в G HUB для «{self.device.display_name}» нет настройки:\n\n"
            f"{self.setting.title}: {self.setting.target}"
        )
        if QMessageBox.question(self, "Подтверждение", question) == QMessageBox.Yes:
            self.marked.emit(self.setting.id, state)

    def set_status(self, status: gaming.RowStatus) -> None:
        self.device = status.device
        self.badge.set_state(status.state, status.text)
        self.detail.setText(status.detail)
        has_device = status.device is not None
        self.applied_btn.setEnabled(has_device)
        self.unsupported_btn.setEnabled(has_device)
        self.reset_btn.setVisible(status.text in ("Применено", "Не поддерживается"))


class DeviceCard(QFrame):
    def __init__(self, title: str, subtitle: str) -> None:
        super().__init__()
        self.setObjectName("card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(16, 14, 16, 14)
        self.layout_.setSpacing(10)
        head = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(_label(title, "cardTitle", wrap=False))
        self.subtitle = _label(subtitle, "cardSubtitle")
        names.addWidget(self.subtitle)
        head.addLayout(names, 1)
        self.head_buttons = QHBoxLayout()
        head.addLayout(self.head_buttons)
        self.layout_.addLayout(head)


class GamingPage(QWidget):
    notify = Signal(str, str, str)
    launch_requested = Signal(str)

    def __init__(self, engine: Engine) -> None:
        super().__init__()
        self.engine = engine
        self.settings = engine.settings
        self.devices: list[Device] = []
        self.rows: dict[str, SettingRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("cardsHost")
        layout = QVBoxLayout(host)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)
        scroll.setWidget(host)
        outer.addWidget(scroll)

        notice = QFrame()
        notice.setObjectName("notice")
        nl = QVBoxLayout(notice)
        nl.setContentsMargins(14, 10, 14, 10)
        nl.addWidget(_label("⚠  " + gaming.LIMITATION_TEXT, "noticeText"))
        layout.addWidget(notice)

        # --- устройства
        dev_card = DeviceCard("Подключённые устройства", "Определяются через Windows — по данным самих устройств")
        refresh = _button("⟳ Обновить", "secondary")
        refresh.clicked.connect(lambda: self.refresh(announce=True))
        dev_card.head_buttons.addWidget(refresh)
        self.devices_label = _label("", "devices")
        self.devices_label.setTextFormat(Qt.RichText)
        dev_card.layout_.addWidget(self.devices_label)
        layout.addWidget(dev_card)

        # --- мышь
        self.mouse_card = DeviceCard("Мышь — Logitech G HUB", "")
        btn = _button("Открыть G HUB", "accentOutline")
        btn.clicked.connect(lambda: self.launch_requested.emit("ghub"))
        self.mouse_card.head_buttons.addWidget(btn)
        layout.addWidget(self.mouse_card)

        # --- клавиатура
        self.kb_card = DeviceCard("Клавиатура — Logitech G HUB", "")
        btn = _button("Открыть G HUB", "accentOutline",
                      "G HUB не поддерживает открытие конкретного раздела извне — выберите клавиатуру в окне G HUB")
        btn.clicked.connect(lambda: self.launch_requested.emit("ghub"))
        self.kb_card.head_buttons.addWidget(btn)
        self.other_vendors = QVBoxLayout()
        layout.addWidget(self.kb_card)

        for setting in gaming.SETTINGS:
            row = SettingRow(setting)
            row.marked.connect(self._on_marked)
            self.rows[setting.id] = row
            card = self.mouse_card if setting.device_kind == "mouse" else self.kb_card
            card.layout_.addWidget(row)
        self.kb_card.layout_.addLayout(self.other_vendors)

        # --- Steam
        steam = DeviceCard("Steam", "Вход только через официальное окно Steam")
        btn = _button("Запустить Steam", "accentOutline")
        btn.clicked.connect(lambda: self.launch_requested.emit("steam"))
        steam.head_buttons.addWidget(btn)
        steam.layout_.addWidget(_label(
            "ProSetup Launcher не запрашивает, не хранит и не вводит логин и пароль Steam — их нет "
            "ни в коде, ни в настройках, ни в журнале. Войдите в открывшемся окне Steam. Быстрее и "
            "безопаснее всего на чужом ПК — вход по QR-коду через мобильное приложение Steam: "
            "пароль на клавиатуре клуба вводить не придётся.", "hint"))
        layout.addWidget(steam)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    def refresh(self, announce: bool = False) -> None:
        try:
            self.devices = list_devices()
        except Exception:
            log.exception("Ошибка определения устройств")
            self.devices = []
        if self.devices:
            items = "".join(
                f"<li><b>{d.display_name}</b> <span style='color:#8b9099'>· {d.kind_text} · {d.key}</span></li>"
                for d in self.devices)
            self.devices_label.setText(f"<ul style='margin-left:-20px'>{items}</ul>")
        else:
            text = ("Устройства Logitech, Wooting, SteelSeries и Razer не обнаружены."
                    if winapi.IS_WINDOWS else "Определение устройств доступно только в Windows.")
            self.devices_label.setText(f"<span style='color:#8b9099'>{text}</span>")

        mice = gaming.candidates(self.devices, "mouse")
        kbs = gaming.candidates(self.devices, "keyboard")
        self.mouse_card.subtitle.setText(mice[0].display_name if mice else "Мышь Logitech не найдена")
        self.kb_card.subtitle.setText(kbs[0].display_name if kbs else "Клавиатура Logitech не найдена")
        ghub_found = self.engine.resolve_path("ghub").path is not None
        for sid, row in self.rows.items():
            row.set_status(gaming.row_status(gaming.SETTINGS_BY_ID[sid], self.devices, self.settings, ghub_found))
        self._refresh_other_vendors()
        if announce:
            self.notify.emit("Устройства обновлены", f"Найдено: {len(self.devices)}", "info")

    def _refresh_other_vendors(self) -> None:
        while self.other_vendors.count():
            item = self.other_vendors.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for device, software, url in gaming.other_rt_vendors(self.devices):
            box = QFrame()
            box.setObjectName("notice")
            bl = QHBoxLayout(box)
            bl.setContentsMargins(12, 8, 12, 8)
            bl.addWidget(_label(f"Найдена {device.display_name}. Rapid Trigger для неё настраивается "
                                f"не в G HUB, а в официальном ПО {software}.", "noticeText"), 1)
            btn = _button(f"Открыть {software}", "secondary", url)
            btn.clicked.connect(lambda _=False, u=url: self._open_url(u))
            bl.addWidget(btn)
            self.other_vendors.addWidget(box)

    def _open_url(self, url: str) -> None:
        try:
            winapi.shell_open(url)
        except winapi.ShellLaunchError as exc:
            self.notify.emit("Не удалось открыть страницу", str(exc), "error")

    def _on_marked(self, setting_id: str, state) -> None:
        row = self.rows[setting_id]
        gaming.mark(self.settings, setting_id, state, row.device)
        self.refresh()
        if state == gaming.APPLIED:
            self.notify.emit("Отмечено: применено", f"{row.setting.title} — {row.setting.target}", "success")
        elif state == gaming.UNSUPPORTED:
            self.notify.emit("Отмечено: не поддерживается", row.setting.title, "info")
