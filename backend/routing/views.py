from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import RouteRequestSerializer
from .services.ors import NotConfiguredError, OrsClient, OrsError, Place, RouteRequestError, UpstreamError
from .services.route_generation import generate_routes


@api_view(["GET"])
def health(request):
    """Liveness check used by the frontend and the hosting platform."""
    return Response({"status": "ok"})


def _error(message: str, http_status: int) -> Response:
    return Response({"error": message}, status=http_status)


def _provider_error_response(exc: OrsError) -> Response:
    if isinstance(exc, NotConfiguredError):
        return _error(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)
    if isinstance(exc, RouteRequestError):
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


@api_view(["POST"])
def routes(request):
    """Generate up to three truck routes: POST /api/routes/."""
    serializer = RouteRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        client = OrsClient()
        origin = _resolve(client, data["origin"], "origin")
        destination = _resolve(client, data["destination"], "destination")
        found = generate_routes(client, (origin.lat, origin.lon), (destination.lat, destination.lon))
    except OrsError as exc:
        return _provider_error_response(exc)

    if not found:
        return _error("No route could be found between those places.", status.HTTP_422_UNPROCESSABLE_ENTITY)

    return Response(
        {
            "origin": _place_json(origin),
            "destination": _place_json(destination),
            "departure_time": data["departure_time"].isoformat(),
            "load_weight_lb": data["load_weight_lb"],
            "routes": [
                {
                    "id": r.id,
                    "name": r.name,
                    "distance_miles": r.distance_miles,
                    "duration_seconds": r.duration_seconds,
                    "geometry": [[lat, lon] for lat, lon in r.geometry],  # [lat, lon] pairs
                }
                for r in found
            ],
        }
    )
