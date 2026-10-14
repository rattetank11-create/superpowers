"""Logic tests for the movement simulation (no Qt required)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import map_data  # noqa: E402
from app.simulation import SIM_DT, Simulation, SimState, Team  # noqa: E402


LAYOUTS = (map_data.textured_layout(), map_data.stylised_layout())


class LayoutTest(unittest.TestCase):
    def test_default_layout_is_the_textured_map(self):
        self.assertEqual(map_data.load_layout().name, "textured")

    def test_spawns_are_walkable_and_in_their_zone(self):
        for lay in LAYOUTS:
            ct, t = lay.zone_by_key["ct_spawn"], lay.zone_by_key["t_spawn"]
            self.assertEqual(len(lay.ct_spawns), 5)
            self.assertEqual(len(lay.t_spawns), 5)
            for pt in lay.ct_spawns:
                self.assertTrue(ct.contains(*pt) and lay.is_walkable(*pt), (lay.name, pt))
            for pt in lay.t_spawns:
                self.assertTrue(t.contains(*pt) and lay.is_walkable(*pt), (lay.name, pt))

    def test_every_lane_has_a_wall_free_path_to_a(self):
        for lay in LAYOUTS:
            for spawns, lanes in ((lay.t_spawns, lay.t_routes), (lay.ct_spawns, lay.ct_routes)):
                for lane in lanes:
                    stops = [spawns[0]] + lane + [lay.a_site.center]
                    for a, b in zip(stops, stops[1:]):
                        leg = lay.find_path(a, b)
                        self.assertTrue(leg, (lay.name, a, b))
                        prev = a
                        for q in leg:
                            self.assertTrue(lay.segment_walkable(prev, q), (lay.name, prev, q))
                            prev = q

    def test_find_path_never_crosses_walls_between_random_points(self):
        import random
        rng = random.Random(0)
        lay = LAYOUTS[0]
        for _ in range(30):
            a = lay.random_point_in(map_data.Zone("all", "", (0, 0, 1, 1)), rng)
            b = lay.random_point_in(map_data.Zone("all", "", (0, 0, 1, 1)), rng)
            prev = a
            for q in lay.find_path(a, b):
                self.assertTrue(lay.segment_walkable(prev, q), (a, b, prev, q))
                prev = q


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
        for lay, seed in [(lay, seed) for lay in LAYOUTS for seed in range(10)]:
            sim = Simulation(seed=seed, layout=lay)
            sim.start()
            max_speed = max(p.base_speed for p in sim.players) * 1.2
            for _ in range(int(90 / SIM_DT)):
                sim.step(SIM_DT)
                for p in sim.players:
                    jump = math.hypot(p.x - p.prev_x, p.y - p.prev_y)
                    self.assertLess(jump, max_speed * SIM_DT * 1.5, "teleport detected")
                    self.assertTrue(lay.is_walkable(p.x, p.y), (lay.name, seed, p.label))
                if sim.all_arrived:
                    break
            self.assertTrue(sim.all_arrived, f"{lay.name} seed {seed}: not everyone reached A")
            for p in sim.players:
                self.assertTrue(lay.a_site.contains(p.x, p.y, margin=-0.03), (lay.name, seed, p.label))

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
