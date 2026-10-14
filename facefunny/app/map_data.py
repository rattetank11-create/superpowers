"""Mirage layout used by both the renderer and the simulation.

Two layouts exist:

* ``textured`` (default) - built from ``assets/mirage_texture.png`` and the
  walkability grid ``assets/mirage_mask.txt`` (regenerate both with
  ``tools/build_map_assets.py``);
* ``stylised`` - a hand-made rectangle scheme, used automatically when the
  map assets are missing or broken.

All coordinates are normalised to [0, 1] (x to the right, y downwards), so the
map scales with the window. Movement paths are found with A* on the grid, so
markers never walk through walls. None of this is game data.
"""

from __future__ import annotations

import heapq
import logging
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

Point = Tuple[float, float]
Rect = Tuple[float, float, float, float]

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
TEXTURE_PATH = os.path.join(ASSETS_DIR, "mirage_texture.png")
MASK_PATH = os.path.join(ASSETS_DIR, "mirage_mask.txt")

MAP_MARGIN = 0.01
PATH_MARGIN = 0.005   # clearance kept by straightened path segments
WALL_COST = 4.0       # A* cost factor for cells touching a wall


@dataclass(frozen=True)
class Zone:
    key: str
    label: str
    rect: Rect  # x0, y0, x1, y1
    kind: str = "floor"  # floor | site | ct_spawn | t_spawn
    show_label: bool = True

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 + margin <= x <= x1 - margin and y0 + margin <= y <= y1 - margin

    @property
    def center(self) -> Point:
        x0, y0, x1, y1 = self.rect
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


@dataclass
class Layout:
    name: str
    grid: List[bytearray]               # raw walkability, grid[row][col] in {0, 1}
    zones: List[Zone]                   # overlays (sites, spawns) and, if stylised, the floor
    labels: List[Tuple[str, Point]]     # small area names
    ct_spawns: List[Point]
    t_spawns: List[Point]
    t_routes: List[List[Point]]         # via points between spawn and A site
    ct_routes: List[List[Point]]
    texture_path: Optional[str] = None
    _clear: List[bytearray] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.h = len(self.grid)
        self.w = len(self.grid[0]) if self.h else 0
        if not self.h or any(len(r) != self.w for r in self.grid):
            raise ValueError("walkability grid must be a non-empty rectangle")
        self._clear = _erode(self.grid, 1)
        self.zone_by_key: Dict[str, Zone] = {z.key: z for z in self.zones}
        self.a_site = self.zone_by_key["a_site"]
        self.b_site = self.zone_by_key["b_site"]
        # Hand-placed lane points are snapped onto floor with wall clearance.
        self.t_routes = [[self.nearest_clear(v) for v in lane] for lane in self.t_routes]
        self.ct_routes = [[self.nearest_clear(v) for v in lane] for lane in self.ct_routes]

    # ------------------------------------------------------------- queries
    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        return min(self.w - 1, max(0, int(x * self.w))), min(self.h - 1, max(0, int(y * self.h)))

    def _floor(self, x: float, y: float, grid: Optional[List[bytearray]] = None) -> bool:
        if not (MAP_MARGIN <= x <= 1.0 - MAP_MARGIN and MAP_MARGIN <= y <= 1.0 - MAP_MARGIN):
            return False
        c, r = self._cell(x, y)
        return bool((grid or self.grid)[r][c])

    def is_walkable(self, x: float, y: float, margin: float = 0.0) -> bool:
        """True if the point and a small ring of radius `margin` around it are floor."""
        if not self._floor(x, y):
            return False
        if margin <= 0.0:
            return True
        d = margin * 0.7071
        return all(self._floor(x + dx, y + dy) for dx, dy in (
            (-margin, 0), (margin, 0), (0, -margin), (0, margin), (-d, -d), (d, -d), (-d, d), (d, d)))

    def is_clear(self, x: float, y: float) -> bool:
        """True if the point is on floor with some distance from the walls."""
        return self._floor(x, y, self._clear)

    def segment_walkable(self, a: Point, b: Point, margin: float = 0.0) -> bool:
        steps = max(4, int(math.hypot(b[0] - a[0], b[1] - a[1]) * self.w * 2))
        for i in range(steps + 1):
            t = i / steps
            if not self.is_walkable(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, margin):
                return False
        return True

    def _segment_clear(self, a: Point, b: Point) -> bool:
        steps = max(4, int(math.hypot(b[0] - a[0], b[1] - a[1]) * self.w * 2))
        for i in range(steps + 1):
            t = i / steps
            if not self.is_clear(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t):
                return False
        return True

    def nearest_clear(self, p: Point) -> Point:
        """`p` itself if it has wall clearance, else the closest clear cell centre
        (or, failing that, the closest floor cell centre)."""
        if self.is_clear(*p):
            return p
        c0, r0 = self._cell(*p)
        for grid in (self._clear, self.grid):
            for radius in range(1, max(self.w, self.h)):
                best = None
                for r in range(max(0, r0 - radius), min(self.h, r0 + radius + 1)):
                    for c in range(max(0, c0 - radius), min(self.w, c0 + radius + 1)):
                        if grid[r][c]:
                            d = (r - r0) ** 2 + (c - c0) ** 2
                            if best is None or d < best[0]:
                                best = (d, c, r)
                if best is not None:
                    return self._centre(best[1], best[2])
        return p

    def _centre(self, c: int, r: int) -> Point:
        return ((c + 0.5) / self.w, (r + 0.5) / self.h)

    # ------------------------------------------------------------- pathing
    def find_path(self, a: Point, b: Point) -> List[Point]:
        """A* on the clearance grid, then string-pulled into a few waypoints.
        The returned list ends at `b` (snapped to clear floor) and excludes `a`."""
        origin = a
        a = self.nearest_clear(a)
        b = self.nearest_clear(b)
        start, goal = self._cell(*a), self._cell(*b)
        cells = _astar(self.grid, self._clear, start, goal)
        if cells is None:
            return [b] if self.segment_walkable(a, b) else []
        pts = [a] + [self._centre(c, r) for c, r in cells[1:-1]] + [b]
        # String pulling: skip every waypoint that is directly visible.
        out: List[Point] = []
        i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not self.segment_walkable(pts[i], pts[j], PATH_MARGIN):
                j -= 1
            out.append(pts[j])
            i = j
        if a != origin and out and not self.segment_walkable(origin, out[0]):
            out.insert(0, a)  # first step back onto clear floor
        return out

    def random_point_in(self, zone: Zone, rng, tries: int = 60) -> Point:
        x0, y0, x1, y1 = zone.rect
        for _ in range(tries):
            p = (rng.uniform(x0, x1), rng.uniform(y0, y1))
            if self.is_clear(*p):
                return p
        return self.nearest_clear(zone.center)


def _erode(grid: List[bytearray], radius: int) -> List[bytearray]:
    h, w = len(grid), len(grid[0])
    out = [bytearray(w) for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if not grid[r][c]:
                continue
            ok = True
            for rr in range(r - radius, r + radius + 1):
                if not ok:
                    break
                if rr < 0 or rr >= h:
                    ok = False
                    break
                row = grid[rr]
                for cc in range(c - radius, c + radius + 1):
                    if cc < 0 or cc >= w or not row[cc]:
                        ok = False
                        break
            out[r][c] = 1 if ok else 0
    return out


def _astar(grid: List[bytearray], clear: List[bytearray], start: Tuple[int, int],
           goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
    """8-connected A*. Cells next to walls cost more, so paths keep to the middle
    of corridors but can still squeeze through narrow doorways."""
    h, w = len(grid), len(grid[0])
    sq2 = math.sqrt(2.0)
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, sq2), (1, -1, sq2), (-1, 1, sq2), (-1, -1, sq2)]
    gx, gy = goal

    def heur(c: int, r: int) -> float:
        dx, dy = abs(c - gx), abs(r - gy)
        return (dx + dy) + (sq2 - 2) * min(dx, dy)

    open_heap = [(heur(*start), 0.0, start)]
    came: Dict[Tuple[int, int], Tuple[int, int]] = {}
    cost = {start: 0.0}
    while open_heap:
        _, g, node = heapq.heappop(open_heap)
        if node == goal:
            path = [node]
            while node in came:
                node = came[node]
                path.append(node)
            return path[::-1]
        if g > cost.get(node, math.inf):
            continue
        c, r = node
        for dc, dr, step in moves:
            nc, nr = c + dc, r + dr
            if not (0 <= nc < w and 0 <= nr < h) or not grid[nr][nc]:
                continue
            if dc and dr and not (grid[r][nc] and grid[nr][c]):
                continue  # no corner cutting
            ng = g + (step if clear[nr][nc] else step * WALL_COST)
            if ng < cost.get((nc, nr), math.inf):
                cost[(nc, nr)] = ng
                came[(nc, nr)] = node
                heapq.heappush(open_heap, (ng + heur(nc, nr), ng, (nc, nr)))
    return None


# ---------------------------------------------------------------- textured
def _load_mask(path: str) -> List[bytearray]:
    with open(path, "r", encoding="ascii") as fh:
        w, h = (int(v) for v in fh.readline().split())
        rows = [bytearray(1 if ch == "1" else 0 for ch in fh.readline().strip()) for _ in range(h)]
    if len(rows) != h or any(len(r) != w for r in rows):
        raise ValueError(f"{path}: grid size does not match header {w}x{h}")
    return rows


def textured_layout() -> Layout:
    """Layout matching assets/mirage_texture.png (positions in texture space)."""
    grid = _load_mask(MASK_PATH)
    if not os.path.isfile(TEXTURE_PATH):
        raise FileNotFoundError(TEXTURE_PATH)
    zones = [
        Zone("t_spawn", "T SPAWN", (0.885, 0.27, 0.968, 0.43), "t_spawn"),
        Zone("ct_spawn", "CT SPAWN", (0.200, 0.655, 0.335, 0.775), "ct_spawn"),
        Zone("a_site", "A SITE", (0.470, 0.680, 0.645, 0.860), "site"),
        Zone("b_site", "B SITE", (0.105, 0.170, 0.300, 0.310), "site"),
    ]
    labels = [
        ("APARTMENTS", (0.64, 0.135)),
        ("MID", (0.66, 0.475)),
        ("PALACE", (0.80, 0.835)),
        ("A RAMP", (0.66, 0.665)),
        ("JUNGLE", (0.41, 0.615)),
        ("MARKET", (0.165, 0.425)),
    ]
    return Layout(
        name="textured",
        grid=grid,
        zones=zones,
        labels=labels,
        ct_spawns=[(0.225, 0.725), (0.265, 0.70), (0.30, 0.685), (0.27, 0.75), (0.31, 0.74)],
        t_spawns=[(0.905, 0.30), (0.945, 0.31), (0.915, 0.35), (0.948, 0.375), (0.925, 0.405)],
        t_routes=[
            [(0.93, 0.58), (0.83, 0.60), (0.66, 0.68)],                         # A ramp
            [(0.93, 0.60), (0.88, 0.72), (0.79, 0.80), (0.68, 0.79)],           # palace
            [(0.90, 0.20), (0.72, 0.18), (0.70, 0.34), (0.60, 0.46), (0.50, 0.50), (0.48, 0.62)],  # mid
        ],
        ct_routes=[
            [(0.34, 0.80), (0.44, 0.83)],                                        # straight to A
            [(0.30, 0.60), (0.40, 0.61), (0.48, 0.66)],                         # through jungle
        ],
        texture_path=TEXTURE_PATH,
    )


# ---------------------------------------------------------------- stylised
_STYLISED_ZONES: List[Zone] = [
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


def stylised_layout(size: int = 160) -> Layout:
    grid = [bytearray(size) for _ in range(size)]
    for z in _STYLISED_ZONES:
        x0, y0, x1, y1 = z.rect
        for r in range(int(y0 * size), min(size, int(math.ceil(y1 * size)))):
            for c in range(int(x0 * size), min(size, int(math.ceil(x1 * size)))):
                grid[r][c] = 1
    return Layout(
        name="stylised",
        grid=grid,
        zones=list(_STYLISED_ZONES),
        labels=[],
        ct_spawns=[(0.15, 0.60), (0.21, 0.60), (0.14, 0.655), (0.20, 0.655), (0.17, 0.70)],
        t_spawns=[(0.85, 0.42), (0.90, 0.44), (0.86, 0.50), (0.91, 0.53), (0.87, 0.58)],
        t_routes=[
            [(0.82, 0.62), (0.72, 0.64), (0.62, 0.70)],
            [(0.83, 0.70), (0.79, 0.77), (0.68, 0.81)],
            [(0.82, 0.45), (0.60, 0.45), (0.48, 0.47), (0.46, 0.54), (0.42, 0.60)],
        ],
        ct_routes=[
            [(0.25, 0.70), (0.31, 0.72), (0.37, 0.74)],
            [(0.25, 0.70), (0.31, 0.72), (0.37, 0.64), (0.42, 0.60)],
        ],
    )


def load_layout() -> Layout:
    try:
        layout = textured_layout()
        log.info("Map: textured Mirage (%dx%d grid)", layout.w, layout.h)
        return layout
    except Exception as exc:
        log.warning("Map assets unavailable (%s); using the stylised layout", exc)
        return stylised_layout()

