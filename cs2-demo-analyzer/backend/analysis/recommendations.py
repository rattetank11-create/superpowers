"""Rule-based рекомендации.

Каждое правило берёт метрику из отчёта, сравнивает с порогом из thresholds.toml
([recommendations.<id>]) и, если метрика хуже порога и данных достаточно, выдаёт совет.
Тексты — в config/locales/<locale>.json (ключи <id>.title / <id>.text).

kind: "improve" — что подкачать, "stop" — что перестать делать.
Приоритет = severity * (1 + относительное отклонение от порога).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from .settings import load_messages

# getter(report) -> iterable of (value, samples, params)
Getter = Callable[[dict[str, Any]], Iterator[tuple[float | None, int, dict[str, Any]]]]


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str  # improve | stop
    direction: str  # below — плохо, если меньше порога; above — если больше
    getter: Getter
    category: str  # counterstrafe | duels | aim | teamplay


def _one(value, samples, **params):
    yield value, samples, params


def _cs(report):
    return report.get("counterstrafe", {})


def _du(report):
    return report.get("duels", {})


def _moving_weapons(report):
    for w in _cs(report).get("by_weapon", []):
        yield w.get("moving_pct"), w.get("first_shots", 0), {"weapon": w.get("weapon_name")}


def _timing_pct(key):
    def get(report):
        cs = _cs(report)
        total = sum((cs.get("timing") or {}).values())
        yield (cs.get("timing_pct") or {}).get(key, 0.0 if total else None), total, {}

    return get


def _air(report):
    cs = _cs(report)
    total = cs.get("first_shots", 0)
    air = (cs.get("categories") or {}).get("air", 0)
    yield (round(100 * air / total, 1) if total else None), total, {}


def _release(report):
    cs = _cs(report)
    total = sum((cs.get("technique") or {}).get(k, 0) for k in ("counter", "release"))
    rel = (cs.get("technique") or {}).get("release", 0)
    yield (round(100 * rel / total, 1) if total else None), total, {}


def _wr(key):
    def get(report):
        d = _du(report).get(key) or {}
        yield d.get("winrate"), d.get("count", 0), {"wins": d.get("wins"), "count": d.get("count")}

    return get


RULES: list[Rule] = [
    Rule("cs_perfect_low", "improve", "below", lambda r: _one(_cs(r).get("perfect_pct"), _cs(r).get("strafe_shots", 0)), "counterstrafe"),
    Rule("cs_moving_weapon", "stop", "above", _moving_weapons, "counterstrafe"),
    Rule("cs_early", "stop", "above", _timing_pct("early"), "counterstrafe"),
    Rule("cs_late", "improve", "above", _timing_pct("late"), "counterstrafe"),
    Rule("cs_release_only", "improve", "above", _release, "counterstrafe"),
    Rule("cs_air", "stop", "above", _air, "counterstrafe"),
    Rule("duel_winrate_low", "improve", "below", lambda r: _one(_du(r).get("winrate"), _du(r).get("decided", 0)), "duels"),
    Rule("opening_winrate_low", "stop", "below", _wr("opening"), "duels"),
    Rule("peek_no_flash", "stop", "below", _wr("peek_without_flash"), "duels"),
    Rule(
        "first_shot_low", "improve", "below",
        lambda r: _one(_du(r).get("shot_first_pct"), _du(r).get("total", 0)), "duels",
    ),
    Rule("ttk_high", "improve", "above", lambda r: _one(_du(r).get("median_ttk_ms"), _du(r).get("ttk_samples", 0)), "aim"),
    Rule(
        "first_bullet_acc_low", "improve", "below",
        lambda r: _one(r.get("accuracy", {}).get("first_bullet_accuracy_pct"), r.get("accuracy", {}).get("first_bullets", 0)),
        "aim",
    ),
    Rule("hs_low", "improve", "below", lambda r: _one(r.get("overview", {}).get("hs_pct"), r.get("overview", {}).get("kills", 0)), "aim"),
    Rule(
        "crosshair_angle_high", "improve", "above",
        lambda r: _one(r.get("crosshair", {}).get("median_angle"), r.get("crosshair", {}).get("front_samples", 0)), "aim",
    ),
    Rule(
        "crosshair_low", "stop", "above",
        lambda r: _one(r.get("crosshair", {}).get("median_pitch_err"), r.get("crosshair", {}).get("front_samples", 0)), "aim",
    ),
    Rule(
        "untraded_deaths", "stop", "below",
        lambda r: _one(r.get("trades", {}).get("traded_pct"), r.get("trades", {}).get("deaths", 0)), "teamplay",
    ),
    Rule(
        "trade_kills_low", "improve", "below",
        lambda r: _one(r.get("trades", {}).get("trade_kill_pct"), r.get("trades", {}).get("kills", 0)), "teamplay",
    ),
]


def _format(template: str, params: dict[str, Any]) -> str:
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def evaluate_rules(
    report: dict[str, Any],
    cfg: dict[str, Any],
    late_after_stop_ms: float = 94.0,
    locale: str = "ru",
    rules: list[Rule] | None = None,
) -> dict[str, Any]:
    messages = load_messages(locale)
    out: list[dict[str, Any]] = []
    for rule in rules or RULES:
        rc = cfg.get(rule.id)
        if not rc:
            continue
        threshold = float(rc["threshold"])
        for value, samples, params in rule.getter(report):
            if value is None or samples < rc.get("min_samples", 0):
                continue
            bad = value < threshold if rule.direction == "below" else value > threshold
            if not bad:
                continue
            gap = abs(value - threshold) / (abs(threshold) or 1.0)
            fmt = {
                **params,
                "pct": round(value),
                "deg": round(value, 1),
                "ms": round(late_after_stop_ms) if rule.id == "cs_late" else round(value),
            }
            out.append(
                {
                    "id": rule.id,
                    "kind": rule.kind,
                    "category": rule.category,
                    "severity": int(rc.get("severity", 1)),
                    "priority": round(rc.get("severity", 1) * (1 + min(gap, 2.0)), 3),
                    "value": value,
                    "threshold": threshold,
                    "samples": samples,
                    "params": {k: v for k, v in params.items() if v is not None},
                    "title": _format(messages.get(f"{rule.id}.title", rule.id), fmt),
                    "text": _format(messages.get(f"{rule.id}.text", ""), fmt),
                }
            )
    out.sort(key=lambda r: -r["priority"])
    top_n = int(cfg.get("top_n", 3))
    return {
        "items": out,
        "top": out[:top_n],
        "improve": [r for r in out if r["kind"] == "improve"],
        "stop": [r for r in out if r["kind"] == "stop"],
    }

