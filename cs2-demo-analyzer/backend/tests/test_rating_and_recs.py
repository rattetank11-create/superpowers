import pytest

from analysis.rating import estimate_elo, extract_features, level_for_elo
from analysis.recommendations import evaluate_rules
from analysis.settings import load_elo_model, load_faceit_levels


@pytest.fixture
def levels():
    return load_faceit_levels()


@pytest.mark.parametrize(
    "elo,level",
    [(100, 1), (500, 1), (501, 2), (900, 3), (1050, 4), (1200, 5), (1350, 6), (1530, 7), (1750, 8), (2000, 9), (2001, 10), (4000, 10)],
)
def test_level_boundaries(elo, level, levels):
    assert level_for_elo(elo, levels) == level


def report(**over):
    base = {
        "overview": {"hs_pct": 40.0, "kpr": 0.68, "adr": 75.0, "kills": 15},
        "counterstrafe": {
            "perfect_pct": 55.0, "strafe_shots": 40, "first_shots": 50,
            "categories": {"perfect": 30, "slow": 5, "moving": 15, "air": 0},
            "timing": {"good": 20, "early": 10, "late": 10}, "timing_pct": {"good": 50.0, "early": 25.0, "late": 25.0},
            "technique": {"counter": 30, "release": 10}, "by_weapon": [],
        },
        "accuracy": {"first_bullet_accuracy_pct": 30.0, "first_bullets": 50},
        "duels": {"winrate": 50.0, "decided": 20, "total": 25, "opening": {"winrate": 50.0, "count": 6, "wins": 3},
                  "median_ttk_ms": 450, "ttk_samples": 10, "shot_first_pct": 50.0,
                  "peek_without_flash": {"winrate": 50.0, "count": 6, "wins": 3}},
        "crosshair": {"median_angle": 8.0, "median_pitch_err": 0.5, "front_samples": 30},
        "trades": {"traded_pct": 30.0, "deaths": 15, "trade_kill_pct": 20.0, "kills": 15},
    }
    for path, value in over.items():
        section, key = path.split("__")
        base[section][key] = value
    return base


class TestElo:
    def test_average_player_near_intercept(self, levels):
        model = load_elo_model()
        res = estimate_elo(extract_features(report()), model, levels, rounds_played=24)
        assert res["elo"] == pytest.approx(model["intercept"], abs=1)
        assert res["elo_low"] < res["elo"] < res["elo_high"]
        assert res["level_low"] <= res["level"] <= res["level_high"]

    def test_better_metrics_raise_elo(self, levels):
        model = load_elo_model()
        avg = estimate_elo(extract_features(report()), model, levels, 24)["elo"]
        good = estimate_elo(extract_features(report(duels__winrate=65.0, crosshair__median_angle=4.0)), model, levels, 24)["elo"]
        assert good > avg

    def test_missing_features_and_short_demo_widen_range(self, levels):
        model = load_elo_model()
        full = estimate_elo(extract_features(report()), model, levels, 24)
        partial = estimate_elo({"kpr": 0.68}, model, levels, 8)
        assert (partial["elo_high"] - partial["elo_low"]) > (full["elo_high"] - full["elo_low"])
        assert "duel_winrate" in partial["missing_features"]

    def test_never_below_floor(self, levels):
        model = load_elo_model()
        res = estimate_elo(extract_features(report(overview__kpr=0.0, overview__adr=0.0, duels__winrate=0.0)), model, levels, 24)
        assert res["elo_low"] >= 100


class TestRecommendations:
    def test_average_report_has_no_critical_counterstrafe_rule(self, thresholds):
        recs = evaluate_rules(report(), thresholds["recommendations"])
        assert "cs_perfect_low" in [r["id"] for r in recs["items"]]  # 55 < 60
        assert "duel_winrate_low" not in [r["id"] for r in recs["items"]]

    def test_moving_weapon_rule_mentions_weapon(self, thresholds):
        r = report()
        r["counterstrafe"]["by_weapon"] = [{"weapon_name": "AK-47", "moving_pct": 62.0, "first_shots": 30}]
        items = {i["id"]: i for i in evaluate_rules(r, thresholds["recommendations"])["items"]}
        assert items["cs_moving_weapon"]["kind"] == "stop"
        assert "62%" in items["cs_moving_weapon"]["text"] and "AK-47" in items["cs_moving_weapon"]["text"]

    def test_min_samples_suppresses_rule(self, thresholds):
        r = report(duels__winrate=10.0, duels__decided=2)
        assert "duel_winrate_low" not in [i["id"] for i in evaluate_rules(r, thresholds["recommendations"])["items"]]

    def test_peek_without_flash(self, thresholds):
        r = report()
        r["duels"]["peek_without_flash"] = {"winrate": 20.0, "count": 10, "wins": 2}
        items = {i["id"]: i for i in evaluate_rules(r, thresholds["recommendations"])["items"]}
        assert "флешки" in items["peek_no_flash"]["text"]

    def test_top_sorted_by_priority(self, thresholds):
        r = report(crosshair__median_angle=20.0, overview__hs_pct=34.0)
        recs = evaluate_rules(r, thresholds["recommendations"])
        assert len(recs["top"]) <= thresholds["recommendations"]["top_n"]
        prios = [i["priority"] for i in recs["items"]]
        assert prios == sorted(prios, reverse=True)
        assert recs["top"][0]["id"] == "crosshair_angle_high"
