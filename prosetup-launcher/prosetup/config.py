"""Хранение пользовательских настроек в JSON-файле (%APPDATA%\\ProSetupLauncher)."""

from __future__ import annotations

import copy
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import APP_ID

log = logging.getLogger(__name__)

ACTION_IDS = ("steam", "mouse", "faceit_ac", "faceit_web", "ghub")
PATH_ACTION_IDS = ("steam", "faceit_ac", "ghub")

DEFAULTS: dict[str, Any] = {
    "enabled": {aid: True for aid in ACTION_IDS},
    "paths": {aid: "" for aid in PATH_ACTION_IDS},
    "browser": "chrome",          # "chrome" или "default" (браузер по умолчанию)
    "launch_delay": 1.5,          # пауза между действиями сетапа, секунды
    "close_to_tray": True,        # крестик окна сворачивает в трей
    "notifications": True,        # уведомления об успешном запуске
    "minimize_after_launch": False,
    "tray_hint_shown": False,
    "window_geometry": "",
}


_data_dir: Path | None = None


def _portable_dir() -> Path | None:
    """Собранный EXE хранит настройки рядом с собой (папка ProSetupLauncher-data).

    Так настройки переживают очистку профиля в компьютерном клубе и ездят
    вместе с EXE на флешке. Если папка недоступна для записи — используется %APPDATA%.
    """
    if not getattr(sys, "frozen", False):
        return None
    path = Path(sys.executable).resolve().parent / f"{APP_ID}-data"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return path
    except OSError:
        return None


def app_data_dir() -> Path:
    global _data_dir
    if _data_dir is None:
        path = _portable_dir()
        if path is None:
            base = os.environ.get("APPDATA") or str(Path.home() / ".config")
            path = Path(base) / APP_ID
            path.mkdir(parents=True, exist_ok=True)
        _data_dir = path
    return _data_dir


class Settings:
    """Настройки с безопасной загрузкой: битый или чужой файл не роняет приложение."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (app_data_dir() / "settings.json")
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    # ---------- загрузка / сохранение ----------
    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Не удалось прочитать настройки (%s), используются значения по умолчанию", exc)
            return
        if not isinstance(raw, dict):
            return
        self.data = self._merge(raw)

    @staticmethod
    def _merge(raw: dict[str, Any]) -> dict[str, Any]:
        data = copy.deepcopy(DEFAULTS)
        enabled = raw.get("enabled")
        if isinstance(enabled, dict):
            for aid in ACTION_IDS:
                if isinstance(enabled.get(aid), bool):
                    data["enabled"][aid] = enabled[aid]
        paths = raw.get("paths")
        if isinstance(paths, dict):
            for aid in PATH_ACTION_IDS:
                if isinstance(paths.get(aid), str):
                    data["paths"][aid] = paths[aid].strip()
        if raw.get("browser") in ("chrome", "default"):
            data["browser"] = raw["browser"]
        delay = raw.get("launch_delay")
        if isinstance(delay, (int, float)) and not isinstance(delay, bool):
            data["launch_delay"] = float(min(max(delay, 0.0), 10.0))
        for key in ("close_to_tray", "notifications", "minimize_after_launch", "tray_hint_shown"):
            if isinstance(raw.get(key), bool):
                data[key] = raw[key]
        if isinstance(raw.get("window_geometry"), str):
            data["window_geometry"] = raw["window_geometry"]
        return data

    def save(self) -> bool:
        """Атомарная запись: сначала во временный файл, затем замена."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=self.path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            return True
        except OSError as exc:
            log.error("Не удалось сохранить настройки: %s", exc)
            return False

    # ---------- удобный доступ ----------
    def is_enabled(self, action_id: str) -> bool:
        return bool(self.data["enabled"].get(action_id, True))

    def set_enabled(self, action_id: str, value: bool) -> None:
        self.data["enabled"][action_id] = bool(value)

    def get_path(self, action_id: str) -> str:
        return self.data["paths"].get(action_id, "")

    def set_path(self, action_id: str, value: str) -> None:
        self.data["paths"][action_id] = (value or "").strip()

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
