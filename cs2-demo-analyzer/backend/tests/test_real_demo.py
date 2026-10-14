"""Интеграционный тест на реальной демке: CS2_TEST_DEMO=/path/to/demo.dem pytest."""

import json

from analysis.pipeline import analyze_demo


def test_full_pipeline_on_real_demo(real_demo_path):
    stages = []
    res = analyze_demo(real_demo_path, progress=lambda p, s: stages.append(p))
    assert stages == sorted(stages)
    assert res["match"]["rounds"] > 0
    assert len(res["players"]) == 10
    for p in res["players"]:
        r = res["reports"][p["steamid"]]
        json.dumps(r)  # отчёт сериализуется
        assert r["counterstrafe"]["first_shots"] > 0
        assert r["duels"]["total"] > 0
        assert 0 <= r["accuracy"]["first_bullet_accuracy_pct"] <= 100
        assert r["rating"]["elo_low"] <= r["rating"]["elo"] <= r["rating"]["elo_high"]
        assert 1 <= r["rating"]["level"] <= 10
    total_kills = sum(p["kills"] for p in res["players"])
    assert total_kills > 0
