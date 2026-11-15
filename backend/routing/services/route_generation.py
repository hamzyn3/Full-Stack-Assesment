"""Produce up to three distinct truck routes between two places.

ORS alternative routes are limited to short trips, so when it returns fewer
than three distinct routes we ask for routes through sideways-offset via
points and keep the ones that are genuinely different and not absurd detours.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .geo import Point, haversine_miles, offset_midpoint, path_overlap
from .ors import OrsClient, RawRoute, RouteRequestError

logger = logging.getLogger(__name__)

TARGET_ROUTES = 3
# Two routes sharing more than this fraction of their path count as duplicates.
MAX_OVERLAP = 0.85
# Routes slower than this multiple of the fastest are rejected as detours.
MAX_DURATION_RATIO = 1.5
# Sideways via-point offsets, as a fraction of the straight-line distance.
VIA_OFFSETS = (0.12, -0.12, 0.25, -0.25)


@dataclass(frozen=True)
class Route:
    id: str
    name: str
    geometry: list[Point]
    distance_miles: float
    duration_seconds: float


def generate_routes(client: OrsClient, origin: Point, destination: Point) -> list[Route]:
    candidates = _initial_candidates(client, origin, destination)

    if len(_select(candidates)) < TARGET_ROUTES and haversine_miles(origin, destination) > 0.5:
        candidates.extend(_via_point_candidates(client, origin, destination))

    selected = _select(candidates)
    return [
        Route(
            id=f"route-{i}",
            name=f"Route {i}",
            geometry=route.geometry,
            distance_miles=round(route.distance_miles, 1),
            duration_seconds=round(route.duration_seconds),
        )
        for i, route in enumerate(selected, start=1)
    ]


def _initial_candidates(client: OrsClient, origin: Point, destination: Point) -> list[RawRoute]:
    try:
        return list(client.directions([origin, destination], alternatives=TARGET_ROUTES))
    except RouteRequestError as exc:
        # Typically the alternative-route distance limit; retry for a single route.
        logger.info("Alternatives unavailable (%s); requesting a single route.", exc)
        return list(client.directions([origin, destination]))


def _via_point_candidates(client: OrsClient, origin: Point, destination: Point) -> list[RawRoute]:
    """Routes through each sideways-offset via point, requested in parallel.

    The requests are independent, so running them together takes about as long
    as one. A via point that cannot be routed is skipped.
    """
    via_points = [offset_midpoint(origin, destination, fraction) for fraction in VIA_OFFSETS]

    def fetch(via: Point) -> list[RawRoute]:
        try:
            return list(client.directions([origin, via, destination]))
        except RouteRequestError as exc:
            logger.info("Via-point route skipped: %s", exc)
            return []

    with ThreadPoolExecutor(max_workers=len(via_points)) as pool:
        return [route for routes in pool.map(fetch, via_points) for route in routes]


def _select(candidates: list[RawRoute]) -> list[RawRoute]:
    """Fastest first, dropping detours and near-duplicates, capped at three."""
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda r: r.duration_seconds)
    fastest = ordered[0].duration_seconds
    selected: list[RawRoute] = []
    for route in ordered:
        if route.duration_seconds > fastest * MAX_DURATION_RATIO:
            continue
        if any(path_overlap(route.geometry, kept.geometry) > MAX_OVERLAP for kept in selected):
            continue
        selected.append(route)
        if len(selected) == TARGET_ROUTES:
            break
    return selected
