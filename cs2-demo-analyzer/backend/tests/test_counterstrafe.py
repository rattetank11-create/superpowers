import numpy as np
import pandas as pd
import pytest

from analysis.counterstrafe import (
    IN_BACK,
    IN_FORWARD,
    analyze_counterstrafe,
    classify_speed,
    first_shots_of_bursts,
    input_vectors,
)

from .conftest import A, D, strafe_ticks


def shots_at(*ticks, weapon="weapon_ak47"):
    return pd.DataFrame({"tick": list(ticks), "weapon": weapon, "round_num": 1})


def run(ticks, shots, weapons, thresholds):
    return analyze_counterstrafe(shots, ticks, weapons, thresholds["counterstrafe"], 64)


def decel(n_run=30, top=215.0, stop_ticks=6, tail=40):
    """Бег, затем линейное торможение до 0 за stop_ticks тиков, затем стоим."""
    return [top] * n_run + list(np.linspace(top, 0, stop_ticks + 1)[1:]) + [0.0] * tail


class TestBursts:
    def test_gap_splits_bursts(self):
        s = shots_at(100, 106, 112, 200, 206)
        assert first_shots_of_bursts(s, 32)["tick"].tolist() == [100, 200]

    def test_weapon_change_starts_new_burst(self):
        s = pd.DataFrame({"tick": [100, 105], "weapon": ["weapon_ak47", "weapon_deagle"]})
        assert first_shots_of_bursts(s, 32)["tick"].tolist() == [100, 105]

    def test_empty(self):
        assert first_shots_of_bursts(shots_at().iloc[:0], 32).empty


class TestClassify:
    @pytest.mark.parametrize(
        "speed,air,expected",
        [(0, False, "perfect"), (73, False, "perfect"), (100, False, "slow"), (200, False, "moving"), (0, True, "air")],
    )
    def test_categories_for_ak(self, speed, air, expected):
        assert classify_speed(speed, 215, air, 0.34, 0.55) == expected


class TestInputVectors:
    def test_forward_follows_yaw(self):
        ix, iy = input_vectors(np.array([IN_FORWARD]), np.array([0.0]))
        assert ix[0] == pytest.approx(1) and iy[0] == pytest.approx(0)

    def test_back_and_strafes(self):
        ix, iy = input_vectors(np.array([IN_BACK, A, D]), np.array([0.0, 0.0, 90.0]))
        assert (ix[0], iy[0]) == pytest.approx((-1, 0))
        assert (ix[1], iy[1]) == pytest.approx((0, 1))  # A при yaw=0 — влево, это +Y
        assert (ix[2], iy[2]) == pytest.approx((1, 0), abs=1e-9)  # D при yaw=90 — это +X


class TestAnalyze:
    def test_perfect_counter_strafe(self, weapons, thresholds):
        speeds = decel()
        buttons = [D] * 30 + [A] * 6 + [0] * 40
        ticks = strafe_ticks(speeds, buttons)
        shot = 1000 + 30 + 6 + 1  # через тик после полной остановки
        res = run(ticks, shots_at(shot), weapons, thresholds)
        rec = res["shots"][0]
        assert rec["category"] == "perfect"
        assert rec["context"] == "strafe"
        assert rec["technique"] == "counter"
        assert rec["timing"] == "good"
        assert res["perfect_pct"] == 100.0

    def test_shot_before_stop_is_early(self, weapons, thresholds):
        ticks = strafe_ticks(decel(), [D] * 30 + [A] * 6 + [0] * 40)
        res = run(ticks, shots_at(1000 + 31), weapons, thresholds)  # скорость ещё ~180
        rec = res["shots"][0]
        assert rec["category"] == "moving"
        assert rec["timing"] == "early"
        assert rec["technique"] == "counter"
        assert rec["stop_to_shot_ticks"] < 0

    def test_shooting_while_holding_key(self, weapons, thresholds):
        ticks = strafe_ticks([215.0] * 60, [D] * 60)
        rec = run(ticks, shots_at(1040), weapons, thresholds)["shots"][0]
        assert rec["category"] == "moving"
        assert rec["technique"] == "none"
        assert rec["timing"] == "early"

    def test_release_without_counter_key(self, weapons, thresholds):
        ticks = strafe_ticks(decel(stop_ticks=12), [D] * 30 + [0] * 52)
        rec = run(ticks, shots_at(1000 + 30 + 13), weapons, thresholds)["shots"][0]
        assert rec["technique"] == "release"
        assert rec["category"] == "perfect"

    def test_waiting_too_long_is_late(self, weapons, thresholds):
        ticks = strafe_ticks(decel(), [D] * 30 + [A] * 6 + [0] * 40)
        # остановились на тике 1036, выстрел через 20 тиков (всё ещё в окне 0.5 с от движения)
        rec = run(ticks, shots_at(1036 + 20), weapons, thresholds)["shots"][0]
        assert rec["timing"] == "late"
        assert rec["stop_to_shot_ticks"] > thresholds["counterstrafe"]["late_after_stop_ticks"]

    def test_stationary_shot_not_counted_as_counterstrafe(self, weapons, thresholds):
        ticks = strafe_ticks([0.0] * 80, [0] * 80)
        res = run(ticks, shots_at(1060), weapons, thresholds)
        assert res["shots"][0]["context"] == "stationary"
        assert res["strafe_shots"] == 0
        assert res["perfect_pct"] is None
        assert res["accurate_pct"] == 100.0

    def test_air_shot(self, weapons, thresholds):
        air = [False] * 50 + [True] * 30
        ticks = strafe_ticks([215.0] * 80, [0] * 80, airborne=air)
        rec = run(ticks, shots_at(1060), weapons, thresholds)["shots"][0]
        assert rec["category"] == "air"

    def test_scoped_awp_uses_scoped_speed(self, weapons, thresholds):
        # 50 ед/с: ниже 34% от 200 (68), но выше 34% от 100 (34) — в прицеле это уже неточно.
        ticks = strafe_ticks([50.0] * 80, [0] * 80, scoped=True)
        rec = run(ticks, shots_at(1060, weapon="weapon_awp"), weapons, thresholds)["shots"][0]
        assert rec["threshold"] == pytest.approx(34.0)
        assert rec["category"] != "perfect"

    def test_velocity_fallback_without_buttons(self, weapons, thresholds):
        ticks = strafe_ticks(decel(), [0] * 76)
        res = run(ticks, shots_at(1037), weapons, thresholds)
        assert res["buttons_available"] is False
        rec = res["shots"][0]
        assert rec["technique"] is None
        assert rec["brake_to_shot_ticks"] is not None
        assert rec["timing"] == "good"

    def test_knife_and_grenades_ignored(self, weapons, thresholds):
        ticks = strafe_ticks([0.0] * 80, [0] * 80)
        shots = pd.DataFrame({"tick": [1010, 1050], "weapon": ["weapon_knife", "weapon_flashbang"], "round_num": 1})
        assert run(ticks, shots, weapons, thresholds)["first_shots"] == 0

    def test_summary_by_weapon_and_worst(self, weapons, thresholds):
        ticks = strafe_ticks([215.0] * 200, [D] * 200)
        res = run(ticks, shots_at(1050, 1150), weapons, thresholds)
        assert res["by_weapon"][0]["weapon_name"] == "AK-47"
        assert res["by_weapon"][0]["moving_pct"] == 100.0
        assert len(res["worst"]) == 2
        assert {"round", "tick"} <= set(res["worst"][0])
