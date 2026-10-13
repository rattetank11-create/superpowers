"""Самопроверка собранного EXE: ProSetupLauncher.exe --selftest <файл-отчёта>.

Проверяет на настоящей Windows то, что нельзя проверить на другой ОС:
список процессов (WinAPI), чтение реестра, поиск окон, ShellExecuteEx,
создание главного окна и настроек. Ничего из сетапа не запускает.
Код выхода 0 — всё в порядке.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback
from pathlib import Path


def run_selftest(report_path: str) -> int:
    """Никогда не бросает исключений: в собранном EXE без консоли это показало бы
    модальное окно PyInstaller, и автоматическая проверка зависла бы."""
    try:
        return _run(report_path)
    except BaseException:
        try:
            Path(report_path).write_text("FAIL  selftest crashed:\n" + traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        return 2


def _run(report_path: str) -> int:
    lines: list[str] = []
    failures = 0

    def flush() -> None:
        Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def check(name: str, func) -> None:
        nonlocal failures
        lines.append(f"...   {name}")
        flush()  # если шаг зависнет, в отчёте будет видно, на каком
        try:
            detail = func()
            lines[-1] = f"PASS  {name}: {detail}"
        except Exception:
            failures += 1
            lines[-1] = f"FAIL  {name}:\n{traceback.format_exc()}"
        flush()

    lines.append("START")
    flush()
    from PySide6.QtWidgets import QApplication

    from . import detect, winapi
    from .actions import ACTIONS
    from .config import Settings
    from .engine import Engine
    from .ui.main_window import MainWindow
    from .ui.theme import STYLESHEET

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyleSheet(STYLESHEET)

    def processes():
        procs = winapi.list_processes()
        own = Path(sys.executable).name.lower()
        assert procs, "список процессов пуст"
        assert own in procs.values(), f"собственный процесс {own} не найден"
        return f"{len(procs)} процессов, свой процесс найден"

    def tasklist_fallback():
        procs = winapi._tasklist_processes()
        assert procs, "tasklist ничего не вернул"
        return f"{len(procs)} процессов"

    def detection():
        found = {aid: detect.detect(aid) for aid in detect.DETECTORS}
        assert detect.detect_mouse_cpl(), "main.cpl не найден"
        return ", ".join(f"{k}={v or 'нет'}" for k, v in found.items()) + ", main.cpl найден"

    def setupapi():
        from . import devices
        total = devices.count_present_devices()
        assert total > 0, "SetupAPI не вернул ни одного устройства"
        found = devices.list_devices()
        names = ", ".join(f"{d.display_name} ({d.key})" for d in found) or "игровых устройств нет"
        return f"{total} устройств в системе; {names}"

    def windows_enum():
        procs = winapi.list_processes()
        winapi.find_dialogs(set(procs), ("mouse", "мыш"))
        return "EnumWindows работает"

    def shell_execute():
        marker = Path(tempfile.gettempdir()) / f"prosetup-selftest-{os.getpid()}.txt"
        marker.unlink(missing_ok=True)
        comspec = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
        winapi.co_initialize()
        winapi.shell_open(comspec, f'/c echo ok> "{marker}"')
        for _ in range(100):
            if marker.exists():
                marker.unlink(missing_ok=True)
                return "ShellExecuteExW запустил cmd.exe"
            time.sleep(0.1)
        raise AssertionError("cmd.exe не создал файл-маркер")

    def shell_error():
        try:
            winapi.shell_open(r"C:\definitely\missing\app.exe")
        except winapi.ShellLaunchError as exc:
            return f"понятная ошибка: {exc}"
        raise AssertionError("ошибка не была выброшена")

    def ui_and_engine():
        tmp = Path(tempfile.mkdtemp(prefix="prosetup-selftest-"))
        settings = Settings(tmp / "settings.json")
        engine = Engine(settings)
        window = MainWindow(settings, engine)
        statuses = engine.statuses()
        assert set(statuses) == {a.id for a in ACTIONS}
        settings.set_enabled("ghub", False)
        assert settings.save() and Settings(tmp / "settings.json").is_enabled("ghub") is False
        window._really_quit = True
        window.deleteLater()
        return "; ".join(f"{k}={v.text}" for k, v in statuses.items())

    for name, func in (
        ("Список процессов (Toolhelp32)", processes),
        ("Список процессов (tasklist)", tasklist_fallback),
        ("Автоопределение путей (реестр)", detection),
        ("Перебор окон", windows_enum),
        ("Устройства (SetupAPI)", setupapi),
        ("ShellExecuteEx", shell_execute),
        ("Ошибка для несуществующего файла", shell_error),
        ("Главное окно, статусы, настройки", ui_and_engine),
    ):
        check(name, func)

    lines.append(f"RESULT: {'OK' if failures == 0 else f'{failures} FAILED'}")
    flush()
    return 0 if failures == 0 else 1
