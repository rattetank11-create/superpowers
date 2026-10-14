"""Полный анализ демки: отчёты сразу для всех игроков матча.

Считаем всех игроков за один проход, чтобы демку можно было удалить сразу
после анализа, а выбор игрока на сайте был мгновенным.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .counterstrafe import analyze_counterstrafe
from .crosshair import analyze_crosshair, spotted_pairs
from .duels import basic_stats, build_duels, enrich_duels, shot_accuracy, summarize_duels
from .geometry import TickIndex
from .loader import MatchData, ProgressFn, load_match
from .rating import estimate_elo, extract_features
from .recommendations import evaluate_rules
from .settings import load_elo_model, load_faceit_levels, load_thresholds, load_weapons
from .trades import analyze_trades

REPORT_VERSION = 1


def analyze_player(match: MatchData, steamid: int, ctx: dict[str, Any]) -> dict[str, Any]:
    th, weapons, tickrate = ctx["thresholds"], ctx["weapons"], match.tickrate
    sec = lambda s: int(round(s * tickrate))  # noqa: E731
    names = ctx["names"]
    my_ticks = match.ticks[match.ticks["steamid"] == steamid]
    my_shots = match.shots[match.shots["steamid"] == steamid]
    rounds_played = int(match.ticks.loc[match.ticks["steamid"] == steamid, "round_num"].nunique())

    cs = analyze_counterstrafe(
        my_shots,
        my_ticks,
        weapons,
        th["counterstrafe"],
        tickrate,
        th["general"]["max_plausible_speed"],
        match.rounds,
    )
    accuracy = shot_accuracy(match.shots, match.hurts, steamid, weapons, sec(th["counterstrafe"]["burst_gap_seconds"]))
    duels = build_duels(match.hurts, match.deaths, steamid, sec(th["duels"]["duel_gap_seconds"]))
    duels = enrich_duels(duels, steamid, match.shots, match.blinds, match.deaths, ctx["index"], th["duels"], tickrate)
    duel_summary = summarize_duels(duels, names, tickrate)
    crosshair = analyze_crosshair(ctx["pairs"], steamid, ctx["index"], th["crosshair"], tickrate, names, match.rounds)
    trades = analyze_trades(match.deaths, steamid, sec(th["trades"]["trade_window_seconds"]))
    overview = basic_stats(match.deaths, match.hurts, steamid, rounds_played)

    report: dict[str, Any] = {
        "version": REPORT_VERSION,
        "player": {"steamid": str(steamid), "name": names.get(steamid, str(steamid))},
        "match": ctx["match_meta"],
        "overview": overview,
        "counterstrafe": cs,
        "accuracy": accuracy,
        "duels": duel_summary,
        "crosshair": crosshair,
        "trades": trades,
    }
    late_ms = th["counterstrafe"]["late_after_stop_ticks"] * 1000 / tickrate
    report["recommendations"] = evaluate_rules(report, th["recommendations"], late_after_stop_ms=late_ms)
    report["rating"] = estimate_elo(extract_features(report), ctx["elo_model"], ctx["levels"], rounds_played)
    return report


def analyze_match(match: MatchData, progress: ProgressFn | None = None) -> dict[str, Any]:
    th = load_thresholds()
    names = {int(s): str(n) for s, n in zip(match.players["steamid"], match.players["name"])}
    meta = {
        "map": match.map_name,
        "rounds": int(len(match.rounds)),
        "server": match.header.get("server_name"),
        "tickrate": match.tickrate,
        "score": _score(match),
    }
    ctx = {
        "thresholds": th,
        "weapons": load_weapons(),
        "elo_model": load_elo_model(),
        "levels": load_faceit_levels(),
        "names": names,
        "index": TickIndex(match.ticks),
        "pairs": spotted_pairs(match.ticks),
        "match_meta": meta,
    }
    players = []
    reports = {}
    total = max(len(match.players), 1)
    for i, row in enumerate(match.players.itertuples()):
        sid = int(row.steamid)
        if progress:
            progress(70 + int(28 * i / total), "players")
        reports[str(sid)] = analyze_player(match, sid, ctx)
        last_team = match.ticks.loc[match.ticks["steamid"] == sid, "team_num"]
        players.append(
            {
                "steamid": str(sid),
                "name": names[sid],
                "team": int(last_team.iloc[-1]) if len(last_team) else int(row.team_number or 0),
                "kills": reports[str(sid)]["overview"]["kills"],
                "deaths": reports[str(sid)]["overview"]["deaths"],
            }
        )
    return {"match": meta, "players": players, "reports": reports}


def _score(match: MatchData) -> dict[str, int]:
    winners = match.rounds["winner"].dropna().astype(int)
    return {"t": int((winners == 2).sum()), "ct": int((winners == 3).sum())}


def analyze_demo(path: str | Path, progress: ProgressFn | None = None) -> dict[str, Any]:
    th = load_thresholds()
    match = load_match(path, tickrate=int(th["general"]["tickrate"]), progress=progress)
    return analyze_match(match, progress)
