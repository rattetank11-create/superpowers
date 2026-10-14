"""Purely artificial movement logic for the ten radar markers.

The simulation runs on a fixed timestep. The renderer asks for positions
interpolated between the previous and the current tick, so the motion stays
smooth regardless of the display frame rate. Nothing here talks to the game.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, List, Optional, Tuple

from . import map_data
from .map_data import Point

SIM_HZ = 60
SIM_DT = 1.0 / SIM_HZ
MAX_STEPS_PER_FRAME = 8  # prevents a "spiral of death" after a long stall

ARRIVE_RADIUS = 0.012
WALL_MARGIN = 0.004
TRAIL_LENGTH = 26
TRAIL_EVERY_TICKS = 4


class SimState(Enum):
    IDLE = "idle"        # at bases, never started since last reset
    RUNNING = "running"
    PAUSED = "paused"


class Team(Enum):
    CT = "CT"
    T = "T"


@dataclass
class Player:
    team: Team
    number: int
    spawn: Point
    x: float = 0.0
    y: float = 0.0
    prev_x: float = 0.0
    prev_y: float = 0.0
    heading: float = 0.0
    speed: float = 0.0
    base_speed: float = 0.04
    route: List[Point] = field(default_factory=list)
    route_index: int = 0
    stop_timer: float = 0.0
    wander: float = 0.0
    arrived: bool = False
    hold_timer: float = 0.0
    stuck_timer: float = 0.0
    trail: Deque[Point] = field(default_factory=lambda: deque(maxlen=TRAIL_LENGTH))

    @property
    def label(self) -> str:
        return f"{self.team.value} #{self.number}"

    @property
    def target(self) -> Optional[Point]:
        if self.route_index < len(self.route):
            return self.route[self.route_index]
        return None

    def place_at_spawn(self, face: Point) -> None:
        self.x, self.y = self.spawn
        self.prev_x, self.prev_y = self.spawn
        self.speed = 0.0
        self.route = []
        self.route_index = 0
        self.stop_timer = 0.0
        self.wander = 0.0
        self.arrived = False
        self.hold_timer = 0.0
        self.stuck_timer = 0.0
        self.trail.clear()
        self.heading = math.atan2(face[1] - self.y, face[0] - self.x)


class Simulation:
    def __init__(self, seed: Optional[int] = None, layout: Optional[map_data.Layout] = None) -> None:
        self.layout = layout or map_data.load_layout()
        self.rng = random.Random(seed)
        self.state = SimState.IDLE
        self.players: List[Player] = []
        self._accumulator = 0.0
        self._tick = 0
        for i, spawn in enumerate(self.layout.ct_spawns):
            self.players.append(Player(Team.CT, i + 1, spawn))
        for i, spawn in enumerate(self.layout.t_spawns):
            self.players.append(Player(Team.T, i + 1, spawn))
        self.reset()

    # ------------------------------------------------------------------ control
    def reset(self) -> None:
        """Return every marker to its base and stop the movement."""
        for p in self.players:
            p.place_at_spawn(self.layout.a_site.center)
        self.state = SimState.IDLE
        self._accumulator = 0.0
        self._tick = 0

    def restart(self) -> None:
        """Reset to bases and immediately start a new run."""
        self.reset()
        self.start()

    def start(self) -> None:
        if self.state is SimState.RUNNING:
            return  # never run two movement cycles at once
        if self.state is SimState.IDLE:
            for p in self.players:
                self._assign_route(p)
        self.state = SimState.RUNNING
        self._accumulator = 0.0

    def pause(self) -> None:
        if self.state is SimState.RUNNING:
            self.state = SimState.PAUSED
            self._sync_prev()

    def toggle(self) -> SimState:
        if self.state is SimState.RUNNING:
            self.pause()
        else:
            self.start()
        return self.state

    @property
    def running(self) -> bool:
        return self.state is SimState.RUNNING

    @property
    def all_arrived(self) -> bool:
        return all(p.arrived for p in self.players)

    # ------------------------------------------------------------------- timing
    def advance(self, real_dt: float) -> float:
        """Advance by real elapsed time; return the interpolation factor [0, 1)."""
        if self.state is not SimState.RUNNING:
            return 1.0
        real_dt = max(0.0, min(real_dt, 0.25))
        self._accumulator += real_dt
        steps = 0
        while self._accumulator >= SIM_DT and steps < MAX_STEPS_PER_FRAME:
            self.step(SIM_DT)
            self._accumulator -= SIM_DT
            steps += 1
        if steps == MAX_STEPS_PER_FRAME:
            self._accumulator = min(self._accumulator, SIM_DT)
        return self._accumulator / SIM_DT

    def interpolated(self, player: Player, alpha: float) -> Point:
        alpha = max(0.0, min(1.0, alpha))
        return (
            player.prev_x + (player.x - player.prev_x) * alpha,
            player.prev_y + (player.y - player.prev_y) * alpha,
        )

    def _sync_prev(self) -> None:
        for p in self.players:
            p.prev_x, p.prev_y = p.x, p.y

    # ------------------------------------------------------------------ routing
    def _jittered(self, point: Point, radius: float) -> Point:
        for _ in range(12):
            cand = (
                point[0] + self.rng.uniform(-radius, radius),
                point[1] + self.rng.uniform(-radius, radius),
            )
            if self.layout.is_clear(*cand):
                return cand
        return self.layout.nearest_clear(point)

    def _assign_route(self, p: Player) -> None:
        """Pick one of the team's lanes, jitter its via points and let A* join them,
        so every marker takes a slightly different, wall-free path."""
        lay = self.layout
        lanes = lay.t_routes if p.team is Team.T else lay.ct_routes
        vias = [self._jittered(v, 0.015) for v in self.rng.choice(lanes)]
        dest = lay.random_point_in(lay.a_site, self.rng)
        route: List[Point] = []
        prev: Point = (p.x, p.y)
        for target in vias + [dest]:
            leg = lay.find_path(prev, target)
            if leg:
                route.extend(leg)
                prev = leg[-1]
        p.route = route or [lay.nearest_clear(dest)]
        p.route_index = 0
        p.base_speed = self.rng.uniform(0.03, 0.06)
        p.speed = 0.0
        p.stop_timer = self.rng.uniform(0.0, 0.6)  # staggered reaction time

    # ----------------------------------------------------------------- physics
    def step(self, dt: float) -> None:
        self._tick += 1
        for p in self.players:
            p.prev_x, p.prev_y = p.x, p.y
            self._step_player(p, dt)
            if self._tick % TRAIL_EVERY_TICKS == 0:
                p.trail.append((p.x, p.y))

    def _step_player(self, p: Player, dt: float) -> None:
        rng = self.rng
        target = p.target
        if target is None:
            # Holding the site: occasionally pick a new spot nearby.
            p.arrived = True
            p.hold_timer -= dt
            if p.hold_timer <= 0.0:
                dest = self.layout.random_point_in(self.layout.a_site, rng)
                p.route.extend(self.layout.find_path((p.x, p.y), dest))
                p.hold_timer = rng.uniform(1.5, 4.0)
            target = p.target
            if target is None:
                self._decelerate(p, dt)
                return

        # Random short stops.
        if p.stop_timer > 0.0:
            p.stop_timer -= dt
            self._decelerate(p, dt)
            return
        if rng.random() < 0.10 * dt:
            p.stop_timer = rng.uniform(0.3, 1.4)

        dx, dy = target[0] - p.x, target[1] - p.y
        dist = math.hypot(dx, dy)
        if dist < ARRIVE_RADIUS:
            p.route_index += 1
            p.stuck_timer = 0.0
            if p.route_index >= len(p.route):
                p.arrived = True
                p.hold_timer = rng.uniform(1.0, 3.5)
            return

        # Smooth wander (Ornstein-Uhlenbeck style) gives chaotic but fluid turns.
        p.wander += (-p.wander * 1.4 + rng.gauss(0.0, 1.0) * 2.6) * dt
        p.wander = max(-0.9, min(0.9, p.wander))
        wander_weight = min(1.0, dist / 0.06)  # straighten up near waypoints
        if not self.layout.is_clear(p.x, p.y):
            wander_weight *= 0.25  # narrow passage: walk straighter
        desired = math.atan2(dy, dx) + p.wander * wander_weight

        # Limited turn rate: no instant direction changes.
        diff = (desired - p.heading + math.pi) % (2 * math.pi) - math.pi
        max_turn = 4.0 * dt
        p.heading += max(-max_turn, min(max_turn, diff))

        # Speed varies slightly over time, slows down on sharp turns.
        speed_noise = 1.0 + 0.15 * math.sin(self._tick * 0.05 + p.number * 1.7)
        turn_factor = 0.55 + 0.45 * math.cos(min(abs(diff), math.pi / 2))
        target_speed = p.base_speed * speed_noise * turn_factor
        p.speed += (target_speed - p.speed) * min(1.0, 3.0 * dt)

        step = p.speed * dt
        nx = p.x + math.cos(p.heading) * step
        ny = p.y + math.sin(p.heading) * step
        nx, ny = self._apply_separation(p, nx, ny, dt)

        # Keep a little distance from walls, unless we are already closer than
        # that (e.g. pushed into a nook) or that is what got us stuck.
        keep = p.stuck_timer < 0.5 and self.layout.is_walkable(p.x, p.y, WALL_MARGIN)
        margin = WALL_MARGIN if keep else 0.0
        if self.layout.is_walkable(nx, ny, margin):
            p.x, p.y = nx, ny
        elif self.layout.is_walkable(nx, p.y, margin):
            p.x = nx  # slide along the wall
        elif self.layout.is_walkable(p.x, ny, margin):
            p.y = ny
        else:
            # Blocked: turn straight towards the target and calm the wander.
            p.heading = math.atan2(dy, dx)
            p.wander *= 0.3

        moved = math.hypot(p.x - p.prev_x, p.y - p.prev_y)
        if moved < step * 0.2:
            p.stuck_timer += dt
            if p.stuck_timer > 1.0:
                # Wandered behind a corner: re-plan the way to the current waypoint.
                leg = self.layout.find_path((p.x, p.y), target)
                if leg:
                    p.route[p.route_index:p.route_index + 1] = leg
                p.heading = math.atan2(dy, dx)
                p.wander = 0.0
                p.stuck_timer = 0.0
        else:
            p.stuck_timer = 0.0

    def _decelerate(self, p: Player, dt: float) -> None:
        p.speed *= max(0.0, 1.0 - 6.0 * dt)
        if p.speed < 1e-4:
            p.speed = 0.0
            return
        nx = p.x + math.cos(p.heading) * p.speed * dt
        ny = p.y + math.sin(p.heading) * p.speed * dt
        if self.layout.is_walkable(nx, ny, WALL_MARGIN):
            p.x, p.y = nx, ny

    def _apply_separation(self, p: Player, nx: float, ny: float, dt: float) -> Tuple[float, float]:
        min_dist = 0.022
        push_x = push_y = 0.0
        for other in self.players:
            if other is p:
                continue
            ox, oy = nx - other.x, ny - other.y
            d = math.hypot(ox, oy)
            if 1e-6 < d < min_dist:
                strength = (min_dist - d) / min_dist
                push_x += ox / d * strength
                push_y += oy / d * strength
        return nx + push_x * 0.06 * dt, ny + push_y * 0.06 * dt
