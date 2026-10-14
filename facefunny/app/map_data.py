"""Stylised top-down layout of de_mirage used by both the renderer and the simulation.

All coordinates are normalised to the range [0, 1] (x to the right, y downwards),
so the map can be scaled to any window size. The layout is an artistic
approximation of the map, not real game data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class Zone:
    key: str
    label: str
    rect: Tuple[float, float, float, float]  # x0, y0, x1, y1
    kind: str = "floor"  # floor | site | ct_spawn | t_spawn
    show_label: bool = True

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 + margin <= x <= x1 - margin and y0 + margin <= y <= y1 - margin

    @property
    def center(self) -> Point:
        x0, y0, x1, y1 = self.rect
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


ZONES: List[Zone] = [
    Zone("t_spawn", "T SPAWN", (0.80, 0.34, 0.95, 0.64), "t_spawn"),
    Zone("t_ramp", "T RAMP", (0.66, 0.58, 0.84, 0.70)),
    Zone("palace_entry", "", (0.78, 0.62, 0.88, 0.80), show_label=False),
    Zone("palace", "PALACE", (0.60, 0.74, 0.80, 0.88)),
    Zone("a_ramp", "A RAMP", (0.56, 0.62, 0.68, 0.80)),
    Zone("a_site", "A SITE", (0.36, 0.66, 0.60, 0.88), "site"),
    Zone("ticket", "TICKET", (0.24, 0.62, 0.38, 0.80)),
    Zone("ct_spawn", "CT SPAWN", (0.10, 0.56, 0.26, 0.76), "ct_spawn"),
    Zone("jungle", "JUNGLE", (0.36, 0.52, 0.48, 0.66)),
    Zone("connector", "CON", (0.44, 0.46, 0.52, 0.56)),
    Zone("mid", "MID", (0.40, 0.40, 0.84, 0.50)),
    Zone("window", "WINDOW", (0.28, 0.36, 0.42, 0.50)),
    Zone("b_short", "SHORT", (0.28, 0.24, 0.38, 0.38)),
    Zone("t_apps", "", (0.76, 0.14, 0.86, 0.36), show_label=False),
    Zone("b_apps", "APARTMENTS", (0.36, 0.14, 0.82, 0.24)),
    Zone("b_site", "B SITE", (0.08, 0.08, 0.34, 0.32), "site"),
    Zone("market", "MARKET", (0.10, 0.32, 0.22, 0.58)),
]

ZONE_BY_KEY: Dict[str, Zone] = {z.key: z for z in ZONES}

A_SITE = ZONE_BY_KEY["a_site"]
B_SITE = ZONE_BY_KEY["b_site"]

# Points that lie in the overlap of neighbouring zones so that straight
# segments between consecutive waypoints stay on walkable ground.
WAYPOINTS: Dict[str, Point] = {
    "t_spawn": (0.875, 0.49),
    "t_ramp_top": (0.82, 0.62),
    "t_ramp": (0.72, 0.64),
    "a_ramp": (0.62, 0.70),
    "palace_entry": (0.83, 0.70),
    "palace_in": (0.79, 0.77),
    "palace": (0.68, 0.81),
    "mid_t": (0.82, 0.45),
    "mid": (0.60, 0.45),
    "connector_top": (0.48, 0.47),
    "connector": (0.46, 0.54),
    "jungle": (0.42, 0.60),
    "a_from_jungle": (0.42, 0.69),
    "ct_spawn": (0.18, 0.66),
    "ct_exit": (0.25, 0.70),
    "ticket": (0.31, 0.72),
    "ticket_jungle": (0.37, 0.64),
    "a_from_ct": (0.37, 0.74),
    "a_site": A_SITE.center,
}

T_ROUTES: List[List[str]] = [
    ["t_spawn", "t_ramp_top", "t_ramp", "a_ramp", "a_site"],
    ["t_spawn", "palace_entry", "palace_in", "palace", "a_site"],
    ["t_spawn", "mid_t", "mid", "connector_top", "connector", "jungle", "a_from_jungle", "a_site"],
]

CT_ROUTES: List[List[str]] = [
    ["ct_spawn", "ct_exit", "ticket", "a_from_ct", "a_site"],
    ["ct_spawn", "ct_exit", "ticket", "ticket_jungle", "jungle", "a_from_jungle", "a_site"],
]

CT_SPAWN_POINTS: List[Point] = [
    (0.15, 0.60), (0.21, 0.60), (0.14, 0.655), (0.20, 0.655), (0.17, 0.70),
]
T_SPAWN_POINTS: List[Point] = [
    (0.85, 0.42), (0.90, 0.44), (0.86, 0.50), (0.91, 0.53), (0.87, 0.58),
]

MAP_MARGIN = 0.02


def _on_floor(x: float, y: float) -> bool:
    if not (MAP_MARGIN <= x <= 1.0 - MAP_MARGIN and MAP_MARGIN <= y <= 1.0 - MAP_MARGIN):
        return False
    return any(z.contains(x, y) for z in ZONES)


def is_walkable(x: float, y: float, margin: float = 0.0) -> bool:
    """True if the point (and a small cross of radius `margin` around it) is on the
    walkable union of zones. Checking the union keeps zone junctions passable."""
    if not _on_floor(x, y):
        return False
    if margin <= 0.0:
        return True
    return (
        _on_floor(x - margin, y) and _on_floor(x + margin, y)
        and _on_floor(x, y - margin) and _on_floor(x, y + margin)
        and _on_floor(x - margin * 0.7, y - margin * 0.7)
        and _on_floor(x + margin * 0.7, y - margin * 0.7)
        and _on_floor(x - margin * 0.7, y + margin * 0.7)
        and _on_floor(x + margin * 0.7, y + margin * 0.7)
    )


def segment_walkable(a: Point, b: Point, margin: float = 0.0, steps: int = 40) -> bool:
    """Sample a straight segment and check that every sample is walkable."""
    for i in range(steps + 1):
        t = i / steps
        if not is_walkable(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, margin):
            return False
    return True
