"""Place weather-sampling checkpoints along a route and estimate arrival times."""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta

from .geo import Point, haversine_miles

# A final checkpoint is only added at the destination if it is further than this
# from the last regular checkpoint.
MIN_TAIL_MILES = 0.5


@dataclass(frozen=True)
class Checkpoint:
    index: int
    mile: float  # distance from the origin along the route
    lat: float
    lon: float
    eta: datetime
    segment_miles: float  # stretch of road this checkpoint's weather is applied to


def checkpoint_miles(total_miles: float, interval_miles: float) -> list[float]:
    """Mile marks: 0, interval, 2*interval, ... and the destination."""
    miles = [0.0]
    if total_miles <= 0:
        return miles
    mark = interval_miles
    while mark < total_miles - MIN_TAIL_MILES:
        miles.append(mark)
        mark += interval_miles
    if total_miles - miles[-1] > MIN_TAIL_MILES:
        miles.append(total_miles)
    return miles


def segment_lengths(miles: list[float], total_miles: float) -> list[float]:
    """Split the route at the midpoints between checkpoints.

    Each checkpoint owns the road around it, so the lengths sum to the route length.
    """
    if total_miles <= 0:
        return [0.0] * len(miles)
    bounds = [0.0] + [(a + b) / 2 for a, b in zip(miles, miles[1:])] + [total_miles]
    return [bounds[i + 1] - bounds[i] for i in range(len(miles))]


def _position_at(geometry: list[Point], cumulative: list[float], target: float) -> Point:
    """Point at ``target`` miles (haversine measure) along the polyline."""
    if target <= 0:
        return geometry[0]
    if target >= cumulative[-1]:
        return geometry[-1]
    i = bisect_right(cumulative, target) - 1
    span = cumulative[i + 1] - cumulative[i]
    fraction = (target - cumulative[i]) / span if span else 0.0
    a, b = geometry[i], geometry[i + 1]
    return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)


def build_checkpoints(
    geometry: list[Point],
    total_miles: float,
    duration_seconds: float,
    departure: datetime,
    interval_miles: float,
) -> list[Checkpoint]:
    """Checkpoints every ``interval_miles`` with ETAs.

    The truck is assumed to travel at the route's average speed, so the ETA at
    a checkpoint is the departure plus the share of the total duration that
    matches its share of the total distance.
    """
    cumulative = [0.0]
    for a, b in zip(geometry, geometry[1:]):
        cumulative.append(cumulative[-1] + haversine_miles(a, b))
    geometry_miles = cumulative[-1]

    miles = checkpoint_miles(total_miles, interval_miles)
    segments = segment_lengths(miles, total_miles)

    checkpoints = []
    for index, (mile, segment) in enumerate(zip(miles, segments)):
        share = mile / total_miles if total_miles > 0 else 0.0
        # The provider's distance and the polyline length differ slightly; use the share.
        lat, lon = _position_at(geometry, cumulative, share * geometry_miles)
        checkpoints.append(
            Checkpoint(
                index=index,
                mile=round(mile, 2),
                lat=lat,
                lon=lon,
                eta=departure + timedelta(seconds=duration_seconds * share),
                segment_miles=segment,
            )
        )
    return checkpoints
