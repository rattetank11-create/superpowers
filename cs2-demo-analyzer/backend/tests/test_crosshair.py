import numpy as np
import pandas as pd
import pytest

from analysis.crosshair import analyze_crosshair, spot_events, spotted_pairs
from analysis.geometry import TickIndex, aim_error

ME, ENEMY = 1, 2


class TestAimError:
    def test_direct_aim_is_zero(self):
        angle, yaw_err, pitch_err, dist = aim_error(np.array([0, 0, 64]), 0.0, 0.0, np.array([1000, 0, 64]))
        assert angle == pytest.approx(0, abs=1e-6) and dist == pytest.approx(1000)

    def test_yaw_offset(self):
        angle, yaw_err, pitch_err, _ = aim_error(np.array([0, 0, 0]), 0.0, 10.0, np.array([1000, 0, 0]))
        assert angle == pytest.approx(10) and yaw_err == pytest.approx(10) and pitch_err == pytest.approx(0)

    def test_pitch_positive_means_aiming_below(self):
        _, _, pitch_err, _ = aim_error(np.array([0, 0, 0]), 5.0, 0.0, np.array([1000, 0, 0]))
        assert pitch_err == pytest.approx(5)

    def test_yaw_wraps_around(self):
        _, yaw_err, _, _ = aim_error(np.array([0, 0, 0]), 0.0, 179.0, np.array([-1000, -10, 0]))
        assert abs(yaw_err) < 2


def ticks_with_spotting(spotted_ticks, me_yaw=0.0, me_pitch=0.0, n=600):
    rows = []
    for t in range(n):
        rows.append({"tick": t, "steamid": ME, "X": 0.0, "Y": 0.0, "Z": 0.0, "pitch": me_pitch, "yaw": me_yaw,
                     "duck_amount": 0.0, "velocity": 0.0, "round_num": 1, "approximate_spotted_by": []})
        rows.append({"tick": t, "steamid": ENEMY, "X": 1000.0, "Y": 0.0, "Z": 0.0, "pitch": 0.0, "yaw": 180.0,
                     "duck_amount": 0.0, "velocity": 0.0, "round_num": 1,
                     "approximate_spotted_by": [ME] if t in spotted_ticks else []})
    return pd.DataFrame(rows)


def test_spot_events_cooldown():
    seen = set(range(100, 120)) | set(range(150, 160)) | set(range(400, 410))
    pairs = spotted_pairs(ticks_with_spotting(seen))
    ev = spot_events(pairs, ME, cooldown_ticks=128)
    assert ev["tick"].tolist() == [100, 400]  # 150 — слишком скоро после 119
    assert ev["enemy"].tolist() == [ENEMY, ENEMY]


def test_analyze_crosshair(thresholds):
    ticks = ticks_with_spotting(set(range(100, 110)), me_yaw=6.0, me_pitch=3.0)
    res = analyze_crosshair(spotted_pairs(ticks), ME, TickIndex(ticks), thresholds["crosshair"], 64, {ENEMY: "bot"})
    assert res["approximate"] is True
    assert res["samples"] == 1
    assert res["median_angle"] == pytest.approx(6.7, abs=0.2)
    assert res["median_pitch_err"] == pytest.approx(3.0, abs=0.1)
    assert res["worst"][0]["enemy"] == "bot"


def test_no_spotting():
    ticks = ticks_with_spotting(set())
    res = analyze_crosshair(spotted_pairs(ticks), ME, TickIndex(ticks), {"respot_cooldown_seconds": 2,
                            "eye_height_standing": 64, "eye_height_crouch_delta": 18, "max_distance": 3500,
                            "good_angle_deg": 5}, 64)
    assert res["samples"] == 0 and res["median_angle"] is None
