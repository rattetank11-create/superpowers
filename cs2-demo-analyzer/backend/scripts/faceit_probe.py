"""Печатает СЫРОЙ ответ FACEIT Data API для SteamID (и/или ника) и то, как его разобрал клиент.

Запускать на сервере с ключом, чтобы сверить названия полей:
    FACEIT_API_KEY=... python -m scripts.faceit_probe 76561198265366770
    FACEIT_API_KEY=... python -m scripts.faceit_probe 76561198265366770 --nickname SomeNick
В docker-compose:
    docker compose exec api python -m scripts.faceit_probe 76561198265366770
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.faceit import API_BASE, parse_player  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("steamid")
    ap.add_argument("--nickname")
    args = ap.parse_args()
    key = os.environ.get("FACEIT_API_KEY", "").strip()
    if not key:
        raise SystemExit("Задайте FACEIT_API_KEY")

    headers = {"Authorization": f"Bearer {key}"}
    queries = [{"game": "cs2", "game_player_id": args.steamid}]
    if args.nickname:
        queries.append({"nickname": args.nickname})
    for params in queries:
        r = httpx.get(f"{API_BASE}/players", params=params, headers=headers, timeout=10)
        print(f"GET /players {params} -> HTTP {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            print(r.text[:2000])
            continue
        print(json.dumps(body, indent=2, ensure_ascii=False))
        if r.status_code == 200:
            print("разобрано клиентом:", json.dumps(parse_player(body), indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
