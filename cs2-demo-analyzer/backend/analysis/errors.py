"""Ошибки анализа с кодами, которые фронт показывает пользователю."""

from __future__ import annotations


class AnalysisError(Exception):
    """Базовая ошибка; `code` уходит в API, `message` — понятный текст по-русски."""

    code = "analysis_failed"
    message = "Не удалось проанализировать демку."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        if message:
            self.message = message


class NotADemoError(AnalysisError):
    code = "not_a_demo"
    message = "Файл не является демкой Counter-Strike (неверный заголовок)."


class LegacyDemoError(AnalysisError):
    code = "not_cs2"
    message = "Это демка CS:GO (Source 1). Поддерживаются только демки CS2."


class CorruptDemoError(AnalysisError):
    code = "corrupt_demo"
    message = "Демка повреждена или обрезана — парсер не смог её прочитать."


class NoRoundsError(AnalysisError):
    code = "no_rounds"
    message = "В демке не найдено ни одного сыгранного раунда (только разминка?)."


class PlayerNotFoundError(AnalysisError):
    code = "player_not_found"
    message = "Игрок с таким SteamID не найден в этой демке."
