from rest_framework import serializers


class LocationField(serializers.Field):
    """A place given either as free text or as {label, lat, lon}."""

    default_error_messages = {
        "invalid": "Provide a place name or an object with lat and lon.",
        "range": "lat must be within [-90, 90] and lon within [-180, 180].",
    }

    def to_internal_value(self, data):
        if isinstance(data, str):
            text = data.strip()
            if not text:
                self.fail("invalid")
            return {"text": text}
        if isinstance(data, dict):
            try:
                lat, lon = float(data["lat"]), float(data["lon"])
            except (KeyError, TypeError, ValueError):
                self.fail("invalid")
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                self.fail("range")
            return {"lat": lat, "lon": lon, "label": str(data.get("label") or f"{lat:.4f}, {lon:.4f}")}
        self.fail("invalid")

    def to_representation(self, value):
        return value


class RouteRequestSerializer(serializers.Serializer):
    origin = LocationField()
    destination = LocationField()
    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.IntegerField(min_value=0, max_value=200_000)
