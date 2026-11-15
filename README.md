# Weather-Aware Truck Routing

A React + Django app that helps a truck driver choose the safest route based on weather, load weight, and travel time. See [Task.md](Task.md) for the full requirements.

> Work in progress: this README is extended at each build step.

## Structure

```
backend/    Django + Django REST Framework API (stateless, no database)
frontend/   React + Vite + TypeScript UI (Leaflet map)
```

## Local setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit values
python manage.py test
python manage.py runserver  # http://localhost:8000/api/health/
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev                 # http://localhost:5173
```

## API (so far)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health/` | Liveness check |
| `GET /api/geocode/?q=dallas` | Place suggestions (`{results: [{label, lat, lon}]}`) |
| `POST /api/routes/` | Up to 3 truck routes with weather risk and a recommendation. Body: `origin`, `destination` (text or `{label, lat, lon}`), `departure_time` (ISO 8601), `load_weight_lb`, optional `checkpoint_interval_miles` (10, 25 or 50; default 25) |

`POST /api/routes/` returns `recommendation` (`route_id`, `reason`, `all_routes_blocked`) and `routes` ordered best first. Each route has `rank`, `recommended`, distance, duration, `arrival_time`, `miles_by_risk`, `average_risk`, `max_risk`, `has_no_travel`, `geometry` and `checkpoints` (`mile`, `lat`, `lon`, `eta`, `segment_miles`, `wind_mph`, `rain_in_hr`, `risk`). Errors are `{"error": "..."}` with 400 (bad input), 422 (unroutable place or date outside the forecast window), 502 (provider failure) or 503 (missing API key).

Routes come from OpenRouteService's `driving-hgv` (truck) profile. Its alternative-route feature is limited to short trips, so when fewer than 3 distinct routes come back the backend requests routes through sideways-offset via points and keeps those that are distinct (under 85% shared path) and not more than 1.5x the fastest duration. Fewer than 3 routes can be returned when the corridor has no real alternatives. Route geometry is returned as `[lat, lon]` pairs.

## How the analysis works

1. **Checkpoints.** Along each route, a checkpoint is placed at the origin, every 10/25/50 miles, and the destination. The truck is assumed to travel at the route's average speed, so a checkpoint's ETA is the departure time plus its share of the total duration. Each checkpoint owns the stretch of road around it (split at the midpoints between checkpoints), so per-risk miles add up to the route length.
2. **Weather.** Wind (mph, sustained 10 m) and precipitation (in/hr) come from Open-Meteo for the hour nearest each checkpoint's ETA. Coordinates are rounded to 0.01 degrees, de-duplicated, fetched in parallel batches of 50 and cached for 30 minutes. Open-Meteo serves forecasts roughly 16 days ahead (and recent history), so dates outside that window return a clear 422.
3. **Risk.** Each checkpoint takes the worst of its wind level, rain level and the load rules.

| Level | Wind (mph) | Rain (in/hr) |
| --- | --- | --- |
| Low | < 25 | < 0.10 |
| Moderate | 25 to < 35 | 0.10 to 0.25 |
| High | 35 to < 45 | > 0.25 to 0.50 |
| Severe | 45 to < 55 | > 0.50 to 1.00 |
| No Travel | >= 55 | > 1.0 |

Load rules: wind >= 55 is No Travel for any load; wind 45-54 with a load over 30,000 lb is No Travel; wind 35-44 with a load over 40,000 lb is Severe. "Over" is strict, so exactly 30,000 or 40,000 lb does not trigger a rule. The load rules only ever raise a level.

Boundary decisions where the task table is ambiguous for decimal values: wind bands include their lower bound (34.9 mph is Moderate, 35.0 is High); rain bands include their upper bound, matching the task's ">1.0" for No Travel (0.25 is Moderate, 0.26 is High, exactly 1.00 is Severe).

4. **Recommendation.** Routes are ranked by fewest No Travel miles (a route that cannot be driven never beats one that can), then the task's order: fewest Severe miles, fewest High miles, lowest average risk (mile-weighted, Low=0 to No Travel=4), then shortest travel time. Comparisons use 0.1 mile and 0.01 risk precision so floating-point noise cannot decide a tie. If every route contains No Travel conditions, the response says so (`all_routes_blocked`) and picks the one with the fewest No Travel miles.

## Environment variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | backend | Django secret (required when `DEBUG=False`) |
| `DEBUG` | backend | `True` for local development |
| `ALLOWED_HOSTS` | backend | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | backend | Comma-separated frontend origins |
| `ORS_API_KEY` | backend | OpenRouteService key (geocoding + routing) |
| `ORS_BASE_URL` | backend | Optional override of the ORS base URL |
| `WEATHER_BASE_URL` | backend | Optional override of the Open-Meteo forecast URL |
| `VITE_API_URL` | frontend | Backend base URL |
