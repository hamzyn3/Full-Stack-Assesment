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
| `POST /api/routes/` | Up to 3 truck routes. Body: `origin`, `destination` (text or `{label, lat, lon}`), `departure_time` (ISO 8601), `load_weight_lb` |

Routes come from OpenRouteService's `driving-hgv` (truck) profile. Its alternative-route feature is limited to short trips, so when fewer than 3 distinct routes come back the backend requests routes through sideways-offset via points and keeps those that are distinct (under 85% shared path) and not more than 1.5x the fastest duration. Fewer than 3 routes can be returned when the corridor has no real alternatives. Route geometry is returned as `[lat, lon]` pairs.

## Environment variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | backend | Django secret (required when `DEBUG=False`) |
| `DEBUG` | backend | `True` for local development |
| `ALLOWED_HOSTS` | backend | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | backend | Comma-separated frontend origins |
| `ORS_API_KEY` | backend | OpenRouteService key (geocoding + routing) |
| `ORS_BASE_URL` | backend | Optional override of the ORS base URL |
| `VITE_API_URL` | frontend | Backend base URL |
