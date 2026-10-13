"""Логика: определение путей, реальные статусы процессов и запуск действий."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import detect, winapi
from .actions import ACTIONS, ACTIONS_BY_ID, FACEIT_URL, MOUSE_TITLE_KEYWORDS, ActionDef
from .config import Settings

log = logging.getLogger(__name__)

# Сколько ждать появления процесса после запуска, прежде чем предупредить
START_TIMEOUT = 60.0

RUNNING = "running"
STARTING = "starting"
IDLE = "idle"
NOT_FOUND = "notfound"


@dataclass
class ActionStatus:
    state: str
    text: str
    detail: str = ""


@dataclass
class LaunchResult:
    ok: bool
    skipped: bool
    message: str


@dataclass
class ResolvedPath:
    path: str | None
    source: str        # "manual" | "auto" | ""
    problem: str = ""  # пояснение, если путь не найден


class Engine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._detected: dict[str, str | None] = {}
        self._launching: set[str] = set()
        self._pending: dict[str, float] = {}      # id -> monotonic время запуска
        self._timed_out: list[str] = []
        self._opened_at: dict[str, float] = {}    # id -> time.time() (для URL)
        self.redetect()

    # ------------------------------------------------------------------ пути
    def redetect(self, action_id: str | None = None) -> None:
        ids = [action_id] if action_id else list(detect.DETECTORS)
        for aid in ids:
            found = detect.detect(aid)
            log.info("Автоопределение %s: %s", aid, found or "не найдено")
            with self._lock:
                self._detected[aid] = found

    def detected_path(self, action_id: str) -> str | None:
        with self._lock:
            return self._detected.get(action_id)

    def resolve_path(self, action_id: str) -> ResolvedPath:
        action = ACTIONS_BY_ID[action_id]
        manual = self.settings.get_path(action_id)
        manual_problem = ""
        if manual:
            if _is_file(manual):
                return ResolvedPath(manual, "manual")
            manual_problem = f"Указанный вручную файл не существует: {manual}. "
        auto = self.detected_path(action_id)
        if auto and _is_file(auto):
            return ResolvedPath(auto, "auto", manual_problem.strip())
        return ResolvedPath(
            None, "",
            manual_problem + f"{action.title} не найден. Укажите путь к {action.exe_name} "
            "кнопкой «Путь…» на карточке или в настройках.",
        )

    def describe_target(self, action_id: str) -> str:
        action = ACTIONS_BY_ID[action_id]
        if action.kind == "url":
            return FACEIT_URL
        if action.kind == "cpl":
            return "control.exe main.cpl" if detect.detect_mouse_cpl() else "main.cpl не найден в System32"
        resolved = self.resolve_path(action_id)
        if resolved.path:
            suffix = " · вручную" if resolved.source == "manual" else " · найдено автоматически"
            return resolved.path + suffix
        return "Путь не найден — укажите вручную"

    def _process_names(self, action: ActionDef) -> set[str]:
        names = set(action.process_names)
        resolved = self.resolve_path(action.id)
        if resolved.path:
            names.add(Path(resolved.path).name.lower())
        return names

    # --------------------------------------------------------------- статусы
    def statuses(self) -> dict[str, ActionStatus]:
        processes = winapi.list_processes()
        running_names = set(processes.values())
        result: dict[str, ActionStatus] = {}
        for action in ACTIONS:
            try:
                result[action.id] = self._status_for(action, processes, running_names)
            except Exception as exc:  # статус одной карточки не должен ломать остальные
                log.exception("Ошибка вычисления статуса %s", action.id)
                result[action.id] = ActionStatus(IDLE, "Неизвестно", str(exc))
        return result

    def _status_for(self, action: ActionDef, processes: dict[int, str],
                    running_names: set[str]) -> ActionStatus:
        with self._lock:
            launching = action.id in self._launching

        if action.kind == "exe":
            resolved = self.resolve_path(action.id)
            if not resolved.path:
                return ActionStatus(NOT_FOUND, "Не найдена", resolved.problem)
            names = self._process_names(action)
            if names & running_names:
                with self._lock:
                    self._pending.pop(action.id, None)
                return ActionStatus(RUNNING, "Запущена", f"Процесс {', '.join(sorted(names & running_names))} работает")
            if launching:
                return ActionStatus(STARTING, "Запуск", "Выполняется запуск…")
            with self._lock:
                started = self._pending.get(action.id)
                if started is not None and time.monotonic() - started > START_TIMEOUT:
                    self._pending.pop(action.id, None)
                    self._timed_out.append(action.id)
                    started = None
            if started is not None:
                return ActionStatus(STARTING, "Запуск", "Ожидание появления процесса…")
            return ActionStatus(IDLE, "Не запущена", "Программа найдена, но сейчас не работает")

        if action.kind == "cpl":
            if not detect.detect_mouse_cpl():
                return ActionStatus(NOT_FOUND, "Не найдена", "Файл main.cpl отсутствует в System32")
            if launching:
                return ActionStatus(STARTING, "Запуск", "Открытие панели…")
            if self._mouse_dialogs(processes):
                return ActionStatus(RUNNING, "Открыто", "Окно «Свойства: Мышь» открыто")
            return ActionStatus(IDLE, "Закрыто", "Окно настроек мыши сейчас не открыто")

        # url
        if launching:
            return ActionStatus(STARTING, "Запуск", "Открытие браузера…")
        with self._lock:
            opened = self._opened_at.get(action.id)
        if opened:
            return ActionStatus(RUNNING, "Открыто", "Последнее открытие: " + time.strftime("%H:%M:%S", time.localtime(opened)))
        return ActionStatus(IDLE, "Готово", "Откроется в браузере по умолчанию")

    def pop_timeouts(self) -> list[str]:
        with self._lock:
            items, self._timed_out = self._timed_out, []
        return items

    @staticmethod
    def _mouse_dialogs(processes: dict[int, str]) -> list[int]:
        pids = {pid for pid, name in processes.items() if name == "rundll32.exe"}
        return winapi.find_dialogs(pids, MOUSE_TITLE_KEYWORDS)

    # ---------------------------------------------------------------- запуск
    def launch(self, action_id: str) -> LaunchResult:
        """Выполнить одно действие. Вызывается из рабочего потока."""
        action = ACTIONS_BY_ID[action_id]
        with self._lock:
            self._launching.add(action_id)
        try:
            if action.kind == "exe":
                return self._launch_exe(action)
            if action.kind == "cpl":
                return self._launch_mouse(action)
            return self._launch_url(action)
        except winapi.ShellLaunchError as exc:
            log.warning("Запуск %s не удался: %s", action_id, exc)
            return LaunchResult(False, False, f"{action.title}: {exc}")
        except Exception as exc:
            log.exception("Непредвиденная ошибка запуска %s", action_id)
            return LaunchResult(False, False, f"{action.title}: непредвиденная ошибка — {exc}")
        finally:
            with self._lock:
                self._launching.discard(action_id)

    def _launch_exe(self, action: ActionDef) -> LaunchResult:
        resolved = self.resolve_path(action.id)
        if not resolved.path:
            return LaunchResult(False, False, resolved.problem)
        running = set(winapi.list_processes().values())
        if self._process_names(action) & running:
            return LaunchResult(True, True, action.skipped_text)
        winapi.shell_open(resolved.path, cwd=str(Path(resolved.path).parent))
        with self._lock:
            self._pending[action.id] = time.monotonic()
        log.info("Запущен %s: %s", action.id, resolved.path)
        return LaunchResult(True, False, action.success_text)

    def _launch_mouse(self, action: ActionDef) -> LaunchResult:
        if not detect.detect_mouse_cpl():
            return LaunchResult(False, False, "Панель настроек мыши (main.cpl) не найдена в System32")
        dialogs = self._mouse_dialogs(winapi.list_processes())
        if dialogs:
            winapi.bring_to_front(dialogs[0])
            return LaunchResult(True, True, action.skipped_text)
        winapi.shell_open(detect.control_exe(), "main.cpl")
        return LaunchResult(True, False, action.success_text)

    def _launch_url(self, action: ActionDef) -> LaunchResult:
        winapi.shell_open(FACEIT_URL)
        with self._lock:
            self._opened_at[action.id] = time.time()
        return LaunchResult(True, False, action.success_text)


def _is_file(path: str) -> bool:
    try:
        return os.path.isfile(path)
    except (OSError, ValueError):
        return False
