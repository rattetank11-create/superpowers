"""Logic tests for the movement simulation (no Qt required)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import map_data  # noqa: E402
from app.simulation import SIM_DT, Simulation, SimState, Team  # noqa: E402


class RouteGeometryTest(unittest.TestCase):
    def test_route_segments_are_walkable(self):
        for routes in (map_data.T_ROUTES, map_data.CT_ROUTES):
            for route in routes:
                pts = [map_data.WAYPOINTS[n] for n in route]
                for a, b in zip(pts, pts[1:]):
                    self.assertTrue(map_data.segment_walkable(a, b, 0.006), (route, a, b))

    def test_spawns_are_walkable_and_in_their_zone(self):
        ct, t = map_data.ZONE_BY_KEY["ct_spawn"], map_data.ZONE_BY_KEY["t_spawn"]
        for pt in map_data.CT_SPAWN_POINTS:
            self.assertTrue(ct.contains(*pt))
        for pt in map_data.T_SPAWN_POINTS:
            self.assertTrue(t.contains(*pt))


class SimulationTest(unittest.TestCase):
    def test_ten_players_five_per_team_at_bases(self):
        sim = Simulation(seed=1)
        self.assertEqual(len(sim.players), 10)
        self.assertEqual(sum(p.team is Team.CT for p in sim.players), 5)
        self.assertEqual(sum(p.team is Team.T for p in sim.players), 5)
        for p in sim.players:
            self.assertEqual((p.x, p.y), p.spawn)

    def test_toggle_cycles_run_and_pause(self):
        sim = Simulation(seed=2)
        self.assertIs(sim.state, SimState.IDLE)
        self.assertIs(sim.toggle(), SimState.RUNNING)
        self.assertIs(sim.toggle(), SimState.PAUSED)
        self.assertIs(sim.toggle(), SimState.RUNNING)

    def test_start_twice_does_not_reassign_routes(self):
        sim = Simulation(seed=3)
        sim.start()
        routes = [list(p.route) for p in sim.players]
        sim.start()
        self.assertEqual(routes, [p.route for p in sim.players])

    def test_paused_players_do_not_move(self):
        sim = Simulation(seed=4)
        sim.start()
        sim.advance(1.0 / 30)
        for _ in range(120):
            sim.advance(1.0 / 60)
        sim.pause()
        before = [(p.x, p.y) for p in sim.players]
        for _ in range(60):
            sim.advance(1.0 / 60)
        self.assertEqual(before, [(p.x, p.y) for p in sim.players])

    def test_movement_is_smooth_and_reaches_a_site(self):
        for seed in range(20):
            sim = Simulation(seed=seed)
            sim.start()
            max_speed = max(p.base_speed for p in sim.players) * 1.2
            for _ in range(int(60 / SIM_DT)):
                sim.step(SIM_DT)
                for p in sim.players:
                    jump = math.hypot(p.x - p.prev_x, p.y - p.prev_y)
                    self.assertLess(jump, max_speed * SIM_DT * 1.5, "teleport detected")
                    self.assertTrue(map_data.is_walkable(p.x, p.y), (seed, p.label))
                if sim.all_arrived:
                    break
            self.assertTrue(sim.all_arrived, f"seed {seed}: not everyone reached A")
            for p in sim.players:
                self.assertTrue(map_data.A_SITE.contains(p.x, p.y))

    def test_players_use_different_paths_and_speeds(self):
        sim = Simulation(seed=5)
        sim.start()
        self.assertGreater(len({round(p.base_speed, 4) for p in sim.players}), 5)
        self.assertEqual(len({tuple(p.route[0]) for p in sim.players}), 10)

    def test_reset_returns_to_bases(self):
        sim = Simulation(seed=6)
        sim.start()
        for _ in range(300):
            sim.step(SIM_DT)
        sim.reset()
        self.assertIs(sim.state, SimState.IDLE)
        for p in sim.players:
            self.assertEqual((p.x, p.y), p.spawn)

    def test_interpolation_between_ticks(self):
        sim = Simulation(seed=7)
        p = sim.players[0]
        p.prev_x, p.prev_y, p.x, p.y = 0.0, 0.0, 1.0, 0.5
        self.assertEqual(sim.interpolated(p, 0.5), (0.5, 0.25))


if __name__ == "__main__":
    unittest.main()
