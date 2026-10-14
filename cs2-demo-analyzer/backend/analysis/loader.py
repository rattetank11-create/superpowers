"""Чтение демки CS2 через demoparser2 в набор pandas-таблиц.

Названия полей проверены на реальной демке (demoparser2 0.42):
  * tick-props: X, Y, Z, pitch, yaw, velocity (2D-скорость из позиций), buttons (битмаска),
    is_scoped, is_airborne, duck_amount, team_num, is_alive, approximate_spotted_by
    (список SteamID врагов, которые "видят" игрока — серверный m_bSpottedByMask).
  * события: weapon_fire, player_hurt, player_death, player_blind,
    round_freeze_end, round_end, begin_new_match.
  * velocity_X/Y/Z в SourceTV-демках пустые (NaN) — поэтому скорость берём из `velocity`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .errors import CorruptDemoError, LegacyDemoError, NoRoundsError, NotADemoError

CS2_MAGIC = b"PBDEMS2\x00"
CSGO_MAGIC = b"HL2DEMO\x00"

TICK_PROPS = [
    "X",
    "Y",
    "Z",
    "pitch",
    "yaw",
    "velocity",
    "buttons",
    "is_scoped",
    "is_airborne",
    "duck_amount",
    "team_num",
    "is_alive",
    "approximate_spotted_by",
]

ProgressFn = Callable[[int, str], None]


def check_demo_header(head: bytes) -> None:
    """Проверяет магические байты файла. Бросает ошибку, если это не CS2-демка."""
    if head.startswith(CS2_MAGIC):
        return
    if head.startswith(CSGO_MAGIC):
        raise LegacyDemoError()
    raise NotADemoError()


@dataclass
class MatchData:
    header: dict
    tickrate: int
    players: pd.DataFrame  # steamid, name, team_number
    rounds: pd.DataFrame  # round_num, start_tick, end_tick, winner
    ticks: pd.DataFrame  # tick, steamid, + TICK_PROPS (только живые игроки в раундах)
    shots: pd.DataFrame  # tick, steamid, weapon, round_num
    hurts: pd.DataFrame  # tick, attacker, victim, attacker_team, victim_team, dmg, hitgroup, weapon, round_num
    deaths: pd.DataFrame  # tick, attacker, victim, attacker_team, victim_team, headshot, weapon, round_num
    blinds: pd.DataFrame  # tick, attacker, victim, attacker_team, victim_team, duration, round_num
    extra: dict = field(default_factory=dict)

    @property
    def map_name(self) -> str:
        return str(self.header.get("map_name", ""))


def _steamid(series: pd.Series) -> pd.Series:
    """SteamID из событий приходят строками; ботов/мир (0, пусто) превращаем в NA."""
    # Не через pd.to_numeric: при пропусках он даёт float64 и теряет младшие цифры SteamID.
    def parse(v) -> int | None:
        try:
            n = int(str(v).split(".")[0])
        except (TypeError, ValueError):
            return None
        return n or None

    return pd.Series([parse(v) for v in series], index=series.index, dtype="Int64")


def assign_rounds(ticks: pd.Series, rounds: pd.DataFrame) -> pd.Series:
    """Номер раунда для каждого тика: [start_tick текущего, start_tick следующего).

    Тики до первого раунда получают NA.
    """
    if rounds.empty:
        return pd.Series(pd.NA, index=ticks.index, dtype="Int64")
    starts = rounds["start_tick"].to_numpy()
    idx = np.searchsorted(starts, ticks.to_numpy(), side="right") - 1
    nums = rounds["round_num"].to_numpy()
    result = pd.Series(np.where(idx >= 0, nums[np.clip(idx, 0, None)], -1), index=ticks.index)
    return result.where(result >= 0).astype("Int64")


def build_rounds(freeze_end: pd.DataFrame, round_end: pd.DataFrame, match_start_tick: int) -> pd.DataFrame:
    """Таблица раундов из событий round_freeze_end / round_end (без разминки)."""
    fe = freeze_end
    if "is_warmup_period" in fe:
        fe = fe[~fe["is_warmup_period"].fillna(False).astype(bool)]
    fe = fe[fe["tick"] >= match_start_tick].sort_values("tick").reset_index(drop=True)
    if fe.empty:
        return pd.DataFrame(columns=["round_num", "start_tick", "end_tick", "winner"])

    re_ = round_end[round_end["tick"] >= match_start_tick].sort_values("tick")
    rows = []
    for i, r in fe.iterrows():
        start = int(r["tick"])
        nxt = int(fe.loc[i + 1, "tick"]) if i + 1 < len(fe) else None
        ends = re_[(re_["tick"] > start) & ((re_["tick"] < nxt) if nxt else True)]
        end = int(ends["tick"].iloc[0]) if len(ends) else (nxt if nxt else start)
        winner = int(ends["winner"].iloc[0]) if len(ends) and pd.notna(ends["winner"].iloc[0]) else None
        played = r.get("total_rounds_played")
        round_num = int(played) + 1 if played is not None and pd.notna(played) else i + 1
        rows.append({"round_num": round_num, "start_tick": start, "end_tick": end, "winner": winner})
    rounds = pd.DataFrame(rows)
    # Номера раундов должны строго расти (рестарты/перезапуски могут их сбросить).
    if not rounds["round_num"].is_monotonic_increasing or rounds["round_num"].duplicated().any():
        rounds["round_num"] = np.arange(1, len(rounds) + 1)
    return rounds


def _event(parser, name: str, available: set[str], **kwargs) -> pd.DataFrame:
    if name not in available:
        return pd.DataFrame()
    df = parser.parse_event(name, **kwargs)
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)


def load_match(path: str | Path, tickrate: int = 64, progress: ProgressFn | None = None) -> MatchData:
    from demoparser2 import DemoParser  # тяжёлый импорт — только в воркере

    def report(pct: int, stage: str) -> None:
        if progress:
            progress(pct, stage)

    path = Path(path)
    with path.open("rb") as f:
        check_demo_header(f.read(16))

    report(5, "header")
    try:
        parser = DemoParser(str(path))
        header = parser.parse_header()
        available = set(parser.list_game_events())
    except Exception as exc:  # noqa: BLE001 — demoparser бросает "голые" исключения
        raise CorruptDemoError() from exc

    try:
        report(15, "events")
        team = ["team_num"]
        other = ["is_warmup_period", "total_rounds_played"]
        begin = _event(parser, "begin_new_match", available)
        match_start = int(begin["tick"].max()) if len(begin) else 0
        freeze_end = _event(parser, "round_freeze_end", available, other=other)
        round_end = _event(parser, "round_end", available, other=other)
        rounds = build_rounds(freeze_end, round_end, match_start)
        if rounds.empty:
            raise NoRoundsError()

        fire = _event(parser, "weapon_fire", available, player=team)
        hurt = _event(parser, "player_hurt", available, player=team)
        death = _event(parser, "player_death", available, player=team)
        blind = _event(parser, "player_blind", available, player=team)
        players = parser.parse_player_info()

        report(35, "ticks")
        ticks = parser.parse_ticks(TICK_PROPS)
    except NoRoundsError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CorruptDemoError() from exc

    report(60, "prepare")
    first_tick = int(rounds["start_tick"].min())
    ticks = _prepare_ticks(ticks, first_tick)

    shots = pd.DataFrame(
        {
            "tick": fire.get("tick", pd.Series(dtype=int)),
            "steamid": _steamid(fire.get("user_steamid", pd.Series(dtype=object))),
            "weapon": fire.get("weapon", pd.Series(dtype=object)),
        }
    )
    hurts = pd.DataFrame(
        {
            "tick": hurt.get("tick"),
            "attacker": _steamid(hurt.get("attacker_steamid", pd.Series(dtype=object))),
            "victim": _steamid(hurt.get("user_steamid", pd.Series(dtype=object))),
            "attacker_team": hurt.get("attacker_team_num"),
            "victim_team": hurt.get("user_team_num"),
            "dmg": pd.to_numeric(hurt.get("dmg_health"), errors="coerce").clip(upper=100),
            "hitgroup": hurt.get("hitgroup"),
            "weapon": hurt.get("weapon"),
        }
    )
    deaths = pd.DataFrame(
        {
            "tick": death.get("tick"),
            "attacker": _steamid(death.get("attacker_steamid", pd.Series(dtype=object))),
            "victim": _steamid(death.get("user_steamid", pd.Series(dtype=object))),
            "attacker_team": death.get("attacker_team_num"),
            "victim_team": death.get("user_team_num"),
            "headshot": death.get("headshot", pd.Series(dtype=bool)).fillna(False).astype(bool),
            "weapon": death.get("weapon"),
        }
    )
    blinds = pd.DataFrame(
        {
            "tick": blind.get("tick"),
            "attacker": _steamid(blind.get("attacker_steamid", pd.Series(dtype=object))),
            "victim": _steamid(blind.get("user_steamid", pd.Series(dtype=object))),
            "attacker_team": blind.get("attacker_team_num"),
            "victim_team": blind.get("user_team_num"),
            "duration": blind.get("blind_duration"),
        }
    )

    tables = []
    for df in (shots, hurts, deaths, blinds):
        df = df.dropna(subset=["tick"]).copy()
        df["tick"] = df["tick"].astype(int)
        df["round_num"] = assign_rounds(df["tick"], rounds)
        tables.append(df[df["round_num"].notna()].sort_values("tick").reset_index(drop=True))
    shots, hurts, deaths, blinds = tables
    ticks["round_num"] = assign_rounds(ticks["tick"], rounds)

    players["steamid"] = _steamid(players["steamid"])
    players = players.dropna(subset=["steamid"]).drop_duplicates("steamid").reset_index(drop=True)

    report(70, "parsed")
    return MatchData(
        header=dict(header),
        tickrate=tickrate,
        players=players[["steamid", "name", "team_number"]],
        rounds=rounds,
        ticks=ticks,
        shots=shots,
        hurts=hurts,
        deaths=deaths,
        blinds=blinds,
    )


def _prepare_ticks(ticks: pd.DataFrame, first_tick: int) -> pd.DataFrame:
    ticks = ticks[(ticks["tick"] >= first_tick - 64)]
    ticks = ticks[ticks["is_alive"].fillna(False).astype(bool)].copy()
    ticks["steamid"] = ticks["steamid"].astype("int64")
    for col in ("X", "Y", "Z", "pitch", "yaw", "velocity", "duck_amount"):
        ticks[col] = ticks[col].astype("float32")
    ticks["buttons"] = ticks["buttons"].fillna(0).astype("int64")
    for col in ("is_scoped", "is_airborne"):
        ticks[col] = ticks[col].fillna(False).astype(bool)
    ticks["team_num"] = ticks["team_num"].fillna(0).astype("int8")
    ticks = ticks.drop(columns=["is_alive", "name"], errors="ignore")
    return ticks.sort_values(["steamid", "tick"]).reset_index(drop=True)
