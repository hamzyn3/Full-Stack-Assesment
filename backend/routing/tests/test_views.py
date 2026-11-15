from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from routing.services.ors import OrsClient, Place, RawRoute, RouteRequestError, UpstreamError

VALID_BODY = {
    "origin": {"label": "Dallas, TX", "lat": 32.78, "lon": -96.8},
    "destination": {"label": "Atlanta, GA", "lat": 33.75, "lon": -84.39},
    "departure_time": "2026-11-20T08:00:00Z",
    "load_weight_lb": 42000,
}


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

    @patch("routing.views.generate_routes")
    def test_success_shape(self, generate):
        from routing.services.route_generation import Route

        generate.return_value = [
            Route("route-1", "Route 1", [(32.78, -96.8), (33.75, -84.39)], 783.4, 50760),
        ]
        response = self.post(VALID_BODY)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["origin"]["label"], "Dallas, TX")
        self.assertEqual(body["load_weight_lb"], 42000)
        self.assertEqual(body["departure_time"], "2026-11-20T08:00:00+00:00")
        route = body["routes"][0]
        self.assertEqual(route["geometry"], [[32.78, -96.8], [33.75, -84.39]])
        self.assertEqual(route["distance_miles"], 783.4)
        self.assertEqual(route["duration_seconds"], 50760)

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
