"""Геометрия: направление взгляда, углы до головы цели, быстрый доступ к тикам игрока.

Соглашения Source 2 (проверены на хедшот-убийствах в реальной демке — ошибка < 1°):
  * yaw — угол в плоскости XY от оси X, градусы;
  * pitch положительный, когда игрок смотрит ВНИЗ;
  * позиция X/Y/Z — ноги; глаза на высоте ~64 стоя и ~46 сидя.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def eye_height(duck_amount: float | np.ndarray, standing: float = 64.0, crouch_delta: float = 18.0):
    duck = np.nan_to_num(np.asarray(duck_amount, dtype=float), nan=0.0)
    return standing - crouch_delta * np.clip(duck, 0.0, 1.0)


def aim_error(
    eye: np.ndarray, pitch: float, yaw: float, target: np.ndarray
) -> tuple[float, float, float, float]:
    """Ошибка прицела относительно точки `target`.

    Возвращает (полный угол, ошибка по yaw, ошибка по pitch, дистанция).
    Ошибка по pitch > 0 — прицел НИЖЕ цели.
    """
    d = np.asarray(target, dtype=float) - np.asarray(eye, dtype=float)
    flat = float(np.hypot(d[0], d[1]))
    dist = float(np.linalg.norm(d))
    target_yaw = np.degrees(np.arctan2(d[1], d[0]))
    target_pitch = -np.degrees(np.arctan2(d[2], flat))
    yaw_err = float((yaw - target_yaw + 180.0) % 360.0 - 180.0)
    pitch_err = float(pitch - target_pitch)

    p, y = np.radians(pitch), np.radians(yaw)
    view = np.array([np.cos(p) * np.cos(y), np.cos(p) * np.sin(y), -np.sin(p)])
    cos = float(np.dot(view, d) / dist) if dist > 0 else 1.0
    angle = float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    return angle, yaw_err, pitch_err, dist


@dataclass
class PlayerState:
    tick: int
    x: float
    y: float
    z: float
    pitch: float
    yaw: float
    duck: float
    speed: float

    def eye(self, standing: float = 64.0, crouch_delta: float = 18.0) -> np.ndarray:
        return np.array([self.x, self.y, self.z + float(eye_height(self.duck, standing, crouch_delta))])


class TickIndex:
    """Состояние любого игрока в любом тике за O(log n)."""

    COLS = ("X", "Y", "Z", "pitch", "yaw", "duck_amount", "velocity")

    def __init__(self, ticks: pd.DataFrame):
        self._data: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        for sid, g in ticks.groupby("steamid", sort=False):
            g = g.sort_values("tick").drop_duplicates("tick")
            cols = [g[c].to_numpy(dtype=float) if c in g else np.zeros(len(g)) for c in self.COLS]
            self._data[int(sid)] = (g["tick"].to_numpy(), np.vstack(cols))

    def get(self, steamid: int, tick: int) -> PlayerState | None:
        entry = self._data.get(int(steamid))
        if entry is None:
            return None
        t, vals = entry
        i = int(np.searchsorted(t, tick))
        if i >= len(t) or t[i] != tick:
            return None
        v = vals[:, i]
        return PlayerState(int(tick), *(float(x) for x in v))

    def mean_speed(self, steamid: int, start: int, end: int, max_plausible: float = 400.0) -> float | None:
        entry = self._data.get(int(steamid))
        if entry is None:
            return None
        t, vals = entry
        lo, hi = np.searchsorted(t, start), np.searchsorted(t, end, side="right")
        sp = vals[6, lo:hi]
        sp = sp[np.isfinite(sp) & (sp <= max_plausible)]
        return float(sp.mean()) if sp.size else None
