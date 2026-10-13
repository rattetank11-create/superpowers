"""Тонкая обёртка над WinAPI через ctypes (стандартная библиотека Python).

Только чтение состояния системы и открытие программ — никаких изменений
реестра, DPI, чувствительности мыши или параметров безопасности.
На не-Windows системах функции деградируют до безопасных заглушек,
чтобы интерфейс можно было запускать и отлаживать где угодно.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

log = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"


class ShellLaunchError(Exception):
    """Понятное пользователю описание ошибки запуска."""


if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32")

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL

    SEE_MASK_NOASYNC = 0x00000100
    SEE_MASK_FLAG_NO_UI = 0x00000400
    SW_SHOWNORMAL = 1
    SW_RESTORE = 9

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long

    _SHELL_ERRORS = {
        2: "файл не найден",
        3: "путь не найден",
        5: "доступ запрещён",
        8: "недостаточно памяти",
        32: "файл занят другим процессом",
        193: "файл не является приложением Windows",
        740: "требуются права администратора",
        1155: "нет программы для открытия этого типа файлов",
        1223: "запуск отменён пользователем (окно UAC)",
    }


# ---------------------------------------------------------------------------
# Процессы
# ---------------------------------------------------------------------------
def list_processes() -> dict[int, str]:
    """PID -> имя exe (в нижнем регистре) для всех процессов системы."""
    if not IS_WINDOWS:
        return {}
    try:
        return _toolhelp_processes()
    except OSError as exc:
        log.warning("Toolhelp32 недоступен (%s), используется tasklist", exc)
        return _tasklist_processes()


def _toolhelp_processes() -> dict[int, str]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot in (None, 0, INVALID_HANDLE_VALUE):
        raise ctypes.WinError(ctypes.get_last_error())
    result: dict[int, str] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            result[int(entry.th32ProcessID)] = entry.szExeFile.lower()
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return result


def _tasklist_processes() -> dict[int, str]:
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        log.error("tasklist не сработал: %s", exc)
        return {}
    result: dict[int, str] = {}
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[1].isdigit():
            result[int(parts[1])] = parts[0].lower()
    return result


# ---------------------------------------------------------------------------
# Окна
# ---------------------------------------------------------------------------
def find_dialogs(pids: set[int], title_keywords: tuple[str, ...]) -> list[int]:
    """Видимые диалоги (#32770) указанных процессов, заголовок которых содержит ключевое слово."""
    if not IS_WINDOWS or not pids:
        return []
    found: list[int] = []
    cls_buf = ctypes.create_unicode_buffer(64)
    title_buf = ctypes.create_unicode_buffer(256)

    @WNDENUMPROC
    def _callback(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value not in pids:
                return True
            user32.GetClassNameW(hwnd, cls_buf, 64)
            if cls_buf.value != "#32770":
                return True
            user32.GetWindowTextW(hwnd, title_buf, 256)
            title = title_buf.value.lower()
            if any(k in title for k in title_keywords):
                found.append(hwnd)
        except Exception:  # колбэк WinAPI не должен бросать исключения
            log.exception("Ошибка при переборе окон")
        return True

    user32.EnumWindows(_callback, 0)
    return found


def bring_to_front(hwnd: int) -> None:
    if not IS_WINDOWS or not hwnd:
        return
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------
def shell_open(target: str, params: str | None = None, cwd: str | None = None,
               quiet: bool = True) -> None:
    """Открыть программу, файл или URL так же, как это делает Проводник/Win+R.

    quiet=True запрещает Windows показывать собственные модальные окна ошибок
    (иначе поток запуска ждал бы, пока их закроют) — ошибку показываем сами.
    quiet=False используется для уже проверенных .exe: так запрос UAC для
    программ с правами администратора (FACEIT Anti-Cheat) гарантированно появится.
    """
    if not IS_WINDOWS:
        _dev_open(target, params, cwd)
        return
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOASYNC | (SEE_MASK_FLAG_NO_UI if quiet else 0)
    info.hwnd = None
    info.lpVerb = "open"
    info.lpFile = target
    info.lpParameters = params
    info.lpDirectory = cwd
    info.nShow = SW_SHOWNORMAL
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        code = ctypes.get_last_error()
        reason = _SHELL_ERRORS.get(code) or ctypes.FormatError(code).strip() or f"код {code}"
        raise ShellLaunchError(reason)


def _dev_open(target: str, params: str | None, cwd: str | None) -> None:
    """Не-Windows: только для отладки интерфейса."""
    if target.startswith(("http://", "https://")):
        import webbrowser
        if not webbrowser.open(target):
            raise ShellLaunchError("не удалось открыть браузер")
        return
    if not os.path.exists(target):
        raise ShellLaunchError("файл не найден")
    try:
        subprocess.Popen([target] + ([params] if params else []), cwd=cwd)
    except OSError as exc:
        raise ShellLaunchError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Прочее
# ---------------------------------------------------------------------------
def co_initialize() -> bool:
    """ShellExecuteEx рекомендует инициализированный COM в вызывающем потоке.

    Возвращает True, если потом нужно вызвать co_uninitialize().
    """
    if not IS_WINDOWS:
        return False
    hr = ole32.CoInitializeEx(None, 0x2 | 0x4)  # APARTMENTTHREADED | DISABLE_OLE1DDE
    return hr >= 0  # S_OK или S_FALSE


def co_uninitialize() -> None:
    if IS_WINDOWS:
        ole32.CoUninitialize()


def set_app_user_model_id(app_id: str) -> None:
    """Своя иконка и группировка на панели задач (не системная настройка)."""
    if not IS_WINDOWS:
        return
    try:
        shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id))
    except (AttributeError, OSError):
        pass


def enable_dark_title_bar(hwnd: int) -> None:
    """Тёмный заголовок окна только для нашего окна (Windows 10 1809+ / 11)."""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        value = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (новые / старые сборки)
            if dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), attr, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                break
    except (AttributeError, OSError):
        pass
