from django.test import SimpleTestCase

from routing.services.geo import densify, haversine_miles, offset_midpoint, path_overlap


class GeoTests(SimpleTestCase):
    def test_haversine_one_degree_of_latitude(self):
        self.assertAlmostEqual(haversine_miles((0, 0), (1, 0)), 69.09, delta=0.2)

    def test_densify_limits_gap_and_keeps_endpoints(self):
        dense = densify([(0, 0), (0, 1)], step_miles=5)
        self.assertEqual(dense[0], (0, 0))
        self.assertEqual(dense[-1], (0, 1))
        gaps = [haversine_miles(a, b) for a, b in zip(dense, dense[1:])]
        self.assertLessEqual(max(gaps), 5.0)

    def test_overlap_identical_paths_is_one(self):
        path = [(0, 0), (0, 1), (0.5, 2)]
        self.assertEqual(path_overlap(path, path), 1.0)

    def test_overlap_disjoint_paths_is_zero(self):
        self.assertEqual(path_overlap([(0, 0), (0, 1)], [(5, 0), (5, 1)]), 0.0)

    def test_overlap_partial(self):
        # Second path shares the first half, then diverges north.
        a = [(0, 0), (0, 2)]
        b = [(0, 0), (0, 1), (1, 1.5)]
        overlap = path_overlap(a, b)
        self.assertGreater(overlap, 0.2)
        self.assertLess(overlap, 0.8)

    def test_offset_midpoint_is_perpendicular_and_signed(self):
        origin, destination = (0.0, 0.0), (0.0, 2.0)  # due east
        north = offset_midpoint(origin, destination, 0.2)
        south = offset_midpoint(origin, destination, -0.2)
        self.assertAlmostEqual(north[1], 1.0, places=3)
        self.assertGreater(north[0], 0)
        self.assertLess(south[0], 0)
        expected_shift_deg = 0.2 * haversine_miles(origin, destination) / 69.0
        self.assertAlmostEqual(north[0], expected_shift_deg, places=3)

    def test_offset_midpoint_same_point(self):
        self.assertEqual(offset_midpoint((1, 1), (1, 1), 0.2), (1.0, 1.0))
