"""FACEIT-клиент на mock-ответах (реальный API в тестах не вызывается)."""

import httpx
import pytest

from app.faceit import FOUND, NO_KEY, NOT_FOUND, UNAVAILABLE, FaceitClient, faceit_block, parse_player

STEAM = "76561198265366770"


def player_json(steamid=STEAM, nickname="s1mple_fan", elo=1620, level=8):
    return {
        "player_id": "a1b2c3",
        "nickname": nickname,
        "avatar": "https://distribution.faceit-cdn.net/images/avatar.jpg",
        "country": "ru",
        "steam_id_64": steamid,
        "faceit_url": f"https://www.faceit.com/{{lang}}/players/{nickname}",
        "games": {"cs2": {"faceit_elo": elo, "skill_level": level, "game_player_id": steamid}},
    }


def make_client(handler, key="test-key"):
    calls = []

    def wrapped(request: httpx.Request):
        calls.append(request)
        return handler(request)

    return FaceitClient(key, transport=httpx.MockTransport(wrapped)), calls


def test_found_by_steamid():
    client, calls = make_client(lambda r: httpx.Response(200, json=player_json()))
    res = client.lookup(STEAM, "игрок из демки")
    assert res["status"] == FOUND
    acc = res["account"]
    assert (acc["nickname"], acc["elo"], acc["level"]) == ("s1mple_fan", 1620, 8)
    assert acc["url"] == "https://www.faceit.com/ru/players/s1mple_fan"
    assert calls[0].url.params["game_player_id"] == STEAM
    assert calls[0].url.params["game"] == "cs2"
    assert calls[0].headers["Authorization"] == "Bearer test-key"


def test_fallback_to_nickname_requires_same_steamid():
    def handler(r):
        if "game_player_id" in r.url.params:
            return httpx.Response(404, json={"errors": []})
        return httpx.Response(200, json=player_json(nickname=r.url.params["nickname"]))

    client, calls = make_client(handler)
    res = client.lookup(STEAM, "Nick")
    assert res["status"] == FOUND and res["account"]["nickname"] == "Nick"
    assert len(calls) == 2


def test_nickname_with_other_steamid_is_rejected():
    def handler(r):
        if "game_player_id" in r.url.params:
            return httpx.Response(404)
        return httpx.Response(200, json=player_json(steamid="76561190000000000"))

    client, _ = make_client(handler)
    res = client.lookup(STEAM, "Nick")
    assert res["status"] == NOT_FOUND
    assert res["message"] == "Аккаунт FACEIT не найден."


def test_not_found():
    client, _ = make_client(lambda r: httpx.Response(404))
    assert client.lookup(STEAM, "Nick")["status"] == NOT_FOUND


def test_account_without_cs2_is_not_found():
    data = player_json()
    data["games"] = {}
    client, _ = make_client(lambda r: httpx.Response(200, json=data))
    assert client.lookup(STEAM)["status"] == NOT_FOUND


def test_timeout_is_unavailable_and_not_cached():
    def handler(r):
        raise httpx.ReadTimeout("timeout", request=r)

    client, calls = make_client(handler)
    assert client.lookup(STEAM)["status"] == UNAVAILABLE
    client.lookup(STEAM)
    assert len(calls) == 2  # ошибка не кэшируется


def test_server_error_is_unavailable():
    client, _ = make_client(lambda r: httpx.Response(503))
    assert client.lookup(STEAM)["status"] == UNAVAILABLE


def test_no_key_makes_no_requests():
    client, calls = make_client(lambda r: httpx.Response(200, json=player_json()), key="")
    res = client.lookup(STEAM)
    assert res["status"] == NO_KEY and not calls


def test_cache_hit_and_bypass():
    client, calls = make_client(lambda r: httpx.Response(200, json=player_json()))
    client.lookup(STEAM)
    client.lookup(STEAM)
    assert len(calls) == 1
    client.lookup(STEAM, use_cache=False)
    assert len(calls) == 2


def test_parse_player_tolerates_missing_fields():
    p = parse_player({"nickname": "x"})
    assert p["elo"] is None and p["steam_ids"] == [] and p["url"].endswith("/players/x")


def test_faceit_block_adds_adjustment(thresholds):
    from analysis.settings import load_faceit_levels

    report = {"overview": {"kills": 15, "adr": 80.0}, "rating": {"elo": 1300}}
    lookup = {"status": FOUND, "account": {**parse_player(player_json(elo=1500)), "elo": 1500}, "message": None}
    block = faceit_block(lookup, report, thresholds["faceit_adjustment"], load_faceit_levels())
    adj = block["adjustment"]
    assert adj["current_elo"] == 1500 and adj["tier"] == "bad"
    assert adj["new_elo"] == 1500 + adj["delta"]

    missing = faceit_block({"status": NOT_FOUND, "account": None, "message": "x"}, report, thresholds["faceit_adjustment"], load_faceit_levels())
    assert missing["adjustment"] is None


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Страховка: реальный FACEIT в тестах недоступен."""
    monkeypatch.setenv("FACEIT_API_KEY", "")
