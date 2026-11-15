"""Turn routes into weather-risk analyses and pick the recommended one."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .checkpoints import Checkpoint, build_checkpoints
from .risk import RiskLevel, classify
from .route_generation import Route
from .weather import OpenMeteoClient, weather_at


@dataclass(frozen=True)
class CheckpointResult:
    checkpoint: Checkpoint
    wind_mph: float
    rain_in_hr: float
    risk: RiskLevel


@dataclass(frozen=True)
class RouteAnalysis:
    route: Route
    checkpoints: list[CheckpointResult]
    miles_by_risk: dict[RiskLevel, float]
    average_risk: float  # mile-weighted mean of RiskLevel values (0 = low ... 4 = no travel)
    max_risk: RiskLevel

    @property
    def has_no_travel(self) -> bool:
        return self.miles_by_risk[RiskLevel.NO_TRAVEL] > 0


def summarize(route: Route, results: list[CheckpointResult]) -> RouteAnalysis:
    miles_by_risk = {level: 0.0 for level in RiskLevel}
    for result in results:
        miles_by_risk[result.risk] += result.checkpoint.segment_miles
    total = sum(miles_by_risk.values())
    average = sum(level * miles for level, miles in miles_by_risk.items()) / total if total > 0 else 0.0
    return RouteAnalysis(
        route=route,
        checkpoints=results,
        miles_by_risk=miles_by_risk,
        average_risk=average,
        max_risk=max((r.risk for r in results), default=RiskLevel.LOW),
    )


def analyze_routes(
    routes: list[Route],
    departure: datetime,
    load_weight_lb: float,
    interval_miles: float,
    weather: OpenMeteoClient,
) -> list[RouteAnalysis]:
    """Sample each route, fetch the weather at each ETA and classify the risk."""
    departure = departure.astimezone(timezone.utc)
    all_checkpoints = [
        build_checkpoints(r.geometry, r.distance_miles, r.duration_seconds, departure, interval_miles) for r in routes
    ]

    flat = [c for checkpoints in all_checkpoints for c in checkpoints]
    start = departure.date()
    end = (max(c.eta for c in flat) + timedelta(minutes=30)).date()
    series = iter(weather.forecast([(c.lat, c.lon) for c in flat], start, end))

    analyses = []
    for route, checkpoints in zip(routes, all_checkpoints):
        results = []
        for checkpoint in checkpoints:
            hourly = weather_at(next(series), checkpoint.eta)
            results.append(
                CheckpointResult(
                    checkpoint=checkpoint,
                    wind_mph=hourly.wind_mph,
                    rain_in_hr=hourly.rain_in_hr,
                    risk=classify(hourly.wind_mph, hourly.rain_in_hr, load_weight_lb),
                )
            )
        analyses.append(summarize(route, results))
    return analyses
