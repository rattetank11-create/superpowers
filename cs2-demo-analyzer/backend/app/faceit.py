"""Поиск аккаунта FACEIT игрока по SteamID (и запасной вариант — по нику).

Официальный FACEIT Data API v4, ключ только на сервере (FACEIT_API_KEY).
Названия полей взяты из документации FACEIT Data API v4 и разбираются терпимо
(отсутствующее поле -> None). Проверить реальный ответ:
    python -m scripts.faceit_probe <steamid64>

Любая ошибка FACEIT не ломает анализ: возвращается статус unavailable/no_key.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

API_BASE = "https://open.faceit.com/data/v4"

FOUND = "found"
NOT_FOUND = "not_found"
UNAVAILABLE = "unavailable"
NO_KEY = "no_key"

MESSAGES = {
    NOT_FOUND: "Аккаунт FACEIT не найден.",
    UNAVAILABLE: "FACEIT сейчас недоступен — показываем оценку по метрикам.",
    NO_KEY: "Поиск на FACEIT пока не подключён — показываем оценку по метрикам.",
}


class _MemoryCache:
    def __init__(self):
        self._data: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._data.get(key)
            if item and item[0] > time.time():
                return item[1]
            self._data.pop(key, None)
            return None

    def setex(self, key: str, ttl: int, value: str) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl, value)


def parse_player(data: dict[str, Any]) -> dict[str, Any]:
    """Нужные поля из ответа /players. Отсутствующие поля -> None."""
    cs2 = (data.get("games") or {}).get("cs2") or {}
    nickname = data.get("nickname")
    url = data.get("faceit_url") or (f"https://www.faceit.com/{{lang}}/players/{nickname}" if nickname else None)
    return {
        "player_id": data.get("player_id"),
        "nickname": nickname,
        "avatar": data.get("avatar") or None,
        "url": url.replace("{lang}", "ru") if url else None,
        "country": data.get("country"),
        "elo": cs2.get("faceit_elo"),
        "level": cs2.get("skill_level"),
        "steam_ids": sorted({str(s) for s in (data.get("steam_id_64"), cs2.get("game_player_id")) if s}),
    }


class FaceitClient:
    def __init__(
        self,
        api_key: str,
        timeout: float = 5.0,
        cache=None,
        cache_ttl: int = 3600,
        transport: httpx.BaseTransport | None = None,
    ):
        self.api_key = api_key.strip()
        self.cache = cache if cache is not None else _MemoryCache()
        self.cache_ttl = cache_ttl
        self._http = httpx.Client(
            base_url=API_BASE,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
            transport=transport,
        )

    def _get(self, params: dict[str, str]) -> dict[str, Any] | None:
        """200 -> JSON, 404 -> None, остальное -> исключение."""
        resp = self._http.get("/players", params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def lookup(self, steamid: str, nickname: str | None = None, use_cache: bool = True) -> dict[str, Any]:
        """Результат: {"status": found|not_found|unavailable|no_key, "account": {...}|None, "message": str|None}."""
        if not self.api_key:
            return {"status": NO_KEY, "account": None, "message": MESSAGES[NO_KEY]}
        key = f"faceit:{steamid}"
        if use_cache:
            try:
                cached = self.cache.get(key)
            except Exception:  # noqa: BLE001 — кэш не должен ломать поиск
                cached = None
            if cached:
                return json.loads(cached)

        try:
            result = self._lookup(str(steamid), nickname)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("FACEIT lookup failed for %s: %s", steamid, exc)
            return {"status": UNAVAILABLE, "account": None, "message": MESSAGES[UNAVAILABLE]}

        try:
            self.cache.setex(key, self.cache_ttl, json.dumps(result))
        except Exception:  # noqa: BLE001
            log.warning("FACEIT cache write failed", exc_info=True)
        return result

    def _lookup(self, steamid: str, nickname: str | None) -> dict[str, Any]:
        data = self._get({"game": "cs2", "game_player_id": steamid})
        account = parse_player(data) if data else None

        if account is None and nickname:
            # Ники в демке и на FACEIT часто разные — принимаем только при совпадении SteamID.
            by_nick = self._get({"nickname": nickname})
            if by_nick:
                candidate = parse_player(by_nick)
                if steamid in candidate["steam_ids"]:
                    account = candidate

        if account is None or account["elo"] is None:
            return {"status": NOT_FOUND, "account": None, "message": MESSAGES[NOT_FOUND]}
        return {"status": FOUND, "account": account, "message": None}

    def close(self) -> None:
        self._http.close()


def make_client(settings) -> FaceitClient:
    cache = None
    if settings.task_mode == "rq":
        try:
            from redis import Redis

            cache = Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception:  # noqa: BLE001
            cache = None
    return FaceitClient(
        settings.faceit_api_key,
        timeout=settings.faceit_timeout_seconds,
        cache=cache,
        cache_ttl=settings.faceit_cache_seconds,
    )


def faceit_block(lookup: dict[str, Any], report: dict[str, Any], adjust_cfg: dict, levels: dict) -> dict[str, Any]:
    """Блок report["faceit"]: аккаунт + поправка ELO по этой игре."""
    from analysis.rating import adjust_faceit_elo

    block = {**lookup, "checked_at": int(time.time()), "adjustment": None}
    account = lookup.get("account")
    if lookup.get("status") == FOUND and account and account.get("elo") is not None:
        ov = report.get("overview", {})
        block["adjustment"] = adjust_faceit_elo(
            float(account["elo"]),
            float(report["rating"]["elo"]),
            int(ov.get("kills", 0)),
            float(ov.get("adr", 0.0)),
            adjust_cfg,
            levels,
        )
    return block
