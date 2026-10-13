"""Автоматический поиск установленных программ.

Реестр Windows здесь только ЧИТАЕТСЯ (winreg.OpenKey с KEY_READ) —
приложение ничего в нём не создаёт и не изменяет.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterator

from .winapi import IS_WINDOWS

log = logging.getLogger(__name__)

if IS_WINDOWS:
    import winreg

_UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
def _views() -> tuple[int, ...]:
    return (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)


def _reg_value(root, subkey: str, name: str) -> str | None:
    if not IS_WINDOWS:
        return None
    for view in _views():
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except OSError:
            continue
    return None


def _uninstall_entries() -> Iterator[dict[str, str]]:
    """Записи «Программы и компоненты» (HKLM и HKCU, 64- и 32-битные ветки)."""
    if not IS_WINDOWS:
        return
    seen: set[str] = set()
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in _views():
            try:
                parent = winreg.OpenKey(root, _UNINSTALL_KEY, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            with parent:
                index = 0
                while True:
                    try:
                        sub = winreg.EnumKey(parent, index)
                    except OSError:
                        break
                    index += 1
                    try:
                        with winreg.OpenKey(parent, sub, 0, winreg.KEY_READ | view) as key:
                            entry = {}
                            for field in ("DisplayName", "InstallLocation", "DisplayIcon"):
                                try:
                                    value, _ = winreg.QueryValueEx(key, field)
                                    if isinstance(value, str):
                                        entry[field] = value
                                except OSError:
                                    pass
                    except OSError:
                        continue
                    ident = entry.get("DisplayName", "") + "|" + entry.get("InstallLocation", "")
                    if entry.get("DisplayName") and ident not in seen:
                        seen.add(ident)
                        yield entry


def _program_files() -> list[Path]:
    dirs: list[Path] = []
    for var, fallback in (
        ("ProgramW6432", r"C:\Program Files"),
        ("ProgramFiles", r"C:\Program Files"),
        ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ):
        value = os.environ.get(var) or fallback
        path = Path(value)
        if path not in dirs:
            dirs.append(path)
    return dirs


def _clean_icon_path(value: str) -> str:
    """DisplayIcon бывает вида '"C:\\x\\app.exe",0' — оставляем только путь."""
    value = value.strip().strip('"')
    if "," in value and not value.lower().endswith(".exe"):
        value = value.rsplit(",", 1)[0].strip().strip('"')
    return value


def _first_file(candidates) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(os.path.expandvars(str(candidate)))
        try:
            if path.is_file():
                return str(path)
        except OSError:
            continue
    return None


def _from_uninstall(name_keywords: tuple[str, ...], exe_names: tuple[str, ...],
                    exclude: tuple[str, ...] = ()) -> list[str]:
    result: list[str] = []
    for entry in _uninstall_entries():
        name = entry.get("DisplayName", "").lower()
        if not any(k in name for k in name_keywords) or any(x in name for x in exclude):
            continue
        location = entry.get("InstallLocation", "").strip().strip('"')
        if location:
            result.extend(str(Path(location) / exe) for exe in exe_names)
        icon = _clean_icon_path(entry.get("DisplayIcon", ""))
        if icon and Path(icon).name.lower() in exe_names:
            result.append(icon)
    return result


# ---------------------------------------------------------------------------
# Детекторы
# ---------------------------------------------------------------------------
def detect_steam() -> str | None:
    candidates: list[str] = []
    if IS_WINDOWS:
        steam_exe = _reg_value(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamExe")
        if steam_exe:
            candidates.append(steam_exe.replace("/", "\\"))
        steam_path = _reg_value(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath")
        if steam_path:
            candidates.append(str(Path(steam_path.replace("/", "\\")) / "steam.exe"))
        install = _reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")
        if install:
            candidates.append(str(Path(install) / "steam.exe"))
    candidates += [str(pf / "Steam" / "steam.exe") for pf in reversed(_program_files())]
    candidates += _from_uninstall(("steam",), ("steam.exe",), exclude=("steamvr",))
    return _first_file(candidates)


def detect_faceit_ac() -> str | None:
    exe_names = ("faceitclient.exe",)
    candidates = [str(pf / "FACEIT AC" / exe) for pf in _program_files() for exe in exe_names]
    candidates += _from_uninstall(("faceit ac", "faceit anti-cheat", "faceit anticheat"), exe_names)
    return _first_file(candidates)


def detect_ghub() -> str | None:
    exe_names = ("lghub.exe",)
    candidates = [str(pf / "LGHUB" / exe) for pf in _program_files() for exe in exe_names]
    candidates += _from_uninstall(("g hub", "ghub"), exe_names)
    return _first_file(candidates)


def detect_mouse_cpl() -> str | None:
    system_root = os.environ.get("SystemRoot") or r"C:\Windows"
    return _first_file([str(Path(system_root) / "System32" / "main.cpl")])


def control_exe() -> str:
    system_root = os.environ.get("SystemRoot") or r"C:\Windows"
    path = Path(system_root) / "System32" / "control.exe"
    return str(path) if path.is_file() else "control.exe"


DETECTORS = {
    "steam": detect_steam,
    "faceit_ac": detect_faceit_ac,
    "ghub": detect_ghub,
}


def detect(action_id: str) -> str | None:
    detector = DETECTORS.get(action_id)
    if detector is None:
        return None
    try:
        return detector()
    except Exception:  # детектор не должен ронять приложение
        log.exception("Ошибка автоопределения пути для %s", action_id)
        return None
