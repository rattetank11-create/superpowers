"""Дуэли, точность и базовая статистика игрока.

Дуэль — обмен уроном между игроком и одним врагом, где паузы между попаданиями
не длиннее duel_gap_seconds. Итог: win (игрок убил соперника), loss (соперник убил
игрока) или none (никто никого не убил в этой дуэли).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .counterstrafe import first_shots_of_bursts
from .geometry import TickIndex, aim_error
from .util import pct, records as to_records
from .settings import WeaponSpec, normalize_weapon


def enemy_hurts(hurts: pd.DataFrame, steamid: int) -> pd.DataFrame:
    """Попадания между игроком и врагами (без урона по своим и от мира)."""
    h = hurts.dropna(subset=["attacker", "victim"])
    h = h[(h["attacker_team"] != h["victim_team"]) & (h["attacker"] != h["victim"])]
    h = h[(h["attacker"] == steamid) | (h["victim"] == steamid)].copy()
    h["opponent"] = np.where(h["attacker"] == steamid, h["victim"], h["attacker"]).astype("int64")
    h["outgoing"] = h["attacker"] == steamid
    return h.sort_values("tick")


def build_duels(hurts: pd.DataFrame, deaths: pd.DataFrame, steamid: int, gap_ticks: int) -> list[dict[str, Any]]:
    """Сегментирует обмены уроном на дуэли и определяет исход каждой."""
    h = enemy_hurts(hurts, steamid)
    duels: list[dict[str, Any]] = []
    for (rnd, opp), g in h.groupby(["round_num", "opponent"], sort=False):
        ticks = g["tick"].to_numpy()
        seg_ids = np.concatenate([[0], np.cumsum(np.diff(ticks) > gap_ticks)])
        for _, seg in g.groupby(seg_ids):
            start, end = int(seg["tick"].min()), int(seg["tick"].max())
            between = deaths[(deaths["tick"] >= start) & (deaths["tick"] <= end + 1)]
            won = between[(between["attacker"] == steamid) & (between["victim"] == opp)]
            lost = between[(between["attacker"] == opp) & (between["victim"] == steamid)]
            if len(won):
                result, kill = "win", won.iloc[0]
            elif len(lost):
                result, kill = "loss", lost.iloc[0]
            else:
                result, kill = "none", None
            first = seg.iloc[0]
            duels.append(
                {
                    "round": int(rnd),
                    "opponent": int(opp),
                    "start_tick": start,
                    "end_tick": end,
                    "result": result,
                    "kill_tick": int(kill["tick"]) if kill is not None else None,
                    "headshot": bool(kill["headshot"]) if kill is not None and result == "win" else None,
                    "damaged_first": bool(first["outgoing"]),
                    "dmg_dealt": int(seg.loc[seg["outgoing"], "dmg"].sum()),
                    "dmg_taken": int(seg.loc[~seg["outgoing"], "dmg"].sum()),
                    "my_team": int(first["attacker_team"] if first["outgoing"] else first["victim_team"]),
                }
            )
    duels.sort(key=lambda d: d["start_tick"])
    return duels


def opening_deaths(deaths: pd.DataFrame) -> pd.DataFrame:
    """Первое убийство врага в каждом раунде."""
    d = deaths.dropna(subset=["attacker", "victim"])
    d = d[(d["attacker_team"] != d["victim_team"])]
    return d.sort_values("tick").groupby("round_num").head(1)


def first_aimed_shot(
    shots: pd.DataFrame, shooter: int, target: int, start: int, end: int, index: TickIndex, max_angle: float
) -> int | None:
    """Тик первого выстрела `shooter` в сторону `target` в окне [start, end]."""
    s = shots[(shots["steamid"] == shooter) & (shots["tick"] >= start) & (shots["tick"] <= end)]
    for tick in s["tick"]:
        me, enemy = index.get(shooter, int(tick)), index.get(target, int(tick))
        if me is None or enemy is None:
            continue
        angle, *_ = aim_error(me.eye(), me.pitch, me.yaw, enemy.eye())
        if angle <= max_angle:
            return int(tick)
    return None


def enrich_duels(
    duels: list[dict[str, Any]],
    steamid: int,
    shots: pd.DataFrame,
    blinds: pd.DataFrame,
    deaths: pd.DataFrame,
    index: TickIndex,
    cfg: dict[str, Any],
    tickrate: int,
) -> list[dict[str, Any]]:
    """Добавляет к дуэлям: кто стрелял первым, TTK, флешки, кто пикнул, opening."""
    sec = lambda s: int(round(s * tickrate))  # noqa: E731
    openings = opening_deaths(deaths)
    opening_by_round = {int(r.round_num): r for r in openings.itertuples()}
    lookback = sec(cfg["first_shot_lookback_seconds"])
    flash_window = sec(cfg["flash_support_seconds"])
    peek_window = sec(cfg["peek_window_seconds"])
    gun_shots = shots[shots["weapon"].map(normalize_weapon) != ""]

    for d in duels:
        opp, start, end = d["opponent"], d["start_tick"], d["end_tick"]
        mine = first_aimed_shot(gun_shots, steamid, opp, start - lookback, end, index, cfg["aimed_shot_max_angle_deg"])
        theirs = first_aimed_shot(gun_shots, opp, steamid, start - lookback, end, index, cfg["aimed_shot_max_angle_deg"])
        if mine is None and theirs is None:
            d["shot_first"] = None
        elif theirs is None or (mine is not None and mine < theirs):
            d["shot_first"] = True
        elif mine is None or theirs < mine:
            d["shot_first"] = False
        else:
            d["shot_first"] = None  # один и тот же тик
        d["ttk_ms"] = (
            round((d["kill_tick"] - mine) * 1000 / tickrate) if d["result"] == "win" and mine is not None else None
        )

        fl = blinds[
            (blinds["tick"] >= start - flash_window)
            & (blinds["tick"] <= start)
            & (blinds["duration"] >= cfg["min_blind_seconds"])
        ]
        d["flash_support"] = bool(
            len(fl[(fl["victim"] == opp) & (fl["attacker_team"] == d["my_team"])])
        )
        d["got_flashed"] = bool(len(fl[(fl["victim"] == steamid) & (fl["attacker_team"] != d["my_team"])]))

        my_speed = index.mean_speed(steamid, start - peek_window, start)
        opp_speed = index.mean_speed(opp, start - peek_window, start)
        if my_speed is None or opp_speed is None:
            d["peeked"] = None
        else:
            d["peeked"] = bool(my_speed >= cfg["peek_min_speed"] and my_speed > opp_speed)

        me = index.get(steamid, start)
        enemy = index.get(opp, start)
        d["distance"] = round(float(np.linalg.norm(me.eye() - enemy.eye()))) if me and enemy else None

        op = opening_by_round.get(d["round"])
        d["opening"] = bool(
            op is not None
            and start <= op.tick <= end + 1
            and {int(op.attacker), int(op.victim)} == {steamid, opp}
        )
    return duels


def shot_accuracy(
    shots: pd.DataFrame,
    hurts: pd.DataFrame,
    steamid: int,
    weapons: dict[str, WeaponSpec],
    burst_gap_ticks: int,
    hit_window_ticks: int = 0,
) -> dict[str, Any]:
    """Точность: всех выстрелов и первой пули очереди.

    Попадание — урон по врагу в [t, t+window]; на реальной демке player_hurt всегда
    приходит в тот же тик, что и weapon_fire, поэтому окно по умолчанию 0.
    """
    s = shots[(shots["steamid"] == steamid) & shots["weapon"].map(normalize_weapon).isin(weapons.keys())]
    h = hurts[(hurts["attacker"] == steamid) & (hurts["attacker_team"] != hurts["victim_team"])]
    hit_ticks = np.sort(h["tick"].to_numpy())

    def hits(ticks: np.ndarray) -> np.ndarray:
        if not hit_ticks.size or not ticks.size:
            return np.zeros(len(ticks), dtype=bool)
        lo = np.searchsorted(hit_ticks, ticks)
        hi = np.searchsorted(hit_ticks, ticks + hit_window_ticks, side="right")
        return hi > lo

    all_hits = hits(s["tick"].to_numpy())
    firsts = first_shots_of_bursts(s, burst_gap_ticks)
    first_hits = hits(firsts["tick"].to_numpy())
    head_hits = h[h["hitgroup"] == "head"]
    return {
        "shots": int(len(s)),
        "hits": int(all_hits.sum()),
        "accuracy_pct": round(100 * all_hits.mean(), 1) if len(s) else None,
        "first_bullets": int(len(firsts)),
        "first_bullet_hits": int(first_hits.sum()),
        "first_bullet_accuracy_pct": round(100 * first_hits.mean(), 1) if len(firsts) else None,
        "head_hit_pct": round(100 * len(head_hits) / len(h), 1) if len(h) else None,
    }


def basic_stats(deaths: pd.DataFrame, hurts: pd.DataFrame, steamid: int, rounds_played: int) -> dict[str, Any]:
    d = deaths[deaths["attacker_team"] != deaths["victim_team"]]
    kills = d[d["attacker"] == steamid]
    died = deaths[deaths["victim"] == steamid]
    dmg = hurts[(hurts["attacker"] == steamid) & (hurts["attacker_team"] != hurts["victim_team"])]["dmg"].sum()
    k, n = len(kills), max(rounds_played, 1)
    return {
        "rounds": rounds_played,
        "kills": int(k),
        "deaths": int(len(died)),
        "headshot_kills": int(kills["headshot"].sum()),
        "hs_pct": round(100 * kills["headshot"].mean(), 1) if k else None,
        "kd": round(k / len(died), 2) if len(died) else float(k),
        "kpr": round(k / n, 2),
        "adr": round(float(dmg) / n, 1),
    }



def summarize_duels(duels: list[dict[str, Any]], names: dict[int, str], tickrate: int) -> dict[str, Any]:
    df = pd.DataFrame(duels)
    if df.empty:
        return {"total": 0, "decided": 0, "wins": 0, "losses": 0, "winrate": None, "by_round": [], "duels": [], "worst": []}
    df["opponent_name"] = df["opponent"].map(lambda s: names.get(int(s), str(s)))
    decided = df[df["result"] != "none"]
    wins = int((decided["result"] == "win").sum())

    def wr(sub: pd.DataFrame) -> dict[str, Any]:
        sub = sub[sub["result"] != "none"]
        w = int((sub["result"] == "win").sum())
        return {"count": int(len(sub)), "wins": w, "winrate": pct(w, len(sub))}

    opening = df[df["opening"]]
    known_first = df[df["shot_first"].notna()]
    ttk = df["ttk_ms"].dropna()
    peek = df[df["peeked"] == True]  # noqa: E712

    by_round = []
    for rnd, g in df.groupby("round"):
        by_round.append(
            {
                "round": int(rnd),
                "wins": int((g["result"] == "win").sum()),
                "losses": int((g["result"] == "loss").sum()),
                "none": int((g["result"] == "none").sum()),
            }
        )

    # Худшие моменты: проигранные opening-дуэли и дуэли, где выстрелил первым, но проиграл.
    lost = df[df["result"] == "loss"].copy()
    lost["badness"] = lost["opening"].astype(int) * 2 + (lost["shot_first"] == True).astype(int)  # noqa: E712
    worst = lost.sort_values(["badness", "dmg_dealt"], ascending=[False, True]).head(10)

    for col in ("kill_tick", "ttk_ms", "distance"):
        df[col] = df[col].astype("Int64")
        worst[col] = worst[col].astype("Int64")
    cols = [
        "round", "start_tick", "kill_tick", "opponent_name", "result", "opening", "shot_first",
        "damaged_first", "ttk_ms", "dmg_dealt", "dmg_taken", "flash_support", "got_flashed",
        "peeked", "distance", "headshot",
    ]
    return {
        "total": int(len(df)),
        "decided": int(len(decided)),
        "wins": wins,
        "losses": int(len(decided) - wins),
        "winrate": pct(wins, len(decided)),
        "opening": wr(opening),
        "shot_first_pct": pct(int(known_first["shot_first"].sum()), len(known_first)),
        "when_shot_first": wr(df[df["shot_first"] == True]),  # noqa: E712
        "when_shot_second": wr(df[df["shot_first"] == False]),  # noqa: E712
        "damaged_first_pct": pct(int(df["damaged_first"].sum()), len(df)),
        "median_ttk_ms": int(ttk.median()) if len(ttk) else None,
        "ttk_samples": int(len(ttk)),
        "peek_with_flash": wr(peek[peek["flash_support"]]),
        "peek_without_flash": wr(peek[~peek["flash_support"]]),
        "holding": wr(df[df["peeked"] == False]),  # noqa: E712
        "flashed_by_enemy": wr(df[df["got_flashed"]]),
        "by_round": by_round,
        "duels": to_records(df[cols]),
        "worst": to_records(worst[cols]),
        "approximations": [
            "Кто стрелял первым — по первому выстрелу в сторону соперника (угол до головы ≤ порога).",
            "«Пик» — игрок двигался быстрее соперника перед первым попаданием.",
        ],
    }
