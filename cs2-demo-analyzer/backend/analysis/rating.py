"""Оценка уровня FACEIT по метрикам.

Модель линейная: ELO = intercept + Σ weight_i * (x_i - mean_i) / std_i.
Веса лежат в config/elo_model.json и переобучаются скриптом scripts/calibrate_elo.py.
Пропущенная метрика (мало данных) даёт вклад 0 и расширяет диапазон.
Результат — диапазон (±residual_std), а не точное число.
"""

from __future__ import annotations

from typing import Any

FEATURES = (
    "cs_perfect_pct",
    "first_bullet_acc_pct",
    "hs_pct",
    "duel_winrate",
    "opening_winrate",
    "crosshair_median_deg",
    "median_ttk_ms",
    "kpr",
    "adr",
)


def extract_features(report: dict[str, Any]) -> dict[str, float | None]:
    """Вектор признаков из готового отчёта игрока (тот же, что использует калибровка)."""
    cs = report.get("counterstrafe", {})
    acc = report.get("accuracy", {})
    du = report.get("duels", {})
    ov = report.get("overview", {})
    ch = report.get("crosshair", {})
    return {
        "cs_perfect_pct": cs.get("perfect_pct"),
        "first_bullet_acc_pct": acc.get("first_bullet_accuracy_pct"),
        "hs_pct": ov.get("hs_pct"),
        "duel_winrate": du.get("winrate"),
        "opening_winrate": (du.get("opening") or {}).get("winrate"),
        "crosshair_median_deg": ch.get("median_angle"),
        "median_ttk_ms": du.get("median_ttk_ms"),
        "kpr": ov.get("kpr"),
        "adr": ov.get("adr"),
    }


def level_for_elo(elo: float, levels: dict[str, Any]) -> int:
    for lv in levels["levels"]:
        if lv["max"] is None or elo <= lv["max"]:
            return int(lv["level"])
    return int(levels["levels"][-1]["level"])


def estimate_elo(
    features: dict[str, float | None],
    model: dict[str, Any],
    levels: dict[str, Any],
    rounds_played: int,
) -> dict[str, Any]:
    score = float(model["intercept"])
    contributions = []
    missing = []
    for name, spec in model["features"].items():
        value = features.get(name)
        if value is None:
            missing.append(name)
            continue
        z = (float(value) - spec["mean"]) / spec["std"] if spec["std"] else 0.0
        z = max(-3.0, min(3.0, z))  # один выброс не должен ломать оценку
        delta = spec["weight"] * z
        score += delta
        contributions.append({"feature": name, "value": value, "delta": round(delta)})

    spread = float(model["residual_std"])
    if missing:
        spread *= 1 + 0.1 * len(missing)
    if rounds_played < 12:  # короткая демка — меньше уверенности
        spread *= 1.5

    floor = float(levels.get("min_elo", 100))
    point = max(floor, score)
    low, high = max(floor, point - spread), point + spread
    contributions.sort(key=lambda c: -abs(c["delta"]))
    return {
        "elo": round(point),
        "elo_low": round(low),
        "elo_high": round(high),
        "level": level_for_elo(point, levels),
        "level_low": level_for_elo(low, levels),
        "level_high": level_for_elo(high, levels),
        "model_version": model.get("version"),
        "calibrated": bool(model.get("calibrated")),
        "missing_features": missing,
        "contributions": contributions,
        "disclaimer": "Это оценка по одной демке, а не реальный ELO FACEIT.",
    }
