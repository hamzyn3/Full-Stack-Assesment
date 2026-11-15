from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from routing.services.checkpoints import build_checkpoints, checkpoint_miles, segment_lengths
from routing.services.geo import haversine_miles

DEPARTURE = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)
LINE = [(0.0, 0.0), (0.0, 2.0)]  # due east, ~138 miles
LINE_MILES = haversine_miles(*LINE)


class CheckpointMilesTests(SimpleTestCase):
    def test_regular_marks_plus_destination(self):
        self.assertEqual(checkpoint_miles(120, 50), [0, 50, 100, 120])

    def test_exact_multiple_does_not_duplicate_destination(self):
        self.assertEqual(checkpoint_miles(100, 50), [0, 50, 100])

    def test_tiny_tail_is_absorbed_into_last_checkpoint(self):
        # 0.2 mi past the 100 mi mark: no separate checkpoint for the tail.
        self.assertEqual(checkpoint_miles(100.2, 50), [0, 50, 100.2])

    def test_tail_just_over_half_a_mile_gets_its_own_checkpoint(self):
        self.assertEqual(checkpoint_miles(100.6, 50), [0, 50, 100, 100.6])

    def test_short_trip(self):
        self.assertEqual(checkpoint_miles(5, 50), [0, 5])

    def test_degenerate_trips(self):
        self.assertEqual(checkpoint_miles(0, 25), [0])
        self.assertEqual(checkpoint_miles(0.3, 25), [0])

    def test_interval_choices(self):
        for interval in (10, 25, 50):
            miles = checkpoint_miles(300, interval)
            self.assertEqual(miles[:3], [0, interval, 2 * interval])
            self.assertEqual(miles[-1], 300)


class SegmentLengthTests(SimpleTestCase):
    def test_segments_split_at_midpoints_and_sum_to_total(self):
        self.assertEqual(segment_lengths([0, 50, 100, 120], 120), [25, 50, 35, 10])

    def test_single_checkpoint_owns_everything(self):
        self.assertEqual(segment_lengths([0], 0.3), [0.3])

    def test_zero_length(self):
        self.assertEqual(segment_lengths([0], 0), [0])


class BuildCheckpointsTests(SimpleTestCase):
    def build(self, interval=50, duration=7200, geometry=LINE, total=LINE_MILES):
        return build_checkpoints(geometry, total, duration, DEPARTURE, interval)

    def test_first_checkpoint_is_origin_at_departure_and_last_is_destination(self):
        checkpoints = self.build()
        self.assertEqual((checkpoints[0].lat, checkpoints[0].lon), (0.0, 0.0))
        self.assertEqual(checkpoints[0].eta, DEPARTURE)
        self.assertEqual(checkpoints[-1].lon, 2.0)
        self.assertEqual(checkpoints[-1].eta, DEPARTURE + timedelta(seconds=7200))

    def test_eta_scales_with_distance_travelled(self):
        checkpoints = self.build(interval=50)
        expected = DEPARTURE + timedelta(seconds=7200 * 50 / LINE_MILES)
        self.assertAlmostEqual((checkpoints[1].eta - expected).total_seconds(), 0, places=3)
        self.assertEqual(checkpoints[1].mile, 50)

    def test_positions_follow_the_route(self):
        checkpoints = self.build(interval=50)
        self.assertAlmostEqual(checkpoints[1].lon, 2.0 * 50 / LINE_MILES, places=4)
        self.assertEqual(checkpoints[1].lat, 0.0)

    def test_positions_follow_a_bent_route(self):
        # Two equal legs: east then north. The midpoint checkpoint is at the corner.
        geometry = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
        total = haversine_miles(geometry[0], geometry[1]) + haversine_miles(geometry[1], geometry[2])
        checkpoints = self.build(interval=total / 2, geometry=geometry, total=total, duration=3600)
        self.assertAlmostEqual(checkpoints[1].lat, 0.0, places=3)
        self.assertAlmostEqual(checkpoints[1].lon, 1.0, places=3)

    def test_segment_miles_sum_to_route_length(self):
        for interval in (10, 25, 50):
            with self.subTest(interval=interval):
                checkpoints = self.build(interval=interval)
                self.assertAlmostEqual(sum(c.segment_miles for c in checkpoints), LINE_MILES, places=6)

    def test_checkpoint_count_matches_interval(self):
        self.assertEqual(len(self.build(interval=50)), 4)  # 0, 50, 100, 138
        self.assertEqual(len(self.build(interval=25)), 7)  # 0, 25, ..., 125, 138
        self.assertEqual(len(self.build(interval=10)), 15)

    def test_uses_provider_distance_when_it_differs_from_polyline(self):
        # Provider says 150 mi for the same polyline; checkpoints still span the whole line.
        checkpoints = self.build(interval=50, total=150)
        self.assertEqual([c.mile for c in checkpoints], [0, 50, 100, 150])
        self.assertAlmostEqual(checkpoints[-1].lon, 2.0, places=6)
        self.assertAlmostEqual(checkpoints[1].lon, 2.0 / 3, places=4)

    def test_zero_length_route_gives_one_checkpoint(self):
        checkpoints = self.build(geometry=[(1.0, 1.0)], total=0)
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0].eta, DEPARTURE)
