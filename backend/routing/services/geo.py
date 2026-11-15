"""Small geometry helpers. Points are (lat, lon) tuples in degrees."""

import math

Point = tuple[float, float]

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(a: Point, b: Point) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


def densify(points: list[Point], step_miles: float) -> list[Point]:
    """Insert points so consecutive points are at most ``step_miles`` apart."""
    if not points:
        return []
    dense = [points[0]]
    for start, end in zip(points, points[1:]):
        gap = haversine_miles(start, end)
        pieces = max(1, math.ceil(gap / step_miles))
        for i in range(1, pieces + 1):
            fraction = i / pieces
            dense.append((start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction))
    return dense


def _cell(point: Point, cell_deg: float) -> tuple[int, int]:
    return math.floor(point[0] / cell_deg), math.floor(point[1] / cell_deg)


def path_overlap(a: list[Point], b: list[Point], step_miles: float = 0.5, cell_deg: float = 0.02) -> float:
    """Fraction (0-1) of the shorter path that lies on the other path.

    Both paths are densified, then each point of the shorter path is checked
    against the grid cells (and their neighbours) occupied by the longer one.
    """
    dense_a, dense_b = densify(a, step_miles), densify(b, step_miles)
    if not dense_a or not dense_b:
        return 0.0
    shorter, longer = (dense_a, dense_b) if len(dense_a) <= len(dense_b) else (dense_b, dense_a)
    occupied = {_cell(p, cell_deg) for p in longer}
    shared = 0
    for point in shorter:
        row, col = _cell(point, cell_deg)
        if any((row + dr, col + dc) in occupied for dr in (-1, 0, 1) for dc in (-1, 0, 1)):
            shared += 1
    return shared / len(shorter)


def offset_midpoint(origin: Point, destination: Point, fraction: float) -> Point:
    """Midpoint of origin->destination, shifted sideways.

    ``fraction`` is the sideways distance as a share of the straight-line
    distance; positive and negative values go to opposite sides.
    """
    mid_lat = (origin[0] + destination[0]) / 2
    mid_lon = (origin[1] + destination[1]) / 2
    cos_lat = max(math.cos(math.radians(mid_lat)), 1e-6)

    # Direction vector in a locally flat (x=east, y=north) frame, then its perpendicular.
    dx = (destination[1] - origin[1]) * cos_lat
    dy = destination[0] - origin[0]
    length = math.hypot(dx, dy)
    if length == 0:
        return (mid_lat, mid_lon)
    perp_x, perp_y = -dy / length, dx / length

    shift_deg = fraction * haversine_miles(origin, destination) / 69.0
    return (mid_lat + perp_y * shift_deg, mid_lon + perp_x * shift_deg / cos_lat)
