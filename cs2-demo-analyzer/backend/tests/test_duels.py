import numpy as np
import pandas as pd
import pytest

from analysis.duels import (
    basic_stats,
    build_duels,
    enrich_duels,
    shot_accuracy,
    summarize_duels,
)
from analysis.geometry import TickIndex
from analysis.trades import analyze_trades

ME, ENEMY, ENEMY2, MATE = 1, 2, 3, 4
T, CT = 2, 3
TEAM = {ME: T, MATE: T, ENEMY: CT, ENEMY2: CT}


def hurt(tick, attacker, victim, dmg=27, hitgroup="chest", weapon="ak47", rnd=1):
    return {
        "tick": tick, "attacker": attacker, "victim": victim, "attacker_team": TEAM[attacker],
        "victim_team": TEAM[victim], "dmg": dmg, "hitgroup": hitgroup, "weapon": weapon, "round_num": rnd,
    }


def death(tick, attacker, victim, headshot=False, rnd=1):
    return {
        "tick": tick, "attacker": attacker, "victim": victim, "attacker_team": TEAM[attacker],
        "victim_team": TEAM[victim], "headshot": headshot, "weapon": "ak47", "round_num": rnd,
    }


def frame(rows, kind):
    cols = {
        "hurt": ["tick", "attacker", "victim", "attacker_team", "victim_team", "dmg", "hitgroup", "weapon", "round_num"],
        "death": ["tick", "attacker", "victim", "attacker_team", "victim_team", "headshot", "weapon", "round_num"],
    }[kind]
    return pd.DataFrame(rows, columns=cols)


def standing_ticks(players, start=900, end=1400, speed=0.0):
    """ME в (0,0), смотрит на +X; враги — на +X в 1000 юнитах, смотрят на ME."""
    rows = []
    pos = {ME: (0, 0, 0.0), MATE: (0, 100, 0.0), ENEMY: (1000, 0, 180.0), ENEMY2: (1000, 50, 180.0)}
    for sid in players:
        x, y, yaw = pos[sid]
        for t in range(start, end):
            rows.append({"tick": t, "steamid": sid, "X": x, "Y": y, "Z": 0.0, "pitch": 0.0, "yaw": yaw,
                         "duck_amount": 0.0, "velocity": speed})
    return pd.DataFrame(rows)


class TestBuildDuels:
    def test_win_loss_and_gap_split(self):
        hurts = frame(
            [
                hurt(1000, ME, ENEMY), hurt(1010, ENEMY, ME), hurt(1020, ME, ENEMY, dmg=100, hitgroup="head"),
                hurt(2000, ENEMY2, ME, dmg=100),  # другая дуэль
                hurt(1015, MATE, ME, dmg=10),  # урон по своим не считается
            ],
            "hurt",
        )
        deaths = frame([death(1020, ME, ENEMY, headshot=True), death(2000, ENEMY2, ME)], "death")
        duels = build_duels(hurts, deaths, ME, gap_ticks=192)
        assert [d["result"] for d in duels] == ["win", "loss"]
        assert duels[0]["dmg_dealt"] == 127 and duels[0]["dmg_taken"] == 27
        assert duels[0]["damaged_first"] is True
        assert duels[0]["headshot"] is True

    def test_long_pause_starts_new_duel(self):
        hurts = frame([hurt(1000, ME, ENEMY), hurt(1500, ME, ENEMY)], "hurt")
        duels = build_duels(hurts, frame([], "death"), ME, gap_ticks=192)
        assert len(duels) == 2 and all(d["result"] == "none" for d in duels)


class TestEnrich:
    @pytest.fixture
    def cfg(self, thresholds):
        return thresholds["duels"]

    def test_shot_first_ttk_and_opening(self, cfg):
        hurts = frame([hurt(1000, ME, ENEMY, dmg=100)], "hurt")
        deaths = frame([death(1000, ME, ENEMY)], "death")
        shots = pd.DataFrame({"tick": [990, 995, 1000], "steamid": [ME, ENEMY, ME], "weapon": "weapon_ak47"})
        blinds = pd.DataFrame(columns=["tick", "attacker", "victim", "attacker_team", "victim_team", "duration"])
        index = TickIndex(standing_ticks([ME, ENEMY]))
        duels = enrich_duels(build_duels(hurts, deaths, ME, 192), ME, shots, blinds, deaths, index, cfg, 64)
        d = duels[0]
        assert d["shot_first"] is True
        assert d["ttk_ms"] == round(10 * 1000 / 64)
        assert d["opening"] is True
        assert d["distance"] == 1000

    def test_shot_away_from_enemy_is_not_aimed(self, cfg):
        hurts = frame([hurt(1000, ENEMY, ME, dmg=100)], "hurt")
        deaths = frame([death(1000, ENEMY, ME)], "death")
        ticks = standing_ticks([ME, ENEMY])
        ticks.loc[ticks["steamid"] == ME, "yaw"] = 90.0  # ME смотрит в сторону
        shots = pd.DataFrame({"tick": [990, 995], "steamid": [ME, ENEMY], "weapon": "weapon_ak47"})
        blinds = pd.DataFrame(columns=["tick", "attacker", "victim", "attacker_team", "victim_team", "duration"])
        d = enrich_duels(build_duels(hurts, deaths, ME, 192), ME, shots, blinds, deaths, TickIndex(ticks), cfg, 64)[0]
        assert d["shot_first"] is False
        assert d["result"] == "loss"

    def test_flash_support_and_peek(self, cfg):
        hurts = frame([hurt(1000, ME, ENEMY, dmg=100)], "hurt")
        deaths = frame([death(1000, ME, ENEMY)], "death")
        ticks = standing_ticks([ME, ENEMY])
        ticks.loc[ticks["steamid"] == ME, "velocity"] = 200.0
        blinds = pd.DataFrame(
            [{"tick": 950, "attacker": MATE, "victim": ENEMY, "attacker_team": T, "victim_team": CT, "duration": 2.5}]
        )
        shots = pd.DataFrame({"tick": [1000], "steamid": [ME], "weapon": "weapon_ak47"})
        d = enrich_duels(build_duels(hurts, deaths, ME, 192), ME, shots, blinds, deaths, TickIndex(ticks), cfg, 64)[0]
        assert d["flash_support"] is True
        assert d["peeked"] is True


class TestSummary:
    def test_winrates_and_worst(self):
        duels = [
            {"round": 1, "opponent": ENEMY, "start_tick": 10, "end_tick": 10, "result": "win", "kill_tick": 10,
             "headshot": True, "damaged_first": True, "dmg_dealt": 100, "dmg_taken": 0, "my_team": T,
             "shot_first": True, "ttk_ms": 200, "flash_support": False, "got_flashed": False, "peeked": True,
             "distance": 500, "opening": True},
            {"round": 2, "opponent": ENEMY, "start_tick": 20, "end_tick": 20, "result": "loss", "kill_tick": 20,
             "headshot": None, "damaged_first": False, "dmg_dealt": 0, "dmg_taken": 100, "my_team": T,
             "shot_first": True, "ttk_ms": None, "flash_support": False, "got_flashed": False, "peeked": True,
             "distance": 600, "opening": True},
            {"round": 2, "opponent": ENEMY2, "start_tick": 30, "end_tick": 30, "result": "none", "kill_tick": None,
             "headshot": None, "damaged_first": True, "dmg_dealt": 20, "dmg_taken": 0, "my_team": T,
             "shot_first": None, "ttk_ms": None, "flash_support": False, "got_flashed": False, "peeked": False,
             "distance": None, "opening": False},
        ]
        s = summarize_duels(duels, {ENEMY: "enemy"}, 64)
        assert s["winrate"] == 50.0
        assert s["opening"] == {"count": 2, "wins": 1, "winrate": 50.0}
        assert s["peek_without_flash"]["count"] == 2
        assert s["median_ttk_ms"] == 200
        assert s["worst"][0]["round"] == 2
        assert s["by_round"] == [{"round": 1, "wins": 1, "losses": 0, "none": 0}, {"round": 2, "wins": 0, "losses": 1, "none": 1}]
        assert isinstance(s["duels"][0]["kill_tick"], int)

    def test_empty(self):
        assert summarize_duels([], {}, 64)["winrate"] is None


class TestAccuracyAndStats:
    def test_first_bullet_and_overall_accuracy(self, weapons):
        shots = pd.DataFrame({"tick": [100, 106, 112, 300], "steamid": ME, "weapon": "weapon_ak47"})
        hurts = frame([hurt(100, ME, ENEMY), hurt(112, ME, ENEMY, hitgroup="head")], "hurt")
        acc = shot_accuracy(shots, hurts, ME, weapons, burst_gap_ticks=32)
        assert acc["shots"] == 4 and acc["hits"] == 2
        assert acc["first_bullets"] == 2 and acc["first_bullet_hits"] == 1
        assert acc["first_bullet_accuracy_pct"] == 50.0
        assert acc["head_hit_pct"] == 50.0

    def test_basic_stats(self):
        deaths = frame([death(10, ME, ENEMY, headshot=True), death(20, ME, ENEMY2), death(30, ENEMY, ME)], "death")
        hurts = frame([hurt(10, ME, ENEMY, dmg=100), hurt(20, ME, ENEMY2, dmg=100)], "hurt")
        st = basic_stats(deaths, hurts, ME, rounds_played=4)
        assert st["kills"] == 2 and st["deaths"] == 1 and st["hs_pct"] == 50.0
        assert st["adr"] == 50.0 and st["kpr"] == 0.5


class TestTrades:
    def test_traded_death_and_trade_kill(self):
        deaths = frame(
            [
                death(100, ENEMY, ME),  # я умер
                death(200, MATE, ENEMY),  # тиммейт разменял через 100 тиков
                death(1000, ENEMY2, MATE),  # тиммейт умер
                death(1100, ME, ENEMY2),  # я разменял
            ],
            "death",
        )
        res = analyze_trades(deaths, ME, window_ticks=320)
        assert res["traded_deaths"] == 1 and res["traded_pct"] == 100.0
        assert res["trade_kills"] == 1 and res["trade_kill_pct"] == 100.0

    def test_outside_window_not_traded(self):
        deaths = frame([death(100, ENEMY, ME), death(1000, MATE, ENEMY)], "death")
        assert analyze_trades(deaths, ME, window_ticks=320)["traded_deaths"] == 0


def test_tick_index_lookup():
    idx = TickIndex(standing_ticks([ME], start=0, end=10, speed=100.0))
    st = idx.get(ME, 5)
    assert st is not None and st.tick == 5
    assert idx.get(ME, 50) is None
    assert idx.mean_speed(ME, 0, 9) == pytest.approx(100.0)
    assert np.allclose(st.eye(), [0, 0, 64])
