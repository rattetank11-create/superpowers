"""Трейды: разменяли ли игрока и разменивал ли он тиммейтов.

  * Смерть игрока "разменяна", если его убийцу убил тиммейт игрока
    в течение trade_window_seconds после смерти.
  * Убийство игрока — "размен", если жертва за trade_window_seconds до этого
    убила тиммейта игрока.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .util import pct


def analyze_trades(deaths: pd.DataFrame, steamid: int, window_ticks: int) -> dict[str, Any]:
    d = deaths.dropna(subset=["attacker", "victim"])
    d = d[d["attacker_team"] != d["victim_team"]].sort_values("tick")

    my_deaths = d[d["victim"] == steamid]
    traded = 0
    for row in my_deaths.itertuples():
        revenge = d[
            (d["victim"] == row.attacker)
            & (d["tick"] > row.tick)
            & (d["tick"] <= row.tick + window_ticks)
            & (d["attacker_team"] == row.victim_team)
        ]
        traded += int(len(revenge) > 0)

    my_kills = d[d["attacker"] == steamid]
    trade_kills = 0
    for row in my_kills.itertuples():
        avenged = d[
            (d["attacker"] == row.victim)
            & (d["tick"] < row.tick)
            & (d["tick"] >= row.tick - window_ticks)
            & (d["victim_team"] == row.attacker_team)
            & (d["victim"] != steamid)
        ]
        trade_kills += int(len(avenged) > 0)

    return {
        "deaths": int(len(my_deaths)),
        "traded_deaths": traded,
        "traded_pct": pct(traded, len(my_deaths)),
        "kills": int(len(my_kills)),
        "trade_kills": trade_kills,
        "trade_kill_pct": pct(trade_kills, len(my_kills)),
    }
