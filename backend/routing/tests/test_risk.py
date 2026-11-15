from django.test import SimpleTestCase

from routing.services.risk import RiskLevel, classify, load_escalation, rain_level, wind_level

L, M, H, S, N = RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.SEVERE, RiskLevel.NO_TRAVEL


class WindLevelTests(SimpleTestCase):
    def test_band_boundaries(self):
        cases = [
            (0, L), (24.9, L),
            (25, M), (34.9, M),
            (35, H), (44.9, H),
            (45, S), (54.9, S),
            (55, N), (80, N),
        ]  # fmt: skip
        for mph, expected in cases:
            with self.subTest(mph=mph):
                self.assertEqual(wind_level(mph), expected)


class RainLevelTests(SimpleTestCase):
    def test_band_boundaries(self):
        cases = [
            (0, L), (0.09, L),
            (0.10, M), (0.25, M),
            (0.26, H), (0.50, H),
            (0.51, S), (1.00, S),
            (1.01, N), (3.0, N),
        ]  # fmt: skip
        for rain, expected in cases:
            with self.subTest(rain=rain):
                self.assertEqual(rain_level(rain), expected)


class LoadEscalationTests(SimpleTestCase):
    def test_any_load_is_no_travel_at_55_mph(self):
        for load in (0, 10_000, 80_000):
            with self.subTest(load=load):
                self.assertEqual(load_escalation(55, load), N)
                self.assertEqual(classify(55, 0, load), N)

    def test_45_to_54_mph_over_30000_lb_is_no_travel(self):
        for mph in (45, 50, 54.9):
            with self.subTest(mph=mph):
                self.assertEqual(classify(mph, 0, 30_001), N)
                self.assertEqual(classify(mph, 0, 30_000), S)  # exactly 30,000 is not "over"
                self.assertEqual(classify(mph, 0, 0), S)

    def test_35_to_44_mph_over_40000_lb_is_severe(self):
        for mph in (35, 40, 44.9):
            with self.subTest(mph=mph):
                self.assertEqual(classify(mph, 0, 40_001), S)
                self.assertEqual(classify(mph, 0, 40_000), H)  # exactly 40,000 is not "over"
                self.assertEqual(classify(mph, 0, 35_000), H)

    def test_load_rules_do_not_apply_below_their_wind_bands(self):
        self.assertEqual(classify(34.9, 0, 100_000), M)
        self.assertEqual(classify(10, 0, 100_000), L)
        self.assertEqual(load_escalation(10, 100_000), L)

    def test_load_rule_never_lowers_a_level(self):
        # Heavy rain already makes this No Travel; the 35-44 mph rule only raises to Severe.
        self.assertEqual(classify(40, 1.5, 45_000), N)


class ClassifyTests(SimpleTestCase):
    def test_takes_the_worse_of_wind_and_rain(self):
        self.assertEqual(classify(30, 0.3, 10_000), H)  # wind moderate, rain high
        self.assertEqual(classify(40, 0.0, 10_000), H)  # wind high, rain low
        self.assertEqual(classify(10, 0.05, 10_000), L)

    def test_heavy_load_with_rain_in_a_lower_band_still_severe(self):
        self.assertEqual(classify(36, 0.3, 41_000), S)

    def test_rain_alone_can_stop_travel(self):
        self.assertEqual(classify(5, 1.2, 0), N)

    def test_levels_are_ordered_and_keyed(self):
        self.assertLess(L, M)
        self.assertLess(S, N)
        self.assertEqual(N.key, "no_travel")
        self.assertEqual(L.key, "low")
