from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.counterstrafe import IN_MOVELEFT, IN_MOVERIGHT  # noqa: E402
from analysis.settings import load_thresholds, load_weapons  # noqa: E402

TICKRATE = 64


@pytest.fixture
def thresholds():
    return load_thresholds()


@pytest.fixture
def weapons():
    return load_weapons()


def strafe_ticks(
    speeds: list[float],
    buttons: list[int],
    start_tick: int = 1000,
    yaw: float = 90.0,
    airborne: list[bool] | None = None,
    scoped: bool = False,
    steamid: int = 1,
) -> pd.DataFrame:
    """Тики игрока, который движется вдоль +X со скоростями `speeds` (юнитов/с).

    При yaw=90 (смотрит в +Y) клавиша D (MOVERIGHT) толкает в +X, A (MOVELEFT) — в -X.
    """
    n = len(speeds)
    x = np.cumsum(np.asarray(speeds, dtype=float) / TICKRATE)
    return pd.DataFrame(
        {
            "tick": np.arange(start_tick, start_tick + n),
            "steamid": steamid,
            "X": x,
            "Y": np.zeros(n),
            "Z": np.zeros(n),
            "pitch": np.zeros(n),
            "yaw": np.full(n, yaw),
            "velocity": np.asarray(speeds, dtype=float),
            "buttons": np.asarray(buttons, dtype=np.int64),
            "is_airborne": airborne if airborne is not None else [False] * n,
            "is_scoped": [scoped] * n,
            "duck_amount": np.zeros(n),
            "team_num": 2,
            "round_num": 1,
        }
    )


D = IN_MOVERIGHT
A = IN_MOVELEFT


@pytest.fixture
def real_demo_path():
    """Путь к реальной демке для интеграционных тестов (CS2_TEST_DEMO)."""
    path = os.environ.get("CS2_TEST_DEMO")
    if not path or not Path(path).exists():
        pytest.skip("CS2_TEST_DEMO не задан — интеграционный тест на реальной демке пропущен")
    return path
