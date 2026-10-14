"""Анализ контрстрейфов по первому выстрелу каждой очереди.

Логика:
  1. Очередь — серия выстрелов из одного оружия с паузой не больше burst_gap_seconds.
     Смотрим только первый выстрел очереди: именно его точность решает контрстрейф.
  2. Скорость в момент выстрела сравниваем с порогом точности
     (accuracy_speed_ratio * макс. скорость оружия, в прицеле — скорость в прицеле).
     Категории: perfect (≤ порога), slow (≤ slow_speed_ratio), moving, air (в прыжке).
  3. Тайминг. Если в демке есть кнопки (`buttons`), начало торможения — первый тик,
     после которого клавиши перестали толкать игрока по направлению движения.
     Нажата противоположная клавиша → техника "counter", просто отпустил → "release".
     Без кнопок начало торможения берём как пик скорости в окне перед выстрелом.
     Дальше: выстрел до того, как скорость упала ниже порога → "early";
     ожидание после остановки дольше late_after_stop_ticks → "late"; иначе "good".
  4. Выстрелы, перед которыми игрок не разгонялся выше порога, — "с места":
     контрстрейф там не нужен, в % идеальных контрстрейфов они не входят.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .util import pct, records as to_records
from .settings import WeaponSpec, normalize_weapon

# Биты InputBitMask_t, проверены на демке: W даёт движение вперёд по yaw,
# A — влево, D — вправо, S — назад.
IN_ATTACK = 1 << 0
IN_JUMP = 1 << 1
IN_DUCK = 1 << 2
IN_FORWARD = 1 << 3
IN_BACK = 1 << 4
IN_MOVELEFT = 1 << 9
IN_MOVERIGHT = 1 << 10
IN_SPEED = 1 << 16  # шаг (Shift)

CATEGORIES = ("perfect", "slow", "moving", "air")


def first_shots_of_bursts(shots: pd.DataFrame, gap_ticks: int) -> pd.DataFrame:
    """Первые выстрелы очередей. `shots`: tick, weapon (+ любые колонки), одного игрока."""
    if shots.empty:
        return shots.copy()
    s = shots.sort_values("tick").reset_index(drop=True)
    weapon = s["weapon"].map(normalize_weapon)
    gap = s["tick"].diff()
    new_burst = gap.isna() | (gap > gap_ticks) | (weapon != weapon.shift())
    return s[new_burst].reset_index(drop=True)


def input_vectors(buttons: np.ndarray, yaw_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Направление нажатых клавиш движения в мировых координатах (не нормировано)."""
    b = buttons.astype(np.int64)
    fwd = ((b & IN_FORWARD) > 0).astype(float) - ((b & IN_BACK) > 0).astype(float)
    left = ((b & IN_MOVELEFT) > 0).astype(float) - ((b & IN_MOVERIGHT) > 0).astype(float)
    yaw = np.radians(yaw_deg.astype(float))
    ix = fwd * np.cos(yaw) - left * np.sin(yaw)
    iy = fwd * np.sin(yaw) + left * np.cos(yaw)
    return ix, iy


def velocity_vectors(ticks: np.ndarray, x: np.ndarray, y: np.ndarray, tickrate: int) -> tuple[np.ndarray, np.ndarray]:
    """Горизонтальная скорость из разницы позиций (velocity_X/Y в демке пустые)."""
    dt = np.diff(ticks, prepend=ticks[:1] - 1).astype(float)
    dt[dt <= 0] = 1
    vx = np.diff(x.astype(float), prepend=x[:1]) * tickrate / dt
    vy = np.diff(y.astype(float), prepend=y[:1]) * tickrate / dt
    return vx, vy


def classify_speed(speed: float, limit: float, airborne: bool, accuracy_ratio: float, slow_ratio: float) -> str:
    if airborne:
        return "air"
    if speed <= accuracy_ratio * limit:
        return "perfect"
    if speed <= slow_ratio * limit:
        return "slow"
    return "moving"


def find_brake_start(
    speed: np.ndarray,
    push: np.ndarray,
    threshold: float,
    start: int,
    shot: int,
    use_buttons: bool,
) -> tuple[int | None, bool]:
    """Индекс начала торможения в окне [start, shot] и флаг "игрок всё ещё жмёт по ходу".

    push[k] > 0 — клавиши в тике k толкают игрока по направлению движения.
    """
    if use_buttons:
        k = shot
        while k >= start:
            if push[k] > 0 and speed[k] > threshold:
                break
            k -= 1
        if k == shot:
            return None, True  # стрелял, продолжая жать клавиши по ходу движения
        if k >= start:
            return k + 1, False
        # торможение началось раньше окна (или движения не было) — падаем на скорость
    window = speed[start : shot + 1]
    if window.size == 0 or window.max() <= threshold:
        return None, False
    return start + int(np.argmax(window)), False


def analyze_shot(
    i: int,
    t: np.ndarray,
    speed: np.ndarray,
    push: np.ndarray,
    counter: np.ndarray,
    airborne: np.ndarray,
    limit: float,
    cfg: dict[str, Any],
    tickrate: int,
    use_buttons: bool,
) -> dict[str, Any]:
    """Разбор одного выстрела по массивам тиков игрока (i — индекс тика выстрела)."""
    threshold = cfg["accuracy_speed_ratio"] * limit
    lookback = int(round(cfg["lookback_seconds"] * tickrate))
    start = i
    # окно назад — только по непрерывным тикам
    while start > 0 and i - start < lookback and t[start - 1] == t[start] - 1:
        start -= 1
    end = i
    while end + 1 < len(t) and end - i < cfg["lookahead_ticks"] and t[end + 1] == t[end] + 1:
        end += 1

    sp = float(speed[i])
    category = classify_speed(sp, limit, bool(airborne[i]), cfg["accuracy_speed_ratio"], cfg["slow_speed_ratio"])
    was_moving = bool(speed[start : i + 1].max() > threshold) if i >= start else False
    out: dict[str, Any] = {
        "speed": round(sp, 1),
        "threshold": round(threshold, 1),
        "speed_ratio": round(sp / limit, 3) if limit else None,
        "category": category,
        "context": "strafe" if was_moving else "stationary",
        "technique": None,
        "timing": None,
        "brake_to_shot_ticks": None,
        "stop_to_shot_ticks": None,
    }
    if not was_moving or category == "air":
        return out

    brake, still_pushing = find_brake_start(speed, push, threshold, start, i, use_buttons)
    if still_pushing:
        out["technique"] = "none"
        out["timing"] = "early"
        return out
    if brake is None:
        return out
    if use_buttons:
        # Противоположную клавишу часто жмут через 1–3 тика после отпускания основной.
        counter_window = counter[brake : min(brake + cfg.get("counter_window_ticks", 4), i) + 1]
        out["technique"] = "counter" if counter_window.any() else "release"
    out["brake_to_shot_ticks"] = int(t[i] - t[brake])

    below = np.nonzero(speed[brake : end + 1] <= threshold)[0]
    stop = brake + int(below[0]) if below.size else None
    if stop is not None:
        out["stop_to_shot_ticks"] = int(t[i] - t[stop])
    if sp > threshold:
        out["timing"] = "early"
    elif stop is not None and t[i] - t[stop] > cfg["late_after_stop_ticks"]:
        out["timing"] = "late"
    else:
        out["timing"] = "good"
    return out


def analyze_counterstrafe(
    shots: pd.DataFrame,
    ticks: pd.DataFrame,
    weapons: dict[str, WeaponSpec],
    cfg: dict[str, Any],
    tickrate: int = 64,
    max_plausible_speed: float = 400.0,
    rounds: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Контрстрейфы одного игрока.

    shots: tick, weapon, round_num — все выстрелы игрока (weapon_fire).
    ticks: tick, X, Y, yaw, velocity, buttons, is_airborne, is_scoped — тики игрока (живого).
    """
    gun_shots = shots[shots["weapon"].map(normalize_weapon).isin(weapons.keys())]
    firsts = first_shots_of_bursts(gun_shots, int(round(cfg["burst_gap_seconds"] * tickrate)))

    tk = ticks.sort_values("tick").drop_duplicates("tick")
    t = tk["tick"].to_numpy()
    speed = tk["velocity"].to_numpy(dtype=float)
    speed = np.where(np.isfinite(speed) & (speed <= max_plausible_speed), speed, np.nan)
    buttons = tk["buttons"].to_numpy() if "buttons" in tk else np.zeros(len(tk), dtype=np.int64)
    use_buttons = bool(len(buttons)) and bool((buttons & (IN_FORWARD | IN_BACK | IN_MOVELEFT | IN_MOVERIGHT)).any())

    vx, vy = velocity_vectors(t, tk["X"].to_numpy(), tk["Y"].to_numpy(), tickrate)
    ix, iy = input_vectors(buttons, tk["yaw"].to_numpy())
    dot = ix * vx + iy * vy
    push = np.where(np.hypot(ix, iy) > 0, dot, 0.0)
    counter = dot < 0  # нажата клавиша против направления движения
    airborne = tk["is_airborne"].to_numpy(dtype=bool)
    scoped = tk["is_scoped"].to_numpy(dtype=bool) if "is_scoped" in tk else np.zeros(len(tk), dtype=bool)

    round_start = {}
    if rounds is not None and not rounds.empty:
        round_start = dict(zip(rounds["round_num"], rounds["start_tick"]))

    records = []
    for _, shot in firsts.iterrows():
        pos = int(np.searchsorted(t, shot["tick"]))
        if pos >= len(t) or t[pos] != shot["tick"] or np.isnan(speed[pos]):
            continue
        spec = weapons[normalize_weapon(shot["weapon"])]
        limit = spec.speed_limit(bool(scoped[pos]))
        sp = np.nan_to_num(speed, nan=0.0)
        rec = analyze_shot(pos, t, sp, push, counter, airborne, limit, cfg, tickrate, use_buttons)
        rnd = shot.get("round_num")
        rec.update(
            {
                "tick": int(shot["tick"]),
                "round": int(rnd) if pd.notna(rnd) else None,
                "round_time": round((int(shot["tick"]) - round_start[rnd]) / tickrate, 1) if rnd in round_start else None,
                "weapon": spec.key,
                "weapon_name": spec.name,
                "scoped": bool(scoped[pos]),
            }
        )
        records.append(rec)

    return summarize_counterstrafe(records, use_buttons, tickrate)



def summarize_counterstrafe(records: list[dict[str, Any]], buttons_available: bool, tickrate: int = 64) -> dict[str, Any]:
    df = pd.DataFrame(records)
    if df.empty:
        return {
            "buttons_available": buttons_available,
            "first_shots": 0,
            "strafe_shots": 0,
            "perfect_pct": None,
            "accurate_pct": None,
            "categories": {c: 0 for c in CATEGORIES},
            "strafe_categories": {c: 0 for c in CATEGORIES},
            "timing": {},
            "technique": {},
            "median_brake_to_shot_ms": None,
            "by_weapon": [],
            "speed_histogram": [],
            "shots": [],
            "worst": [],
        }

    strafe = df[df["context"] == "strafe"]
    cats = df["category"].value_counts().reindex(CATEGORIES, fill_value=0)
    strafe_cats = strafe["category"].value_counts().reindex(CATEGORIES, fill_value=0)
    timing = strafe["timing"].dropna().value_counts()
    technique = strafe["technique"].dropna().value_counts()
    brake = strafe["brake_to_shot_ticks"].dropna()

    by_weapon = []
    for weapon, g in df.groupby("weapon"):
        gs = g[g["context"] == "strafe"]
        by_weapon.append(
            {
                "weapon": weapon,
                "weapon_name": g["weapon_name"].iloc[0],
                "first_shots": int(len(g)),
                "strafe_shots": int(len(gs)),
                "perfect_pct": pct(int((gs["category"] == "perfect").sum()), len(gs)),
                "accurate_pct": pct(int((g["category"] == "perfect").sum()), len(g)),
                "moving_pct": pct(int(g["category"].isin(["moving", "air"]).sum()), len(g)),
                "median_speed": round(float(g["speed"].median()), 1),
            }
        )
    by_weapon.sort(key=lambda w: -w["first_shots"])

    # Гистограмма: доля от макс. скорости оружия, шаг 10%.
    bins = np.minimum((df["speed_ratio"].fillna(0) * 10).astype(int), 10)
    hist = []
    for b in range(11):
        sel = df[bins == b]
        hist.append(
            {
                "bin": f"{b * 10}–{b * 10 + 10}%" if b < 10 else "100%+",
                **{c: int((sel["category"] == c).sum()) for c in CATEGORIES},
            }
        )

    bad = df[df["category"].isin(["moving", "air"])].sort_values("speed_ratio", ascending=False)
    worst = bad.head(10)[["round", "tick", "round_time", "weapon_name", "speed", "category", "timing"]]

    return {
        "buttons_available": buttons_available,
        "first_shots": int(len(df)),
        "strafe_shots": int(len(strafe)),
        "perfect_pct": pct(int(strafe_cats["perfect"]), len(strafe)),
        "accurate_pct": pct(int(cats["perfect"]), len(df)),
        "categories": {k: int(v) for k, v in cats.items()},
        "strafe_categories": {k: int(v) for k, v in strafe_cats.items()},
        "timing": {k: int(v) for k, v in timing.items()},
        "timing_pct": {k: pct(int(v), int(timing.sum())) for k, v in timing.items()},
        "technique": {k: int(v) for k, v in technique.items()},
        "technique_pct": {k: pct(int(v), int(technique.sum())) for k, v in technique.items()},
        "median_brake_to_shot_ms": round(float(brake.median()) * 1000 / tickrate) if len(brake) else None,
        "by_weapon": by_weapon,
        "speed_histogram": hist,
        "shots": to_records(df),
        "worst": to_records(worst),
    }
