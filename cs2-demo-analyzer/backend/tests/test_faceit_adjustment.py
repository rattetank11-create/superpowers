import pytest

from analysis.rating import adjust_faceit_elo
from analysis.settings import load_faceit_levels


@pytest.fixture
def cfg(thresholds):
    return thresholds["faceit_adjustment"]


@pytest.fixture
def levels():
    return load_faceit_levels()


def adjust(cfg, levels, current=1500, perf=0.0, kills=15, adr=80.0):
    match_elo = current + perf * cfg["scale"]
    return adjust_faceit_elo(current, match_elo, kills, adr, cfg, levels)


class TestTiers:
    def test_normal_game_adds_100_to_300(self, cfg, levels):
        r = adjust(cfg, levels, perf=0.5)
        assert r["tier"] == "normal"
        assert 100 <= r["delta"] <= 300
        assert (r["tier_delta_min"], r["tier_delta_max"]) == (100, 300)

    def test_bad_game_subtracts_100_to_300(self, cfg, levels):
        r = adjust(cfg, levels, perf=-0.8)
        assert r["tier"] == "bad"
        assert -300 <= r["delta"] <= -100
        assert (r["tier_delta_min"], r["tier_delta_max"]) == (-300, -100)

    def test_very_bad_game_subtracts_300_to_700(self, cfg, levels):
        r = adjust(cfg, levels, perf=-2.0)
        assert r["tier"] == "very_bad"
        assert -700 <= r["delta"] <= -300
        assert r["reasons"] == ["perf"]

    def test_worse_play_means_bigger_penalty_inside_tier(self, cfg, levels):
        assert adjust(cfg, levels, perf=-1.4)["delta"] < adjust(cfg, levels, perf=-0.3)["delta"]


class TestBoundaries:
    def test_bad_starts_at_minus_100(self, cfg, levels):
        r = adjust(cfg, levels, perf=-0.2500001)
        assert r["tier"] == "bad" and r["delta"] == -100

    def test_normal_starts_at_plus_100(self, cfg, levels):
        r = adjust(cfg, levels, perf=-0.25)
        assert r["tier"] == "normal" and r["delta"] == 100

    def test_very_bad_boundary(self, cfg, levels):
        assert adjust(cfg, levels, perf=-1.5)["tier"] == "bad"
        assert adjust(cfg, levels, perf=-1.5)["delta"] == -300
        assert adjust(cfg, levels, perf=-1.51)["tier"] == "very_bad"

    def test_clamped_beyond_edges(self, cfg, levels):
        assert adjust(cfg, levels, perf=5.0)["delta"] == 300
        assert adjust(cfg, levels, perf=-10.0)["delta"] == -700


class TestZeroGame:
    def test_zero_kills_is_very_bad_even_with_good_perf(self, cfg, levels):
        r = adjust(cfg, levels, perf=1.0, kills=0)
        assert r["tier"] == "very_bad"
        assert "zero_kills" in r["reasons"]
        assert -700 <= r["delta"] <= -300

    def test_low_adr_is_very_bad(self, cfg, levels):
        r = adjust(cfg, levels, perf=0.0, adr=12.0)
        assert r["tier"] == "very_bad" and "low_adr" in r["reasons"]


class TestFloorAndLevels:
    def test_never_below_100(self, cfg, levels):
        r = adjust(cfg, levels, current=250, perf=-3.0)
        assert r["new_elo"] == 100
        assert r["delta"] == -150  # реально применённая поправка
        assert r["new_level"] == 1

    def test_levels_follow_faceit_table(self, cfg, levels):
        r = adjust(cfg, levels, current=1500, perf=-0.8)
        assert r["current_level"] == 7
        assert r["new_level"] == level_after(r["new_elo"])


def level_after(elo):
    from analysis.rating import level_for_elo

    return level_for_elo(elo, load_faceit_levels())
