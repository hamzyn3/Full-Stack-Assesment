"""Hourly weather-risk grid along the trip corridor, for the heatmap slider.

The corridor is every grid cell touched by (or next to) any route. Each cell
gets one risk value per hour for the 49 hours from the departure hour (+0h) to
+48h, using the same classifier and load rules as the route analysis, so the
heatmap can never disagree with the route risk levels.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .geo import Point, densify
from .risk import classify
from .weather import OpenMeteoClient

HOURS = 49  # +0h ... +48h inclusive
UNAVAILABLE = -1  # no forecast for that hour

SAMPLE_SPACING_MILES = 10
# Cell sizes to try, finest first; coarser ones keep long-haul trips under MAX_CELLS.
GRID_STEPS_DEG = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
# Open-Meteo's free tier allows 600 locations per minute and every grid cell costs one. Route analysis already
# uses roughly 100-260 (25 or 10 mile checkpoints), so the heatmap is capped well below the budget.
MAX_CELLS = 200
MILES_PER_DEGREE = 69.0


@dataclass(frozen=True)
class HeatCell:
    lat: float
    lon: float
    risk: list[int]  # RiskLevel value per hour, or UNAVAILABLE


@dataclass(frozen=True)
class Heatmap:
    start: datetime  # UTC, on the hour: the departure hour (+0h)
    cell_miles: float
    cells: list[HeatCell]


def corridor_cells(routes: list[list[Point]], cell_deg: float) -> list[Point]:
    """Centres of the grid cells covering the routes plus one cell either side."""
    occupied: set[tuple[int, int]] = set()
    for geometry in routes:
        for lat, lon in densify(geometry, SAMPLE_SPACING_MILES):
            row, col = math.floor(lat / cell_deg), math.floor(lon / cell_deg)
            for d_row in (-1, 0, 1):
                for d_col in (-1, 0, 1):
                    occupied.add((row + d_row, col + d_col))
    return [((row + 0.5) * cell_deg, (col + 0.5) * cell_deg) for row, col in sorted(occupied)]


def choose_grid(routes: list[list[Point]]) -> tuple[float, list[Point]]:
    """Finest grid whose corridor stays within MAX_CELLS."""
    for cell_deg in GRID_STEPS_DEG:
        centres = corridor_cells(routes, cell_deg)
        if len(centres) <= MAX_CELLS:
            return cell_deg, centres
    return cell_deg, centres  # coarsest grid, even if still large


def build_heatmap(
    routes: list[list[Point]],
    departure: datetime,
    load_weight_lb: float,
    weather: OpenMeteoClient,
) -> Heatmap:
    start = departure.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    last = start + timedelta(hours=HOURS - 1)
    cell_deg, centres = choose_grid(routes)

    series_per_cell = weather.forecast(centres, start.date(), last.date())
    timestamps = [int((start + timedelta(hours=h)).timestamp()) for h in range(HOURS)]

    cells = []
    for (lat, lon), series in zip(centres, series_per_cell):
        risk = []
        for ts in timestamps:
            hourly = series.get(ts)
            risk.append(UNAVAILABLE if hourly is None else int(classify(hourly.wind_mph, hourly.rain_in_hr, load_weight_lb)))
        cells.append(HeatCell(lat=lat, lon=lon, risk=risk))

    return Heatmap(start=start, cell_miles=cell_deg * MILES_PER_DEGREE, cells=cells)
