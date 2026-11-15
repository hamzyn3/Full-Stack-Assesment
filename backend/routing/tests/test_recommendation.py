from datetime import datetime, timezone

from django.test import SimpleTestCase

from routing.services.analysis import CheckpointResult, summarize
from routing.services.checkpoints import Checkpoint
from routing.services.recommendation import recommend
from routing.services.risk import RiskLevel
from routing.services.route_generation import Route

L, M, H, S, N = RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.SEVERE, RiskLevel.NO_TRAVEL
T0 = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)


def analysis(number, duration_h, segments):
    """Build a RouteAnalysis from [(segment_miles, RiskLevel), ...]."""
    route = Route(f"route-{number}", f"Route {number}", [], sum(m for m, _ in segments), duration_h * 3600)
    results = [
        CheckpointResult(Checkpoint(i, 0, 0, 0, T0, miles), wind_mph=0, rain_in_hr=0, risk=level)
        for i, (miles, level) in enumerate(segments)
    ]
    return summarize(route, results)


class SummarizeTests(SimpleTestCase):
    def test_miles_by_risk_and_average(self):
        result = analysis(1, 5, [(50, L), (30, M), (20, S)])
        self.assertEqual(result.miles_by_risk[L], 50)
        self.assertEqual(result.miles_by_risk[M], 30)
        self.assertEqual(result.miles_by_risk[S], 20)
        self.assertEqual(result.miles_by_risk[H], 0)
        # (0*50 + 1*30 + 3*20) / 100
        self.assertAlmostEqual(result.average_risk, 0.9)
        self.assertEqual(result.max_risk, S)
        self.assertFalse(result.has_no_travel)

    def test_no_travel_flag(self):
        self.assertTrue(analysis(1, 5, [(10, L), (10, N)]).has_no_travel)

    def test_empty_route_is_safe(self):
        result = analysis(1, 1, [])
        self.assertEqual(result.average_risk, 0.0)
        self.assertEqual(result.max_risk, L)


class RecommendTests(SimpleTestCase):
    def best(self, *analyses):
        return recommend(list(analyses))

    def test_fewest_severe_miles_beats_everything_else(self):
        fast_but_severe = analysis(1, 5, [(95, L), (5, S)])
        slow_but_clear = analysis(2, 9, [(100, H)])  # lots of High, zero Severe
        result = self.best(fast_but_severe, slow_but_clear)
        self.assertEqual(result.best.route.id, "route-2")
        self.assertIn("Severe", result.reason)

    def test_fewest_high_miles_breaks_a_severe_tie(self):
        a = analysis(1, 5, [(80, L), (20, H)])
        b = analysis(2, 9, [(95, L), (5, H)])
        result = self.best(a, b)
        self.assertEqual(result.best.route.id, "route-2")
        self.assertIn("High", result.reason)

    def test_lowest_average_risk_breaks_a_severe_and_high_tie(self):
        a = analysis(1, 5, [(60, L), (40, M)])  # avg 0.40
        b = analysis(2, 9, [(90, L), (10, M)])  # avg 0.10
        result = self.best(a, b)
        self.assertEqual(result.best.route.id, "route-2")
        self.assertIn("average risk", result.reason)

    def test_shortest_time_breaks_a_full_tie(self):
        slow = analysis(1, 9, [(100, L)])
        fast = analysis(2, 5, [(100, L)])
        result = self.best(slow, fast)
        self.assertEqual(result.best.route.id, "route-2")
        self.assertIn("shortest travel time", result.reason)

    def test_ranking_is_best_first(self):
        a = analysis(1, 5, [(100, S)])
        b = analysis(2, 6, [(100, H)])
        c = analysis(3, 7, [(100, L)])
        result = self.best(a, b, c)
        self.assertEqual([r.route.id for r in result.ranked], ["route-3", "route-2", "route-1"])

    def test_no_travel_route_is_ranked_below_any_drivable_route(self):
        blocked = analysis(1, 4, [(95, L), (5, N)])
        severe = analysis(2, 9, [(50, S), (50, S)])
        result = self.best(blocked, severe)
        self.assertEqual(result.best.route.id, "route-2")
        self.assertFalse(result.all_routes_blocked)
        self.assertEqual(result.ranked[-1].route.id, "route-1")

    def test_all_blocked_picks_fewest_no_travel_miles_and_flags_it(self):
        a = analysis(1, 4, [(80, L), (20, N)])
        b = analysis(2, 9, [(95, L), (5, N)])
        result = self.best(a, b)
        self.assertEqual(result.best.route.id, "route-2")
        self.assertTrue(result.all_routes_blocked)
        self.assertIn("No Travel", result.reason)

    def test_tiny_float_differences_do_not_decide_a_tie(self):
        a = analysis(1, 9, [(33.333, S), (66.667, L)])
        b = analysis(2, 5, [(33.3331, S), (66.6669, L)])
        self.assertEqual(self.best(a, b).best.route.id, "route-2")  # equal at 0.1 mi -> faster wins

    def test_single_route(self):
        result = self.best(analysis(1, 5, [(100, L)]))
        self.assertEqual(result.best.route.id, "route-1")
        self.assertIn("only route", result.reason)

    def test_input_order_does_not_matter(self):
        a = analysis(1, 5, [(100, S)])
        b = analysis(2, 9, [(100, L)])
        self.assertEqual(self.best(a, b).best.route.id, self.best(b, a).best.route.id)
