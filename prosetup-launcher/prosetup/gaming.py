"""My Gaming Setup: целевые настройки мыши/клавиатуры и их честные статусы.

Logitech G HUB не предоставляет сторонним программам интерфейса для
изменения или чтения DPI, частоты опроса и Rapid Trigger. Поэтому лаунчер:
  * ничего не меняет в устройствах сам и не делает вид, что поменял;
  * определяет подключённые устройства через Windows (только чтение);
  * показывает точные шаги в G HUB;
  * ставит «Применено» / «Не поддерживается» только по отметке пользователя,
    привязанной к конкретному устройству (VID:PID).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .config import Settings
from .devices import VENDOR_SOFTWARE, Device

LOGITECH = "046D"

TARGET_DPI = 800
TARGET_POLLING_HZ = 2000
TARGET_RT_MM = 0.4
RT_KEYS = ("W", "A", "S", "D")

APPLIED = "applied"
UNSUPPORTED = "unsupported"

LIMITATION_TEXT = (
    "Logitech G HUB не даёт сторонним программам изменять или читать DPI, частоту опроса "
    "и Rapid Trigger. Поэтому ProSetup Launcher не меняет эти настройки сам и не может "
    "их проверить: он находит ваши устройства, открывает G HUB и показывает точные шаги. "
    "Статус «Применено» появляется только после вашей проверки в G HUB."
)


@dataclass(frozen=True)
class SettingDef:
    id: str
    device_kind: str      # "mouse" | "keyboard"
    title: str
    target: str
    support_hint: str     # как проверить поддержку в G HUB
    steps: tuple[str, ...]


SETTINGS: tuple[SettingDef, ...] = (
    SettingDef(
        id="mouse_dpi",
        device_kind="mouse",
        title="DPI — один уровень",
        target=f"{TARGET_DPI} DPI, остальные уровни удалены",
        support_hint="Если G HUB не даёт удалить лишние уровни, оставьте 800 DPI уровнем по умолчанию.",
        steps=(
            "Откройте G HUB и нажмите на свою мышь.",
            "Перейдите в раздел «Чувствительность (DPI)».",
            "Удалите все уровни DPI, кроме одного (выберите уровень и удалите его).",
            f"Установите оставшийся уровень на {TARGET_DPI} DPI и сделайте его уровнем по умолчанию.",
            "Если у мыши есть «Встроенная память», сохраните профиль в неё: "
            "настройки останутся в мыши на любом ПК (удобно в компьютерном клубе).",
        ),
    ),
    SettingDef(
        id="mouse_polling",
        device_kind="mouse",
        title="Частота опроса",
        target=f"{TARGET_POLLING_HZ} Hz",
        support_hint=f"Мышь поддерживает {TARGET_POLLING_HZ} Hz, только если это значение есть в списке "
                     "частот опроса в G HUB. Если его нет — отметьте «Не поддерживается».",
        steps=(
            "В G HUB на странице мыши найдите «Частота опроса» (Report rate) — обычно в разделе "
            "чувствительности или настроек производительности.",
            f"Проверьте, есть ли в списке {TARGET_POLLING_HZ}. Нет — значит, мышь или приёмник "
            "не поддерживают эту частоту: ничего не меняйте.",
            f"Если есть — выберите {TARGET_POLLING_HZ} Hz.",
        ),
    ),
    SettingDef(
        id="kb_rapid_trigger",
        device_kind="keyboard",
        title="Rapid Trigger W A S D",
        target=f"{TARGET_RT_MM:.1f} мм".replace(".", ",") + " для клавиш " + ", ".join(RT_KEYS),
        support_hint="Rapid Trigger есть только у клавиатур с магнитными (аналоговыми) переключателями. "
                     "Если на странице клавиатуры в G HUB нет настроек Rapid Trigger — модель его "
                     "не поддерживает: отметьте «Не поддерживается».",
        steps=(
            "Откройте G HUB и нажмите на клавиатуру.",
            "Найдите раздел Rapid Trigger (у клавиатур Logitech с магнитными переключателями — "
            "в настройках срабатывания клавиш).",
            "Выберите клавиши " + ", ".join(RT_KEYS) + " (настройка отдельных клавиш).",
            f"Включите Rapid Trigger и задайте чувствительность "
            f"{TARGET_RT_MM:.1f} мм".replace(".", ",") + ".",
        ),
    ),
)
SETTINGS_BY_ID = {s.id: s for s in SETTINGS}


@dataclass
class RowStatus:
    state: str      # для StatusBadge: running / starting / notfound / idle
    text: str
    detail: str
    device: Device | None


def candidates(devices: list[Device], kind: str) -> list[Device]:
    """Устройства Logitech нужного типа. Приёмники — в конце (модель за ними неизвестна)."""
    flag = "is_mouse" if kind == "mouse" else "is_keyboard"
    found = [d for d in devices if d.vid == LOGITECH and getattr(d, flag)]
    return sorted(found, key=lambda d: d.is_receiver)


def other_rt_vendors(devices: list[Device]) -> list[tuple[Device, str, str]]:
    """Клавиатуры других производителей с официальным ПО для Rapid Trigger."""
    result = []
    for d in devices:
        if d.vid in VENDOR_SOFTWARE and d.is_keyboard:
            name, url = VENDOR_SOFTWARE[d.vid]
            result.append((d, name, url))
    return result


def row_status(setting: SettingDef, devices: list[Device], settings: Settings,
               ghub_found: bool) -> RowStatus:
    found = candidates(devices, setting.device_kind)
    noun = "мышь" if setting.device_kind == "mouse" else "клавиатура"
    if not found:
        return RowStatus("notfound", "Нет устройства",
                         f"Подключённая {noun} Logitech не обнаружена.", None)
    record = settings["gaming"].get(setting.id)
    keys = {d.key for d in found}
    if record and record.get("device") in keys:
        device = next(d for d in found if d.key == record["device"])
        when = time.strftime("%d.%m %H:%M", time.localtime(record.get("at", 0)))
        if record.get("state") == APPLIED:
            return RowStatus("running", "Применено", f"Вы подтвердили {when} для {device.display_name}", device)
        return RowStatus("idle", "Не поддерживается",
                         f"Вы отметили {when}: {device.display_name} не поддерживает эту настройку", device)
    device = found[0]
    if not ghub_found:
        return RowStatus("notfound", "G HUB не найден",
                         "Установите Logitech G HUB или укажите путь к lghub.exe на карточке G HUB.", device)
    detail = "Лаунчер не может применить эту настройку сам — выполните шаги и отметьте результат."
    if device.is_receiver:
        detail = (f"Найден только приёмник Logitech: подключена ли через него {noun}, Windows не сообщает. "
                  "Проверьте в G HUB. " + detail)
    return RowStatus("starting", "Настройте в G HUB", detail, device)


def mark(settings: Settings, setting_id: str, state: str | None, device: Device | None) -> None:
    if state is None or device is None:
        settings["gaming"].pop(setting_id, None)
    else:
        settings["gaming"][setting_id] = {"state": state, "device": device.key, "at": time.time()}
    settings.save()
