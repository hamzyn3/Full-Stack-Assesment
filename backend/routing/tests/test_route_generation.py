from django.test import SimpleTestCase

from routing.services.ors import RawRoute, RouteRequestError
from routing.services.route_generation import generate_routes

ORIGIN = (0.0, 0.0)
DESTINATION = (0.0, 2.0)


def raw(path, seconds):
    return RawRoute(geometry=path, distance_miles=100.0, duration_seconds=seconds)


STRAIGHT = raw([(0, 0), (0, 2)], 7200)
NORTH = raw([(0, 0), (0.5, 1), (0, 2)], 8000)
SOUTH = raw([(0, 0), (-0.5, 1), (0, 2)], 8600)
SLOW_DETOUR = raw([(0, 0), (-1.5, 1), (0, 2)], 7200 * 2)


class FakeClient:
    """Stands in for OrsClient; ``plain`` answers every non-alternatives call in order."""

    def __init__(self, alternatives, plain=(), alternatives_error=None):
        self.alternatives = alternatives
        self.plain = list(plain)
        self.alternatives_error = alternatives_error
        self.calls = []

    def directions(self, waypoints, alternatives=0):
        self.calls.append((len(waypoints), alternatives))
        if alternatives:
            if self.alternatives_error:
                raise self.alternatives_error
            return list(self.alternatives)
        if not self.plain:
            raise RouteRequestError("no more routes")
        item = self.plain.pop(0)
        if isinstance(item, Exception):
            raise item
        return [item]


class GenerateRoutesTests(SimpleTestCase):
    def test_three_alternatives_need_no_extra_calls(self):
        client = FakeClient([SOUTH, STRAIGHT, NORTH])
        routes = generate_routes(client, ORIGIN, DESTINATION)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual([r.id for r in routes], ["route-1", "route-2", "route-3"])
        self.assertEqual([r.duration_seconds for r in routes], [7200, 8000, 8600])

    def test_tops_up_with_via_point_routes_when_alternatives_unavailable(self):
        client = FakeClient([], plain=[STRAIGHT, NORTH, SOUTH], alternatives_error=RouteRequestError("limit"))
        routes = generate_routes(client, ORIGIN, DESTINATION)
        self.assertEqual(len(routes), 3)
        # alternatives attempt, single-route retry, then via-point calls (3 waypoints).
        self.assertEqual(client.calls[0], (2, 3))
        self.assertEqual(client.calls[1], (2, 0))
        self.assertTrue(all(call == (3, 0) for call in client.calls[2:]))

    def test_duplicates_are_dropped(self):
        duplicate = raw([(0, 0), (0, 2)], 7300)
        client = FakeClient([STRAIGHT, duplicate], plain=[], alternatives_error=None)
        routes = generate_routes(client, ORIGIN, DESTINATION)
        self.assertEqual(len(routes), 1)

    def test_slow_detours_are_dropped(self):
        client = FakeClient([STRAIGHT, SLOW_DETOUR])
        routes = generate_routes(client, ORIGIN, DESTINATION)
        self.assertEqual(len(routes), 1)

    def test_failed_via_routes_are_skipped(self):
        client = FakeClient(
            [STRAIGHT],
            plain=[RouteRequestError("unroutable"), NORTH, RouteRequestError("unroutable"), SOUTH],
        )
        routes = generate_routes(client, ORIGIN, DESTINATION)
        self.assertEqual(len(routes), 3)

    def test_returns_fewer_when_only_one_distinct_route_exists(self):
        client = FakeClient([STRAIGHT])
        routes = generate_routes(client, ORIGIN, DESTINATION)
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].name, "Route 1")

    def test_plain_retry_failure_propagates(self):
        client = FakeClient([], plain=[RouteRequestError("no route")], alternatives_error=RouteRequestError("limit"))
        with self.assertRaises(RouteRequestError):
            generate_routes(client, ORIGIN, DESTINATION)
