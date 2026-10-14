"""Калибровка модели ELO по демкам с известным ELO игроков.

Вход — CSV с колонками: demo_path,steamid,elo
(одна строка на игрока; одну демку можно указывать несколько раз для разных игроков).

    python -m scripts.calibrate_elo dataset.csv                 # обучить и записать веса
    python -m scripts.calibrate_elo dataset.csv --dry-run       # только показать метрики
    python -m scripts.calibrate_elo dataset.csv --alpha 5 --out analysis/config/elo_model.json

Признаки извлекаются той же функцией, что и на сайте (analysis.rating.extract_features),
поэтому модель всегда согласована с отчётами. Признаки кэшируются в <csv>.features.json,
чтобы повторное обучение не парсило демки заново.

Модель — ridge-регрессия на стандартизованных признаках (только numpy).
residual_std = RMSE leave-one-out кросс-валидации: из него строится диапазон на сайте.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.pipeline import analyze_demo  # noqa: E402
from analysis.rating import FEATURES, extract_features  # noqa: E402
from analysis.settings import CONFIG_DIR  # noqa: E402


def load_dataset(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8") as f:
        rows = [
            {"demo_path": r["demo_path"].strip(), "steamid": r["steamid"].strip(), "elo": float(r["elo"])}
            for r in csv.DictReader(f)
        ]
    if not rows:
        raise SystemExit("CSV пустой")
    return rows


def collect_features(rows: list[dict], cache_path: Path) -> list[dict]:
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    by_demo: dict[str, list[dict]] = {}
    for r in rows:
        by_demo.setdefault(r["demo_path"], []).append(r)

    samples = []
    for demo, items in by_demo.items():
        missing = [r for r in items if f"{demo}|{r['steamid']}" not in cache]
        if missing:
            print(f"парсинг {demo} ...", file=sys.stderr)
            result = analyze_demo(demo)
            for r in items:
                rep = result["reports"].get(r["steamid"])
                if rep is None:
                    print(f"  ! игрок {r['steamid']} не найден в {demo}", file=sys.stderr)
                    continue
                cache[f"{demo}|{r['steamid']}"] = extract_features(rep)
            cache_path.write_text(json.dumps(cache, indent=1))
        for r in items:
            feats = cache.get(f"{demo}|{r['steamid']}")
            if feats is not None:
                samples.append({"features": feats, "elo": r["elo"]})
    return samples


def fit_ridge(X: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, float, float]:
    """Ridge на стандартизованных X (свободный член не штрафуется).

    Возвращает (веса, intercept, LOO RMSE).
    """
    n, k = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    penalty = alpha * np.eye(k + 1)
    penalty[0, 0] = 0.0
    A = Xb.T @ Xb + penalty
    beta = np.linalg.solve(A, Xb.T @ y)
    # Leave-one-out для линейного сглаживателя: e_i / (1 - h_ii)
    H = Xb @ np.linalg.solve(A, Xb.T)
    resid = y - Xb @ beta
    loo = resid / np.clip(1 - np.diag(H), 1e-6, None)
    return beta[1:], float(beta[0]), float(np.sqrt(np.mean(loo**2)))


def build_matrix(samples: list[dict], prior: dict) -> tuple[np.ndarray, np.ndarray, dict]:
    raw = np.array(
        [[np.nan if s["features"].get(f) is None else float(s["features"][f]) for f in FEATURES] for s in samples]
    )
    y = np.array([s["elo"] for s in samples], dtype=float)
    stats = {}
    for j, f in enumerate(FEATURES):
        col = raw[:, j]
        mean = float(np.nanmean(col)) if np.isfinite(col).any() else prior["features"][f]["mean"]
        std = float(np.nanstd(col)) if np.isfinite(col).sum() > 1 else 0.0
        if std <= 1e-9:
            std = prior["features"][f]["std"]
        stats[f] = {"mean": round(mean, 4), "std": round(std, 4)}
        col = np.where(np.isfinite(col), col, mean)  # пропуск = среднее (вклад 0, как на сайте)
        raw[:, j] = np.clip((col - mean) / std, -3, 3)
    return raw, y, stats


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--alpha", type=float, default=2.0, help="сила L2-регуляризации")
    ap.add_argument("--out", type=Path, default=CONFIG_DIR / "elo_model.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    prior = json.loads((CONFIG_DIR / "elo_model.json").read_text(encoding="utf-8"))
    samples = collect_features(load_dataset(args.csv), args.csv.with_suffix(".features.json"))
    if len(samples) < len(FEATURES) + 5:
        print(f"Внимание: всего {len(samples)} примеров — модель будет ненадёжной.", file=sys.stderr)
    X, y, stats = build_matrix(samples, prior)
    weights, intercept, loo_rmse = fit_ridge(X, y, args.alpha)

    model = {
        "version": f"calibrated-{date.today().isoformat()}",
        "calibrated": True,
        "description": f"Ridge (alpha={args.alpha}) на {len(samples)} примерах. LOO RMSE = {loo_rmse:.0f} ELO.",
        "intercept": round(intercept, 2),
        "residual_std": round(max(loo_rmse, 50.0), 1),
        "trained_on": len(samples),
        "features": {
            f: {"mean": stats[f]["mean"], "std": stats[f]["std"], "weight": round(float(w), 3)}
            for f, w in zip(FEATURES, weights)
        },
    }
    print(json.dumps(model, indent=2, ensure_ascii=False))
    if not args.dry_run:
        args.out.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"сохранено в {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
