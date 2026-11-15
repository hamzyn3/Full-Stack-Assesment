from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import RouteRequestSerializer
from .services.analysis import RouteAnalysis, analyze_routes
from .services.ors import NotConfiguredError, OrsClient, OrsError, Place, RouteRequestError
from .services.recommendation import Recommendation, recommend
from .services.risk import RiskLevel
from .services.route_generation import generate_routes
from .services.weather import ForecastRangeError, OpenMeteoClient, WeatherError


@api_view(["GET"])
def health(request):
    """Liveness check used by the frontend and the hosting platform."""
    return Response({"status": "ok"})


def _error(message: str, http_status: int) -> Response:
    return Response({"error": message}, status=http_status)


def _provider_error_response(exc: OrsError | WeatherError) -> Response:
    if isinstance(exc, NotConfiguredError):
        return _error(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)
    if isinstance(exc, (RouteRequestError, ForecastRangeError)):
        return _error(str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)
    return _error(str(exc), status.HTTP_502_BAD_GATEWAY)


def _place_json(place: Place) -> dict:
    return {"label": place.label, "lat": place.lat, "lon": place.lon}


@api_view(["GET"])
def geocode(request):
    """Place suggestions for the origin/destination inputs: GET /api/geocode/?q=..."""
    query = request.query_params.get("q", "").strip()
    if len(query) < 3:
        return Response({"results": []})
    try:
        places = OrsClient().search(query)
    except OrsError as exc:
        return _provider_error_response(exc)
    return Response({"results": [_place_json(p) for p in places]})


def _resolve(client: OrsClient, location: dict, field: str) -> Place:
    if "text" not in location:
        return Place(label=location["label"], lat=location["lat"], lon=location["lon"])
    matches = client.search(location["text"], size=1, autocomplete=False)
    if not matches:
        raise RouteRequestError(f"Could not find a location for {field}: '{location['text']}'.")
    return matches[0]


def _route_json(analysis: RouteAnalysis, rank: int, recommended: bool) -> dict:
    route = analysis.route
    return {
        "id": route.id,
        "name": route.name,
        "rank": rank,
        "recommended": recommended,
        "distance_miles": route.distance_miles,
        "duration_seconds": route.duration_seconds,
        "arrival_time": analysis.checkpoints[-1].checkpoint.eta.isoformat(),
        "has_no_travel": analysis.has_no_travel,
        "max_risk": analysis.max_risk.key,
        "average_risk": round(analysis.average_risk, 2),
        "miles_by_risk": {level.key: round(analysis.miles_by_risk[level], 1) for level in RiskLevel},
        "geometry": [[lat, lon] for lat, lon in route.geometry],  # [lat, lon] pairs
        "checkpoints": [
            {
                "index": r.checkpoint.index,
                "mile": r.checkpoint.mile,
                "lat": round(r.checkpoint.lat, 5),
                "lon": round(r.checkpoint.lon, 5),
                "eta": r.checkpoint.eta.isoformat(),
                "segment_miles": round(r.checkpoint.segment_miles, 2),
                "wind_mph": r.wind_mph,
                "rain_in_hr": r.rain_in_hr,
                "risk": r.risk.key,
            }
            for r in analysis.checkpoints
        ],
    }


def _recommendation_json(recommendation: Recommendation) -> dict:
    return {
        "route_id": recommendation.best.route.id,
        "reason": recommendation.reason,
        "all_routes_blocked": recommendation.all_routes_blocked,
    }


@api_view(["POST"])
def routes(request):
    """Weather-risk analysis of up to three truck routes: POST /api/routes/."""
    serializer = RouteRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        client = OrsClient()
        origin = _resolve(client, data["origin"], "origin")
        destination = _resolve(client, data["destination"], "destination")
        found = generate_routes(client, (origin.lat, origin.lon), (destination.lat, destination.lon))
        if not found:
            return _error("No route could be found between those places.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        analyses = analyze_routes(
            found,
            data["departure_time"],
            data["load_weight_lb"],
            data["checkpoint_interval_miles"],
            OpenMeteoClient(),
        )
    except (OrsError, WeatherError) as exc:
        return _provider_error_response(exc)

    recommendation = recommend(analyses)
    return Response(
        {
            "origin": _place_json(origin),
            "destination": _place_json(destination),
            "departure_time": data["departure_time"].isoformat(),
            "load_weight_lb": data["load_weight_lb"],
            "checkpoint_interval_miles": data["checkpoint_interval_miles"],
            "recommendation": _recommendation_json(recommendation),
            "routes": [
                _route_json(a, rank, recommended=(rank == 1)) for rank, a in enumerate(recommendation.ranked, start=1)
            ],
        }
    )
