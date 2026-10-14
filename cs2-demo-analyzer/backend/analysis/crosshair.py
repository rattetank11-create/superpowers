"""Crosshair placement: угол между прицелом и головой врага в момент обнаружения.

ПРИБЛИЖЕНИЕ. Точной видимости (raycast) в демке нет. Момент "враг стал видим" берём
из серверного флага m_bSpottedByMask (prop `approximate_spotted_by` в demoparser2):
сервер выставляет его, когда враг попадает в зону видимости игрока (тот же механизм,
что подсвечивает врага на радаре). Голова цели — позиция + высота глаз
(с учётом приседа). Флаг обновляется с небольшой задержкой и не учитывает дым идеально,
поэтому метрика — оценка, что явно помечается в отчёте.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .geometry import TickIndex, aim_error
from .util import pct, records as to_records

ANGLE_BINS = [(0, 2), (2, 5), (5, 10), (10, 20), (20, 45), (45, 180)]


def spotted_pairs(ticks: pd.DataFrame) -> pd.DataFrame:
    """Разворачивает approximate_spotted_by в пары (tick, steamid=кого видят, spotter=кто видит)."""
    t = ticks[["tick", "steamid", "round_num", "approximate_spotted_by"]]
    t = t[t["approximate_spotted_by"].map(lambda lst: lst is not None and len(lst) > 0)]
    ex = t.explode("approximate_spotted_by").rename(columns={"approximate_spotted_by": "spotter"})
    ex["spotter"] = ex["spotter"].astype("int64")
    return ex.reset_index(drop=True)


def spot_events(pairs: pd.DataFrame, steamid: int, cooldown_ticks: int) -> pd.DataFrame:
    """Моменты, когда игрок `steamid` впервые заметил каждого врага.

    `pairs`: результат spotted_pairs(). Повторное обнаружение того же врага
    раньше cooldown_ticks после последнего тика видимости не считается новым.
    Возвращает tick, enemy, round_num.
    """
    seen = pairs[pairs["spotter"] == int(steamid)].sort_values(["steamid", "tick"])
    rows = []
    for enemy, g in seen.groupby("steamid"):
        t = g["tick"].to_numpy()
        new = np.diff(t, prepend=-(10**9)) > cooldown_ticks
        for tick, rnd in zip(t[new], g["round_num"].to_numpy()[new]):
            rows.append({"tick": int(tick), "enemy": int(enemy), "round_num": rnd})
    return pd.DataFrame(rows, columns=["tick", "enemy", "round_num"])


def analyze_crosshair(
    pairs: pd.DataFrame,
    steamid: int,
    index: TickIndex,
    cfg: dict[str, Any],
    tickrate: int,
    names: dict[int, str] | None = None,
    rounds: pd.DataFrame | None = None,
) -> dict[str, Any]:
    names = names or {}
    events = spot_events(pairs, steamid, int(round(cfg["respot_cooldown_seconds"] * tickrate)))
    round_start = dict(zip(rounds["round_num"], rounds["start_tick"])) if rounds is not None else {}
    samples = []
    for ev in events.itertuples():
        me, enemy = index.get(steamid, ev.tick), index.get(ev.enemy, ev.tick)
        if me is None or enemy is None:
            continue
        stand, crouch = cfg["eye_height_standing"], cfg["eye_height_crouch_delta"]
        angle, yaw_err, pitch_err, dist = aim_error(me.eye(stand, crouch), me.pitch, me.yaw, enemy.eye(stand, crouch))
        if dist > cfg["max_distance"]:
            continue
        rnd = ev.round_num
        samples.append(
            {
                "round": int(rnd) if pd.notna(rnd) else None,
                "tick": int(ev.tick),
                "round_time": round((ev.tick - round_start[rnd]) / tickrate, 1) if rnd in round_start else None,
                "enemy": names.get(ev.enemy, str(ev.enemy)),
                "angle": round(angle, 1),
                "yaw_err": round(yaw_err, 1),
                "pitch_err": round(pitch_err, 1),
                "distance": round(dist),
            }
        )
    return summarize_crosshair(samples, cfg)


def summarize_crosshair(samples: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    df = pd.DataFrame(samples)
    base = {
        "approximate": True,
        "method": "m_bSpottedByMask (серверная видимость/радар) + голова = позиция + высота глаз",
    }
    if df.empty:
        return {**base, "samples": 0, "median_angle": None, "histogram": [], "worst": [], "events": []}
    # "В поле зрения" — враг появился в пределах 90° от прицела; остальные — сзади/сбоку.
    front = df[df["angle"] <= 90]
    hist = [
        {"bin": f"{lo}–{hi}°" if hi < 180 else f"{lo}°+", "count": int(((df["angle"] >= lo) & (df["angle"] < hi)).sum())}
        for lo, hi in ANGLE_BINS
    ]
    return {
        **base,
        "samples": int(len(df)),
        "front_samples": int(len(front)),
        "median_angle": round(float(front["angle"].median()), 1) if len(front) else None,
        "mean_angle": round(float(front["angle"].mean()), 1) if len(front) else None,
        "good_pct": pct(int((front["angle"] <= cfg["good_angle_deg"]).sum()), len(front)),
        "median_abs_yaw_err": round(float(front["yaw_err"].abs().median()), 1) if len(front) else None,
        "median_pitch_err": round(float(front["pitch_err"].median()), 1) if len(front) else None,
        "behind_pct": pct(int((df["angle"] > 90).sum()), len(df)),
        "histogram": hist,
        "worst": to_records(front.sort_values("angle", ascending=False).head(10)),
        "events": to_records(df),
    }
