from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from routing.services.geo import haversine_miles
from routing.services.heatmap import HOURS, MAX_CELLS, UNAVAILABLE, build_heatmap, choose_grid, corridor_cells
from routing.services.risk import RiskLevel
from routing.services.weather import (
    ForecastRangeError,
    HourlyWeather,
    OpenMeteoClient,
    WeatherRateLimitError,
    WeatherUnavailableError,
)

DEPARTURE = datetime(2026, 11, 20, 8, 40, tzinfo=timezone.utc)
START = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)
LINE = [(32.0, -96.0), (32.0, -90.0)]  # ~350 miles due east


def series_for(start, wind_by_hour, rain=0.0, hours=HOURS):
    """Series whose wind at hour h after ``start`` is wind_by_hour(h)."""
    first = int(start.timestamp())
    return {first + h * 3600: HourlyWeather(wind_by_hour(h), rain) for h in range(hours)}


class FakeWeather:
    def __init__(self, chooser):
        self.chooser = chooser
        self.calls = []

    def forecast(self, points, start, end):
        self.calls.append((list(points), start, end))
        return [self.chooser(lat, lon) for lat, lon in points]


class CorridorTests(SimpleTestCase):
    def test_cells_cover_the_route_with_a_margin(self):
        cells = corridor_cells([LINE], 0.25)
        lats = {lat for lat, _ in cells}
        lons = [lon for _, lon in cells]
        # Three rows of cells (the route's row plus one either side).
        self.assertEqual(len(lats), 3)
        self.assertLess(min(lons), -96.0)
        self.assertGreater(max(lons), -90.0)

    def test_every_route_point_is_inside_a_cell(self):
        cells = corridor_cells([LINE], 0.25)
        for point in [(32.0, -96.0), (32.0, -93.1), (32.0, -90.0)]:
            nearest = min(haversine_miles(point, cell) for cell in cells)
            self.assertLess(nearest, 0.25 * 69 * 0.75)

    def test_cells_are_unique_and_shared_between_routes(self):
        one = corridor_cells([LINE], 0.25)
        both = corridor_cells([LINE, LINE], 0.25)
        self.assertEqual(len(both), len(one))
        self.assertEqual(len(set(both)), len(both))

    def test_short_trip_keeps_the_fine_grid(self):
        cell_deg, cells = choose_grid([[(32.0, -96.0), (32.5, -95.5)]])
        self.assertEqual(cell_deg, 0.25)
        self.assertLessEqual(len(cells), MAX_CELLS)

    def test_long_trip_coarsens_the_grid_to_stay_under_the_cap(self):
        coast_to_coast = [[(34.0, -118.0), (40.0, -100.0), (40.7, -74.0)]]
        alternative = [[(34.0, -118.0), (36.0, -100.0), (39.0, -90.0), (40.7, -74.0)]]
        cell_deg, cells = choose_grid(coast_to_coast + alternative)
        self.assertGreater(cell_deg, 0.25)
        self.assertLessEqual(len(cells), MAX_CELLS)


class LocationBudgetTests(SimpleTestCase):
    def test_a_three_route_corridor_stays_within_the_location_budget(self):
        routes = [
            [(32.78, -96.8), (32.5, -94.0), (33.0, -91.0), (32.3, -90.2), (33.0, -87.0), (33.75, -84.39)],
            [(32.78, -96.8), (34.5, -94.0), (35.1, -90.0), (34.0, -86.5), (33.75, -84.39)],
            [(32.78, -96.8), (33.0, -93.0), (33.4, -88.0), (33.75, -84.39)],
        ]
        cell_deg, cells = choose_grid(routes)
        self.assertLessEqual(len(cells), MAX_CELLS)
        self.assertLessEqual(cell_deg, 0.5)  # a ~900 mile trip keeps a reasonably fine grid

    def test_budget_is_well_under_the_providers_per_minute_limit(self):
        self.assertLessEqual(MAX_CELLS, 600 // 2)


class BuildHeatmapTests(SimpleTestCase):
    def test_hours_start_at_the_departure_hour_and_span_48_hours(self):
        weather = FakeWeather(lambda lat, lon: series_for(START, lambda h: 5.0))
        result = build_heatmap([LINE], DEPARTURE, 10_000, weather)
        self.assertEqual(result.start, START)  # 08:40 -> 08:00
        self.assertTrue(all(len(cell.risk) == HOURS for cell in result.cells))
        points, start, end = weather.calls[0]
        self.assertEqual((start, end), (START.date(), (START + timedelta(hours=48)).date()))
        self.assertEqual(len(points), len(result.cells))

    def test_risk_follows_the_forecast_hour_by_hour(self):
        # Wind ramps 1 mph per hour: Low until 24, Moderate 25-34, High 35-44, Severe 45-54, No Travel 55+.
        weather = FakeWeather(lambda lat, lon: series_for(START, lambda h: float(h)))
        result = build_heatmap([LINE], DEPARTURE, 10_000, weather)
        risk = result.cells[0].risk
        self.assertEqual(risk[0], RiskLevel.LOW)
        self.assertEqual(risk[24], RiskLevel.LOW)
        self.assertEqual(risk[25], RiskLevel.MODERATE)
        self.assertEqual(risk[35], RiskLevel.HIGH)
        self.assertEqual(risk[45], RiskLevel.SEVERE)
        self.assertEqual(len(risk), 49)

    def test_load_rules_apply_like_the_route_analysis(self):
        weather = FakeWeather(lambda lat, lon: series_for(START, lambda h: 40.0))
        light = build_heatmap([LINE], DEPARTURE, 20_000, weather).cells[0].risk[0]
        heavy = build_heatmap([LINE], DEPARTURE, 45_000, weather).cells[0].risk[0]
        self.assertEqual(light, RiskLevel.HIGH)
        self.assertEqual(heavy, RiskLevel.SEVERE)

    def test_hours_without_forecast_are_marked_unavailable(self):
        weather = FakeWeather(lambda lat, lon: series_for(START, lambda h: 5.0, hours=10))
        risk = build_heatmap([LINE], DEPARTURE, 10_000, weather).cells[0].risk
        self.assertEqual(risk[:10], [RiskLevel.LOW] * 10)
        self.assertEqual(risk[10:], [UNAVAILABLE] * 39)

    def test_weather_varies_by_cell(self):
        weather = FakeWeather(lambda lat, lon: series_for(START, lambda h: 60.0 if lon > -93 else 5.0))
        result = build_heatmap([LINE], DEPARTURE, 0, weather)
        west = [c for c in result.cells if c.lon <= -93]
        east = [c for c in result.cells if c.lon > -93]
        self.assertTrue(all(c.risk[0] == RiskLevel.LOW for c in west))
        self.assertTrue(all(c.risk[0] == RiskLevel.NO_TRAVEL for c in east))

    def test_cell_size_is_reported_in_miles(self):
        weather = FakeWeather(lambda lat, lon: series_for(START, lambda h: 5.0))
        result = build_heatmap([LINE], DEPARTURE, 0, weather)
        self.assertAlmostEqual(result.cell_miles, 0.25 * 69.0)


def calm(points, start, end):
    return [series_for(START, lambda h: 5.0)] * len(points)


class HeatmapViewTests(SimpleTestCase):
    BODY = {
        "routes": [[[32.0, -96.0], [32.0, -93.0], [32.0, -90.0]]],
        "departure_time": "2026-11-20T08:40:00Z",
        "load_weight_lb": 42000,
    }

    def post(self, body):
        return self.client.post("/api/heatmap/", body, content_type="application/json")

    @patch.object(OpenMeteoClient, "forecast", side_effect=calm)
    def test_success_shape(self, forecast):
        response = self.post(self.BODY)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["start_time"], "2026-11-20T08:00:00+00:00")
        self.assertEqual(body["hours"], 49)
        self.assertEqual(body["cell_miles"], 17.2)
        cell = body["cells"][0]
        self.assertEqual(set(cell), {"lat", "lon", "risk"})
        self.assertEqual(cell["risk"], [0] * 49)

    def test_rejects_invalid_input(self):
        for override in (
            {"routes": []},
            {"routes": [[]]},
            {"routes": [[[1.0]]]},
            {"routes": [[[95.0, 0.0]]]},
            {"routes": [[[0.0, 0.0]]] * 4},
            {"routes": "nope"},
            {"departure_time": "later"},
            {"load_weight_lb": -1},
        ):
            with self.subTest(override=override):
                self.assertEqual(self.post({**self.BODY, **override}).status_code, 400)

    def test_rejects_oversized_routes(self):
        huge = [[32.0, -96.0 + i * 0.001] for i in range(1501)]
        self.assertEqual(self.post({**self.BODY, "routes": [huge]}).status_code, 400)

    @patch.object(OpenMeteoClient, "forecast", side_effect=ForecastRangeError("out of range"))
    def test_forecast_range_is_422(self, _):
        response = self.post(self.BODY)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "out of range")

    @patch.object(OpenMeteoClient, "forecast", side_effect=WeatherUnavailableError("down"))
    def test_weather_outage_is_502(self, _):
        self.assertEqual(self.post(self.BODY).status_code, 502)

    @patch.object(OpenMeteoClient, "forecast", side_effect=WeatherRateLimitError("slow down"))
    def test_rate_limit_is_503_with_the_message(self, _):
        response = self.post(self.BODY)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "slow down")

    @override_settings(ORS_API_KEY="")
    @patch.object(OpenMeteoClient, "forecast", side_effect=calm)
    def test_does_not_need_the_routing_api_key(self, _):
        self.assertEqual(self.post(self.BODY).status_code, 200)
