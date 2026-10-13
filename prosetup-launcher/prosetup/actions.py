"""Описание действий сетапа (порядок списка = порядок запуска)."""

from __future__ import annotations

from dataclasses import dataclass

FACEIT_URL = "https://www.faceit.com/"

# Заголовок окна «Свойства: Мышь» на разных языках Windows
MOUSE_TITLE_KEYWORDS = (
    "мыш", "mouse", "maus", "souris", "ratón", "raton", "mysz", "myš", "miš", "egér", "fare",
)


@dataclass(frozen=True)
class ActionDef:
    id: str
    title: str
    subtitle: str
    monogram: str
    color: str          # цвет плашки-иконки
    kind: str           # "exe" | "cpl" | "url"
    exe_name: str = ""  # ожидаемое имя исполняемого файла
    process_names: tuple[str, ...] = ()
    success_text: str = ""
    skipped_text: str = ""


ACTIONS: tuple[ActionDef, ...] = (
    ActionDef(
        id="steam",
        title="Steam",
        subtitle="Клиент Steam для CS2",
        monogram="ST",
        color="#1b6fa8",
        kind="exe",
        exe_name="steam.exe",
        process_names=("steam.exe",),
        success_text="Steam запущен",
        skipped_text="Steam уже запущен — второй экземпляр не нужен",
    ),
    ActionDef(
        id="mouse",
        title="Настройки мыши",
        subtitle="Панель Windows · main.cpl",
        monogram="M",
        color="#3a3f4b",
        kind="cpl",
        success_text="Открыта панель настроек мыши",
        skipped_text="Окно настроек мыши уже открыто — переключаюсь на него",
    ),
    ActionDef(
        id="faceit_ac",
        title="FACEIT Anti-Cheat",
        subtitle="Клиент античита FACEIT AC",
        monogram="AC",
        color="#ff5500",
        kind="exe",
        exe_name="faceitclient.exe",
        process_names=("faceitclient.exe",),
        success_text="FACEIT Anti-Cheat запущен",
        skipped_text="FACEIT Anti-Cheat уже запущен",
    ),
    ActionDef(
        id="faceit_web",
        title="FACEIT в браузере",
        subtitle="faceit.com в Chrome или браузере по умолчанию",
        monogram="FC",
        color="#c84300",
        kind="url",
        success_text="Сайт FACEIT открыт в браузере",
    ),
    ActionDef(
        id="ghub",
        title="Logitech G HUB",
        subtitle="DPI, кнопки и профили мыши",
        monogram="G",
        color="#00a2d8",
        kind="exe",
        exe_name="lghub.exe",
        process_names=("lghub.exe",),
        success_text="Logitech G HUB запущен",
        skipped_text="Logitech G HUB уже запущен",
    ),
)

ACTIONS_BY_ID = {a.id: a for a in ACTIONS}
