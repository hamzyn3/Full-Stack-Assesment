"""Client for the OpenRouteService geocoding and directions APIs."""

from dataclasses import dataclass

import requests
from django.conf import settings

from .geo import Point

TIMEOUT_SECONDS = 25
METERS_PER_MILE = 1609.344


class OrsError(Exception):
    """Base class for provider failures."""


class NotConfiguredError(OrsError):
    """The ORS API key is missing."""


class UpstreamError(OrsError):
    """Network failure, auth failure, rate limit or a 5xx from ORS."""


class RouteRequestError(OrsError):
    """ORS rejected the request (e.g. no routable point, distance limit)."""


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RawRoute:
    geometry: list[Point]  # (lat, lon)
    distance_miles: float
    duration_seconds: float


class OrsClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else settings.ORS_API_KEY
        self.base_url = (base_url or settings.ORS_BASE_URL).rstrip("/")
        if not self.api_key:
            raise NotConfiguredError("ORS_API_KEY is not configured on the server.")

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": self.api_key},
                timeout=TIMEOUT_SECONDS,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise UpstreamError(f"Could not reach the routing provider: {exc}") from exc

        if response.status_code in (401, 403):
            raise UpstreamError("The routing provider rejected the API key.")
        if response.status_code == 429:
            raise UpstreamError("The routing provider rate limit was reached. Try again shortly.")
        if 400 <= response.status_code < 500:
            raise RouteRequestError(_error_message(response))
        if response.status_code >= 500:
            raise UpstreamError(f"The routing provider failed ({response.status_code}).")
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamError("The routing provider returned an invalid response.") from exc

    def search(self, text: str, size: int = 5, autocomplete: bool = True) -> list[Place]:
        endpoint = "/geocode/autocomplete" if autocomplete else "/geocode/search"
        data = self._request("GET", endpoint, params={"text": text, "size": size})
        places = []
        for feature in data.get("features", []):
            lon, lat = feature["geometry"]["coordinates"][:2]
            label = feature.get("properties", {}).get("label") or f"{lat:.4f}, {lon:.4f}"
            places.append(Place(label=label, lat=lat, lon=lon))
        return places

    def directions(self, waypoints: list[Point], alternatives: int = 0) -> list[RawRoute]:
        """Truck (driving-hgv) routes through ``waypoints`` given as (lat, lon).

        ``alternatives`` > 0 asks ORS for that many routes; ORS limits this to
        short trips and two waypoints, so callers must handle RouteRequestError.
        """
        body: dict = {
            "coordinates": [[lon, lat] for lat, lon in waypoints],
            "instructions": False,
            # -1 = snap to the nearest road at any distance (needed for via points).
            "radiuses": [-1] * len(waypoints),
        }
        if alternatives > 1:
            body["alternative_routes"] = {"target_count": alternatives, "share_factor": 0.6, "weight_factor": 1.6}

        data = self._request("POST", "/v2/directions/driving-hgv/geojson", json=body)
        routes = []
        for feature in data.get("features", []):
            summary = feature["properties"]["summary"]
            geometry = [(lat, lon) for lon, lat, *_ in feature["geometry"]["coordinates"]]
            routes.append(
                RawRoute(
                    geometry=geometry,
                    distance_miles=summary["distance"] / METERS_PER_MILE,
                    duration_seconds=summary["duration"],
                )
            )
        return routes


def _error_message(response: requests.Response) -> str:
    try:
        error = response.json().get("error")
        if isinstance(error, dict):
            return error.get("message", "The routing provider rejected the request.")
        if isinstance(error, str):
            return error
    except ValueError:
        pass
    return "The routing provider rejected the request."
