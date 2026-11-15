"""Hourly wind and rain forecasts from Open-Meteo (free, no API key)."""

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime

import requests
from django.conf import settings
from django.core.cache import cache

from .geo import Point

BATCH_SIZE = 50
CACHE_SECONDS = 30 * 60
TIMEOUT_SECONDS = 20
MAX_WORKERS = 4


class WeatherError(Exception):
    """Base class for weather failures."""


class WeatherUnavailableError(WeatherError):
    """Network failure, 5xx, or missing data for a requested hour."""


class WeatherRateLimitError(WeatherUnavailableError):
    """The weather provider is rate limiting us (HTTP 429)."""


class ForecastRangeError(WeatherError):
    """The requested dates are outside what the forecast API serves."""


@dataclass(frozen=True)
class HourlyWeather:
    wind_mph: float
    rain_in_hr: float


# Unix timestamp (UTC, on the hour) -> weather for that hour.
Series = dict[int, HourlyWeather]


def weather_at(series: Series, when: datetime) -> HourlyWeather:
    """Forecast for the hour nearest to ``when``."""
    hour = math.floor((when.timestamp() + 1800) / 3600) * 3600
    try:
        return series[hour]
    except KeyError:
        raise WeatherUnavailableError("The forecast does not cover the full trip.") from None


class OpenMeteoClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.WEATHER_BASE_URL

    def forecast(self, points: list[Point], start: date, end: date) -> list[Series]:
        """One hourly series per point, in the same order as ``points``.

        Coordinates are rounded to 2 decimals (~0.7 mi), de-duplicated, fetched
        in parallel batches, and cached so overlapping routes share requests.
        """
        keys = [(round(lat, 2), round(lon, 2)) for lat, lon in points]
        found: dict[tuple[float, float], Series] = {}
        missing = []
        for key in dict.fromkeys(keys):
            cached = cache.get(_cache_key(key, start, end))
            if cached is not None:
                found[key] = cached
            else:
                missing.append(key)

        batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        if batches:
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batches))) as pool:
                results = list(pool.map(lambda batch: self._fetch_batch(batch, start, end), batches))
            for batch, series_list in zip(batches, results):
                for key, series in zip(batch, series_list):
                    found[key] = series
                    cache.set(_cache_key(key, start, end), series, CACHE_SECONDS)

        return [found[key] for key in keys]

    def _fetch_batch(self, batch: list[tuple[float, float]], start: date, end: date) -> list[Series]:
        params = {
            "latitude": ",".join(str(lat) for lat, _ in batch),
            "longitude": ",".join(str(lon) for _, lon in batch),
            "hourly": "wind_speed_10m,precipitation",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "UTC",
            "timeformat": "unixtime",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise WeatherUnavailableError(f"Could not reach the weather provider: {exc}") from exc

        if response.status_code == 429:
            raise WeatherRateLimitError("The weather provider's rate limit was reached. Wait a minute and try again.")
        if response.status_code == 400:
            raise ForecastRangeError(_reason(response))
        if response.status_code != 200:
            raise WeatherUnavailableError(f"The weather provider failed ({response.status_code}).")

        try:
            payload = response.json()
        except ValueError as exc:
            raise WeatherUnavailableError("The weather provider returned an invalid response.") from exc
        if isinstance(payload, dict):  # a single location comes back as an object
            payload = [payload]
        if len(payload) != len(batch):
            raise WeatherUnavailableError("The weather provider returned an unexpected number of locations.")
        return [_parse_hourly(item) for item in payload]


def _parse_hourly(item: dict) -> Series:
    try:
        hourly = item["hourly"]
        times, winds, rains = hourly["time"], hourly["wind_speed_10m"], hourly["precipitation"]
    except (KeyError, TypeError) as exc:
        raise WeatherUnavailableError("The weather provider returned incomplete data.") from exc
    return {
        int(t): HourlyWeather(wind_mph=float(w), rain_in_hr=float(r))
        for t, w, r in zip(times, winds, rains)
        if w is not None and r is not None
    }


def _reason(response: requests.Response) -> str:
    try:
        return str(response.json().get("reason", "The forecast is unavailable for those dates."))
    except ValueError:
        return "The forecast is unavailable for those dates."


def _cache_key(key: tuple[float, float], start: date, end: date) -> str:
    return f"wx:{key[0]}:{key[1]}:{start.isoformat()}:{end.isoformat()}"
