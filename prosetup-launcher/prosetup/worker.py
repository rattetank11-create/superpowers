"""Последовательный запуск действий в фоновом потоке (интерфейс не зависает)."""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Signal, Slot

from . import winapi
from .engine import Engine, LaunchResult

log = logging.getLogger(__name__)


class LaunchWorker(QObject):
    step_started = Signal(str, int, int)          # id, индекс, всего
    step_finished = Signal(str, bool, bool, str)  # id, ok, skipped, сообщение
    finished = Signal(int, int, int)              # успешно, пропущено, ошибок

    def __init__(self, engine: Engine, action_ids: list[str], delay: float) -> None:
        super().__init__()
        self.engine = engine
        self.action_ids = list(action_ids)
        self.delay = max(0.0, float(delay))
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        ok = skipped = failed = 0
        total = len(self.action_ids)
        com_ready = winapi.co_initialize()
        try:
            for index, action_id in enumerate(self.action_ids):
                if self._cancelled:
                    break
                self.step_started.emit(action_id, index, total)
                try:
                    result = self.engine.launch(action_id)
                except Exception as exc:  # страховка: ошибка одного шага не прерывает сетап
                    log.exception("Сбой шага %s", action_id)
                    result = LaunchResult(False, False, f"Непредвиденная ошибка: {exc}")
                if not result.ok:
                    failed += 1
                elif result.skipped:
                    skipped += 1
                else:
                    ok += 1
                self.step_finished.emit(action_id, result.ok, result.skipped, result.message)
                # Пауза только если что-то действительно запускалось
                if index < total - 1 and not result.skipped and result.ok:
                    self._sleep(self.delay)
        finally:
            if com_ready:
                winapi.co_uninitialize()
            self.finished.emit(ok, skipped, failed)

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._cancelled and time.monotonic() < end:
            time.sleep(0.05)
