import unittest

from app.engine import Road, choose_next_direction, green_duration, optimize_fixed_vs_adaptive, severity


class SignalOptimizationTests(unittest.TestCase):
    def test_green_duration_respects_bounds_and_prioritizes_heavier_queues(self):
        light = Road("North", 0, 0, 0)
        heavy = Road("East", 20, 22, 95)
        self.assertGreater(green_duration(heavy, 10, 45), green_duration(light, 10, 45))
        self.assertEqual(green_duration(heavy, 10, 20), 20)
        self.assertEqual(green_duration(light, 20, 45), 20)

    def test_vehicle_count_influences_green_allocation(self):
        low_count = Road("North", 2, 8, 20)
        high_count = Road("North", 18, 8, 20)
        self.assertGreater(green_duration(high_count, 10, 45), green_duration(low_count, 10, 45))

    def test_congestion_thresholds(self):
        self.assertEqual(severity(2), "Low")
        self.assertEqual(severity(7), "Medium")
        self.assertEqual(severity(14), "High")
        self.assertEqual(severity(20), "Critical")

    def test_scheduler_excludes_current_phase_and_rewards_waiting_approaches(self):
        roads = [Road(direction, 5, queue, queue * 4) for direction, queue in (
            ("North", 3), ("East", 16), ("South", 9), ("West", 2),
        )]
        result = choose_next_direction(roads, "East", {"North": 0, "East": 0, "South": 0, "West": 0}, 20)
        self.assertEqual(result, "South")
        self.assertNotEqual(result, "East")

    def test_adaptive_comparison_uses_input_samples(self):
        result = optimize_fixed_vs_adaptive([12, 24, 36])
        self.assertGreater(result["fixed_average_wait_seconds"], result["adaptive_average_wait_seconds"])
        self.assertGreater(result["improvement_percent"], 0)


if __name__ == "__main__":
    unittest.main()
