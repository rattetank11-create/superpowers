import json

import numpy as np

from analysis.rating import FEATURES, estimate_elo
from analysis.settings import load_elo_model, load_faceit_levels
from scripts.calibrate_elo import build_matrix, fit_ridge


def test_ridge_recovers_linear_relation():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    y = 1200 + 100 * X[:, 0] - 50 * X[:, 1] + rng.normal(scale=10, size=200)
    w, b, rmse = fit_ridge(X, y, alpha=0.1)
    assert abs(b - 1200) < 5
    assert abs(w[0] - 100) < 5 and abs(w[1] + 50) < 5 and abs(w[2]) < 5
    assert rmse < 15


def test_calibrated_model_is_usable_by_rating(tmp_path):
    rng = np.random.default_rng(1)
    prior = load_elo_model()
    samples = []
    for _ in range(80):
        skill = rng.normal()
        feats = {f: prior["features"][f]["mean"] + prior["features"][f]["std"] * skill * np.sign(prior["features"][f]["weight"]) for f in FEATURES}
        samples.append({"features": feats, "elo": 1300 + 400 * skill})
    samples[0]["features"]["median_ttk_ms"] = None  # пропуски допустимы
    X, y, stats = build_matrix(samples, prior)
    w, b, rmse = fit_ridge(X, y, alpha=1.0)
    model = {
        "version": "t", "calibrated": True, "intercept": b, "residual_std": max(rmse, 50),
        "features": {f: {**stats[f], "weight": float(wi)} for f, wi in zip(FEATURES, w)},
    }
    json.dumps(model)
    res = estimate_elo({f: stats[f]["mean"] for f in FEATURES}, model, load_faceit_levels(), 24)
    assert abs(res["elo"] - 1300) < 120
    assert res["calibrated"] is True
