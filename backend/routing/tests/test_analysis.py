from datetime import date, datetime, timedelta, timezone

from django.test import SimpleTestCase

from routing.services.analysis import analyze_routes
from routing.services.geo import haversine_miles
from routing.services.risk import RiskLevel
from routing.services.route_generation import Route
from routing.services.weather import HourlyWeather

LINE = [(0.0, 0.0), (0.0, 2.0)]
MILES = haversine_miles(*LINE)
DEPARTURE = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)


def hours(start: datetime, count: int, wind: float, rain: float = 0.0):
    first = int(start.replace(minute=0, second=0, microsecond=0).timestamp())
    return {first + i * 3600: HourlyWeather(wind, rain) for i in range(count)}


class FakeWeather:
    """Returns the series chosen by ``chooser(lat, lon)`` and records how it was called."""

    def __init__(self, chooser):
        self.chooser = chooser
        self.calls = []

    def forecast(self, points, start, end):
        self.calls.append((list(points), start, end))
        return [self.chooser(lat, lon) for lat, lon in points]


def route(number=1, geometry=LINE, miles=MILES, seconds=7200):
    return Route(f"route-{number}", f"Route {number}", geometry, miles, seconds)


class AnalyzeRoutesTests(SimpleTestCase):
    def test_weather_is_sampled_at_each_checkpoints_eta(self):
        # Wind rises each hour (08:00 -> 10, 09:00 -> 20, 10:00 -> 30, 11:00 -> 40). The checkpoint
        # ETAs are 08:00, 08:43, 09:27 and 10:00, which are nearest to the 8, 9, 9 and 10 o'clock hours.
        series = {}
        for i, hour in enumerate((8, 9, 10, 11)):
            series[int(datetime(2026, 11, 20, hour, tzinfo=timezone.utc).timestamp())] = HourlyWeather(10.0 * (i + 1), 0)
        weather = FakeWeather(lambda lat, lon: series)

        [analysis] = analyze_routes([route()], DEPARTURE, 10_000, 50, weather)

        self.assertEqual([c.wind_mph for c in analysis.checkpoints], [10.0, 20.0, 20.0, 30.0])
        self.assertEqual(
            [c.risk for c in analysis.checkpoints],
            [RiskLevel.LOW, RiskLevel.LOW, RiskLevel.LOW, RiskLevel.MODERATE],
        )

    def test_position_dependent_weather_and_mile_weighted_totals(self):
        # Calm until lon 1.0, then 40 mph (High; Severe for heavy loads).
        def chooser(lat, lon):
            return hours(DEPARTURE, 6, wind=40.0 if lon > 1.0 else 5.0)

        light = analyze_routes([route()], DEPARTURE, 20_000, 50, FakeWeather(chooser))[0]
        heavy = analyze_routes([route()], DEPARTURE, 45_000, 50, FakeWeather(chooser))[0]

        # Checkpoints at miles 0, 50, 100, 138.2 -> lon 0, 0.72, 1.45, 2.0; segments 25, 50, 44.1, 19.1.
        self.assertAlmostEqual(light.miles_by_risk[RiskLevel.LOW], 75, places=1)
        self.assertAlmostEqual(light.miles_by_risk[RiskLevel.HIGH], MILES - 75, places=1)
        self.assertEqual(light.miles_by_risk[RiskLevel.SEVERE], 0)
        self.assertAlmostEqual(heavy.miles_by_risk[RiskLevel.SEVERE], MILES - 75, places=1)
        self.assertEqual(heavy.miles_by_risk[RiskLevel.HIGH], 0)
        self.assertEqual(sum(light.miles_by_risk.values()), sum(heavy.miles_by_risk.values()))
        self.assertAlmostEqual(sum(heavy.miles_by_risk.values()), MILES, places=6)

    def test_no_travel_from_wind_for_any_load(self):
        weather = FakeWeather(lambda lat, lon: hours(DEPARTURE, 6, wind=60.0))
        [analysis] = analyze_routes([route()], DEPARTURE, 0, 50, weather)
        self.assertTrue(analysis.has_no_travel)
        self.assertEqual(analysis.max_risk, RiskLevel.NO_TRAVEL)

    def test_all_routes_share_one_weather_request_covering_the_trip_dates(self):
        weather = FakeWeather(lambda lat, lon: hours(DEPARTURE, 30, wind=5.0))
        late = datetime(2026, 11, 20, 23, 0, tzinfo=timezone.utc)
        routes = [route(1, seconds=3 * 3600), route(2, seconds=2 * 3600)]
        analyze_routes(routes, late, 10_000, 50, weather)
        self.assertEqual(len(weather.calls), 1)
        points, start, end = weather.calls[0]
        self.assertEqual(len(points), 8)  # 4 checkpoints per route
        self.assertEqual((start, end), (date(2026, 11, 20), date(2026, 11, 21)))  # trip crosses midnight

    def test_departure_in_another_timezone_is_converted_to_utc(self):
        plus_five = timezone(timedelta(hours=5))
        local = datetime(2026, 11, 20, 13, 0, tzinfo=plus_five)  # = 08:00 UTC
        weather = FakeWeather(lambda lat, lon: hours(DEPARTURE, 6, wind=5.0))
        [analysis] = analyze_routes([route()], local, 10_000, 50, weather)
        self.assertEqual(analysis.checkpoints[0].checkpoint.eta, DEPARTURE)

    def test_missing_forecast_hours_raise(self):
        from routing.services.weather import WeatherUnavailableError

        weather = FakeWeather(lambda lat, lon: hours(DEPARTURE, 1, wind=5.0))  # only 08:00 available
        with self.assertRaises(WeatherUnavailableError):
            analyze_routes([route()], DEPARTURE, 10_000, 50, weather)
