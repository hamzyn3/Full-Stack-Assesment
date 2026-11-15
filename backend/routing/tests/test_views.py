from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from routing.services.ors import OrsClient, Place, RawRoute, RouteRequestError, UpstreamError
from routing.services.route_generation import Route
from routing.services.weather import (
    ForecastRangeError,
    HourlyWeather,
    OpenMeteoClient,
    WeatherRateLimitError,
    WeatherUnavailableError,
)

DEPARTURE = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)

VALID_BODY = {
    "origin": {"label": "Dallas, TX", "lat": 32.78, "lon": -96.8},
    "destination": {"label": "Atlanta, GA", "lat": 33.75, "lon": -84.39},
    "departure_time": "2026-11-20T08:00:00Z",
    "load_weight_lb": 42000,
}


def calm_series(wind=5.0, rain=0.0, hours=72):
    """Forecast series covering the test departure and the following days."""
    first = int(DEPARTURE.replace(hour=0).timestamp())
    return {first + i * 3600: HourlyWeather(wind, rain) for i in range(hours)}


class HealthTests(SimpleTestCase):
    def test_health_returns_ok(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


@override_settings(ORS_API_KEY="test-key")
class RoutesViewTests(SimpleTestCase):
    def post(self, body):
        return self.client.post("/api/routes/", body, content_type="application/json")

    def test_rejects_invalid_input(self):
        for override in (
            {"load_weight_lb": -5},
            {"load_weight_lb": "heavy"},
            {"departure_time": "tomorrow-ish"},
            {"origin": {"lat": 200, "lon": 0}},
            {"destination": ""},
        ):
            with self.subTest(override=override):
                response = self.post({**VALID_BODY, **override})
                self.assertEqual(response.status_code, 400)

    def test_missing_fields_rejected(self):
        self.assertEqual(self.post({}).status_code, 400)

    @override_settings(ORS_API_KEY="")
    def test_missing_api_key_is_503(self):
        response = self.post(VALID_BODY)
        self.assertEqual(response.status_code, 503)
        self.assertIn("ORS_API_KEY", response.json()["error"])

    @patch.object(OpenMeteoClient, "forecast", side_effect=lambda points, start, end: [calm_series()] * len(points))
    @patch("routing.views.generate_routes")
    def test_success_shape(self, generate, forecast):
        generate.return_value = [
            Route("route-1", "Route 1", [(32.78, -96.8), (33.75, -84.39)], 783.4, 50760),
            Route("route-2", "Route 2", [(32.78, -96.8), (34.0, -90.0), (33.75, -84.39)], 860.0, 55000),
        ]
        response = self.post(VALID_BODY)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["origin"]["label"], "Dallas, TX")
        self.assertEqual(body["load_weight_lb"], 42000)
        self.assertEqual(body["departure_time"], "2026-11-20T08:00:00+00:00")
        self.assertEqual(body["checkpoint_interval_miles"], 25)  # default
        self.assertEqual(body["recommendation"]["route_id"], "route-1")
        self.assertFalse(body["recommendation"]["all_routes_blocked"])

        first, second = body["routes"]
        self.assertEqual((first["rank"], first["recommended"]), (1, True))
        self.assertEqual((second["rank"], second["recommended"]), (2, False))
        self.assertEqual(first["geometry"], [[32.78, -96.8], [33.75, -84.39]])
        self.assertEqual(first["distance_miles"], 783.4)
        self.assertEqual(first["duration_seconds"], 50760)
        self.assertEqual(first["arrival_time"], "2026-11-20T22:06:00+00:00")
        self.assertEqual(first["max_risk"], "low")
        self.assertEqual(first["miles_by_risk"]["low"], 783.4)
        self.assertEqual(set(first["miles_by_risk"]), {"low", "moderate", "high", "severe", "no_travel"})

        checkpoint = first["checkpoints"][1]
        self.assertEqual(
            set(checkpoint),
            {"index", "mile", "lat", "lon", "eta", "segment_miles", "wind_mph", "rain_in_hr", "risk"},
        )
        self.assertEqual(checkpoint["mile"], 25)
        self.assertEqual(checkpoint["risk"], "low")
        self.assertEqual(len(first["checkpoints"]), 33)  # 0, 25, ..., 775, 783.4

    @patch.object(OpenMeteoClient, "forecast", side_effect=lambda points, start, end: [calm_series()] * len(points))
    @patch("routing.views.generate_routes")
    def test_interval_option_and_validation(self, generate, forecast):
        generate.return_value = [Route("route-1", "Route 1", [(32.78, -96.8), (33.75, -84.39)], 100.0, 6000)]
        body = self.post({**VALID_BODY, "checkpoint_interval_miles": 50}).json()
        self.assertEqual(body["checkpoint_interval_miles"], 50)
        self.assertEqual([c["mile"] for c in body["routes"][0]["checkpoints"]], [0, 50, 100])
        self.assertEqual(self.post({**VALID_BODY, "checkpoint_interval_miles": 15}).status_code, 400)

    @patch.object(OpenMeteoClient, "forecast")
    @patch("routing.views.generate_routes")
    def test_severe_weather_changes_the_recommendation(self, generate, forecast):
        # Route 1 is faster but runs into 50 mph wind (No Travel for a 42,000 lb load); route 2 is calm.
        generate.return_value = [
            Route("route-1", "Route 1", [(32.0, -96.0), (32.0, -90.0)], 100.0, 6000),
            Route("route-2", "Route 2", [(32.0, -96.0), (34.0, -93.0), (32.0, -90.0)], 120.0, 7000),
        ]
        forecast.side_effect = lambda points, start, end: [
            calm_series(wind=50.0) if lat == 32.0 and -95.0 < lon < -91.0 else calm_series() for lat, lon in points
        ]
        body = self.post({**VALID_BODY, "checkpoint_interval_miles": 10}).json()
        self.assertEqual(body["recommendation"]["route_id"], "route-2")
        by_id = {r["id"]: r for r in body["routes"]}
        self.assertTrue(by_id["route-1"]["has_no_travel"])
        self.assertEqual(by_id["route-1"]["max_risk"], "no_travel")
        self.assertFalse(by_id["route-2"]["has_no_travel"])
        self.assertEqual(body["routes"][0]["id"], "route-2")

    @patch.object(OpenMeteoClient, "forecast", side_effect=ForecastRangeError("out of range"))
    @patch("routing.views.generate_routes")
    def test_forecast_out_of_range_is_422(self, generate, forecast):
        generate.return_value = [Route("route-1", "Route 1", [(32.78, -96.8), (33.75, -84.39)], 100.0, 6000)]
        response = self.post(VALID_BODY)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "out of range")

    @patch.object(OpenMeteoClient, "forecast", side_effect=WeatherRateLimitError("rate limited"))
    @patch("routing.views.generate_routes")
    def test_weather_rate_limit_is_503(self, generate, forecast):
        generate.return_value = [Route("route-1", "Route 1", [(32.78, -96.8), (33.75, -84.39)], 100.0, 6000)]
        response = self.post(VALID_BODY)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "rate limited")

    @patch.object(OpenMeteoClient, "forecast", side_effect=WeatherUnavailableError("weather down"))
    @patch("routing.views.generate_routes")
    def test_weather_outage_is_502(self, generate, forecast):
        generate.return_value = [Route("route-1", "Route 1", [(32.78, -96.8), (33.75, -84.39)], 100.0, 6000)]
        self.assertEqual(self.post(VALID_BODY).status_code, 502)

    @patch("routing.views.generate_routes", return_value=[])
    def test_no_routes_is_422(self, _):
        self.assertEqual(self.post(VALID_BODY).status_code, 422)

    @patch("routing.views.generate_routes", side_effect=UpstreamError("down"))
    def test_upstream_failure_is_502(self, _):
        response = self.post(VALID_BODY)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], "down")

    @patch("routing.views.generate_routes", side_effect=RouteRequestError("no routable point"))
    def test_rejected_request_is_422(self, _):
        self.assertEqual(self.post(VALID_BODY).status_code, 422)

    @patch("routing.views.generate_routes", return_value=[])
    @patch.object(OrsClient, "search", return_value=[Place("Dallas, TX, USA", 32.78, -96.8)])
    def test_text_places_are_geocoded(self, search, _):
        self.post({**VALID_BODY, "origin": "Dallas", "destination": "Atlanta"})
        self.assertEqual(search.call_count, 2)
        self.assertEqual(search.call_args.kwargs, {"size": 1, "autocomplete": False})

    @patch.object(OrsClient, "search", return_value=[])
    def test_unknown_text_place_is_422(self, _):
        response = self.post({**VALID_BODY, "origin": "zzzzzz"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("origin", response.json()["error"])


@override_settings(ORS_API_KEY="test-key")
class GeocodeViewTests(SimpleTestCase):
    def test_short_query_returns_empty_without_calling_provider(self):
        with patch.object(OrsClient, "search") as search:
            response = self.client.get("/api/geocode/?q=ab")
        self.assertEqual(response.json(), {"results": []})
        search.assert_not_called()

    @patch.object(OrsClient, "search", return_value=[Place("Dallas, TX, USA", 32.78, -96.8)])
    def test_returns_places(self, _):
        response = self.client.get("/api/geocode/?q=dallas")
        self.assertEqual(response.json(), {"results": [{"label": "Dallas, TX, USA", "lat": 32.78, "lon": -96.8}]})

    @patch.object(OrsClient, "search", side_effect=UpstreamError("down"))
    def test_upstream_failure_is_502(self, _):
        self.assertEqual(self.client.get("/api/geocode/?q=dallas").status_code, 502)


@override_settings(ORS_API_KEY="test-key", ORS_BASE_URL="https://ors.test")
class OrsClientTests(SimpleTestCase):
    def response(self, status_code=200, payload=None):
        mock = MagicMock(status_code=status_code)
        mock.json.return_value = payload if payload is not None else {}
        return mock

    @patch("routing.services.ors.requests.request")
    def test_directions_parses_geojson(self, request):
        request.return_value = self.response(
            payload={
                "features": [
                    {
                        "properties": {"summary": {"distance": 1609.344 * 10, "duration": 600}},
                        "geometry": {"coordinates": [[-96.8, 32.78], [-96.7, 32.9]]},
                    }
                ]
            }
        )
        routes = OrsClient().directions([(32.78, -96.8), (32.9, -96.7)], alternatives=3)
        self.assertEqual(routes[0].geometry, [(32.78, -96.8), (32.9, -96.7)])
        self.assertAlmostEqual(routes[0].distance_miles, 10.0)
        self.assertEqual(routes[0].duration_seconds, 600)
        _, kwargs = request.call_args
        self.assertEqual(kwargs["json"]["coordinates"], [[-96.8, 32.78], [-96.7, 32.9]])
        self.assertEqual(kwargs["json"]["alternative_routes"]["target_count"], 3)
        self.assertEqual(kwargs["headers"], {"Authorization": "test-key"})

    @patch("routing.services.ors.requests.request")
    def test_status_codes_map_to_error_types(self, request):
        cases = {
            400: RouteRequestError,
            404: RouteRequestError,
            401: UpstreamError,
            429: UpstreamError,
            503: UpstreamError,
        }
        for status_code, error_type in cases.items():
            with self.subTest(status_code=status_code):
                request.return_value = self.response(status_code, {"error": {"message": "nope"}})
                with self.assertRaises(error_type):
                    OrsClient().search("dallas")

    @patch("routing.services.ors.requests.request")
    def test_search_parses_features(self, request):
        request.return_value = self.response(
            payload={
                "features": [
                    {"geometry": {"coordinates": [-96.8, 32.78]}, "properties": {"label": "Dallas, TX, USA"}}
                ]
            }
        )
        self.assertEqual(OrsClient().search("dallas"), [Place("Dallas, TX, USA", 32.78, -96.8)])
