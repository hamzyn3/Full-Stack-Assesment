# Weather-Aware Truck Routing

A React + Django app that helps a truck driver choose the safest route based on weather, load weight, and travel time. Enter an origin, destination, departure time and load weight; the app finds three truck routes, checks the forecast at the truck's estimated arrival time along each one, classifies the risk, recommends a route, and shows a 0-48 hour weather heatmap along the trip corridor.

- **Live app:** _add the hosted URL here after deploying (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md))_
- **Walkthrough video:** _add the Loom link here (outline in [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md))_
- **Requirements:** [Task.md](Task.md)

## Contents

1. [Stack](#stack)
2. [Run it locally](#run-it-locally)
3. [How it works](#how-it-works)
4. [API](#api)
5. [Frontend](#frontend)
6. [Assumptions and limitations](#assumptions-and-limitations)
7. [Testing](#testing)
8. [Project layout](#project-layout)
9. [Configuration](#configuration)

## Stack

| Concern | Choice |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Leaflet (react-leaflet) on OpenStreetMap tiles |
| Backend | Django + Django REST Framework, stateless (no database) |
| Routing and geocoding | [OpenRouteService](https://openrouteservice.org) (`driving-hgv` truck profile). Free API key required |
| Weather | [Open-Meteo](https://open-meteo.com) hourly wind and precipitation. No key |
| Hosting | Vercel (two projects: the Django API as a serverless function, the frontend as a static site) |

## Run it locally

You need Python 3.12+, Node 20+, and a free OpenRouteService key.

```bash
# Backend  ->  http://localhost:8000
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set ORS_API_KEY
python manage.py runserver

# Frontend  ->  http://localhost:5173   (second terminal)
cd frontend
npm install
cp .env.example .env
npm run dev
```

## How it works

A search runs these steps on the backend. Each lives in its own module under [backend/routing/services/](backend/routing/services/) and is unit tested.

### 1. Routes

OpenRouteService's truck profile is asked for three alternatives. That feature only works on short trips, so when fewer than three distinct routes come back, the backend also requests routes through sideways-offset via points (in parallel) and keeps those that are genuinely different (under 85% shared path) and not absurd detours (within 1.5x the fastest duration). A corridor with no real alternatives can return fewer than three routes.

### 2. Checkpoints and ETAs

A checkpoint is placed at the origin, every 10, 25 or 50 miles (the user's choice), and the destination. The truck is assumed to drive at the route's average speed, so a checkpoint's ETA is the departure time plus its share of the total duration. Each checkpoint owns the road around it (split at the midpoints between checkpoints), so the miles in each risk level add up to the route length.

### 3. Weather

For each checkpoint the backend reads wind speed (sustained, 10 m, mph) and precipitation (in/hr) for the forecast hour nearest the ETA. Locations are rounded to 0.01 degrees, de-duplicated, fetched in parallel batches of 50 and cached for 30 minutes.

### 4. Risk

Each checkpoint takes the worst of its wind level, rain level and the load rules.

| Level | Wind (mph) | Rain (in/hr) |
| --- | --- | --- |
| Low | < 25 | < 0.10 |
| Moderate | 25 to < 35 | 0.10 to 0.25 |
| High | 35 to < 45 | > 0.25 to 0.50 |
| Severe | 45 to < 55 | > 0.50 to 1.00 |
| No Travel | >= 55 | > 1.0 |

Load rules (they only ever raise a level):

- wind >= 55 mph is **No Travel** for any load
- wind 45-54 mph with a load over 30,000 lb is **No Travel**
- wind 35-44 mph with a load over 40,000 lb is **Severe**

"Over" is strict, so exactly 30,000 or 40,000 lb does not trigger a rule.

The task's table is ambiguous for decimal values, so the boundaries were fixed like this: wind bands include their lower bound (34.9 mph is Moderate, 35.0 is High), and rain bands include their upper bound, matching the table's "> 1.0" for No Travel (0.25 is Moderate, 0.26 is High, exactly 1.00 is Severe).

### 5. Recommendation

Routes are ranked by, in order:

1. fewest **No Travel** miles. This is an addition to the task's list: a route that cannot be driven must never beat one that can
2. fewest **Severe** miles
3. fewest **High** miles
4. lowest **average risk** (mile-weighted, Low = 0 up to No Travel = 4)
5. shortest **travel time**

Miles are compared at 0.1 mile and average risk at 0.01 so floating-point noise cannot decide a tie. The response includes a plain-language reason (for example "Same Severe and High miles, lowest average risk"). If every route contains No Travel conditions, the app says so and picks the route with the fewest No Travel miles.

### 6. Heatmap

A separate call builds a grid of cells covering the corridor (every cell touched by, or next to, any route). Each cell gets a risk level for every hour from the departure hour (+0h) to +48h, using the same classifier and load rules as the route analysis, so the two can never disagree. The browser fetches all 49 hours once; moving the slider only recolours circles already on the map. The cell size grows for very long trips so one heatmap never uses more than 200 weather locations.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health/` | Liveness check |
| `GET /api/geocode/?q=dallas` | Place suggestions: `{results: [{label, lat, lon}]}` |
| `POST /api/routes/` | Up to three routes with weather risk and a recommendation |
| `POST /api/heatmap/` | Hourly risk grid along a corridor for hours +0..+48 |

**`POST /api/routes/`** takes `origin` and `destination` (a place name, or `{label, lat, lon}`), `departure_time` (ISO 8601), `load_weight_lb`, and optionally `checkpoint_interval_miles` (10, 25 or 50; default 25). It returns `recommendation` (`route_id`, `reason`, `all_routes_blocked`) and `routes`, best first. Each route has `rank`, `recommended`, `distance_miles`, `duration_seconds`, `arrival_time`, `miles_by_risk`, `average_risk`, `max_risk`, `has_no_travel`, `geometry` (`[lat, lon]` pairs) and `checkpoints` (`mile`, `lat`, `lon`, `eta`, `segment_miles`, `wind_mph`, `rain_in_hr`, `risk`).

**`POST /api/heatmap/`** takes `routes` (up to three `[lat, lon]` polylines), `departure_time` and `load_weight_lb`. It returns `start_time` (the departure hour), `hours` (49), `cell_miles`, and `cells`: each `{lat, lon, risk}` where `risk` has one value per hour (0 Low ... 4 No Travel, -1 no forecast).

Errors are `{"error": "..."}` with status 400 (invalid input), 422 (unroutable place, or a date outside the forecast window), 502 (a provider failed), or 503 (the routing key is missing, or the weather provider's rate limit was reached).

## Frontend

- **Form:** origin and destination with debounced, keyboard-accessible place suggestions; departure date/time (entered in local time, sent as UTC); load weight; checkpoint interval. Text that was not picked from the suggestions is geocoded by the backend.
- **Map:** all routes at once, one colour per route. Click a line or a card to select a route. Checkpoints are dots coloured by risk; click one for its ETA, wind, rain, risk and the road it covers. A and B mark the trip ends.
- **Summary panel:** the recommendation and its reason, a card per route (distance, drive time, arrival, average and maximum risk, a miles-by-risk bar), and a checkpoint table for the selected route.
- **Heatmap:** a toggle and a 0-48 hour slider. It loads in the background, so route results are never delayed by it, and it has a retry button if the forecast provider is busy.
- **Performance:** canvas rendering; checkpoints in their own pane above the route lines; per-route layers memoized so selecting a route only restyles; one shared popup for all checkpoints; heatmap circles created once and recoloured imperatively. In Chrome with about 260 checkpoints on screen, panning, zooming and scrubbing through all 49 hours held 60 fps.
- All times are shown in the browser's time zone.

## Assumptions and limitations

- **ETAs use the route's average speed.** Traffic, stops, breaks and hours-of-service rules are not modelled.
- **Wind is the sustained 10 m speed, not gusts.** Rain is the hourly precipitation rate.
- **Forecast window.** Open-Meteo serves recent history and about two weeks ahead. Searches outside that window return a clear error. The heatmap needs the full +48h inside the window.
- **Weather rate limit.** Open-Meteo's free tier allows 600 locations per minute, one per checkpoint or heatmap cell. A 25-mile search uses roughly 100 locations for the routes plus up to 200 for the heatmap, and a 10-mile search roughly 260 plus 200. Two or three searches in quick succession can hit the limit; the app then shows a clear message and the heatmap has a retry button. Results are cached for 30 minutes per server process (so with several workers each keeps its own cache). Open-Meteo's free API is for non-commercial use; a paid plan would be needed beyond a demo.
- **Routing quota.** OpenRouteService's free tier has per-minute and per-day limits, and a search can use several directions requests.
- **No authentication or rate limiting of its own.** The hosted API is open to anyone with the URL, so a public deployment can be used to spend the ORS and weather quotas.
- **Fewer than three routes** can come back when a corridor has no real alternatives.
- **Map tiles** come from OpenStreetMap's public tile server, which is fine for a demo but not for heavy traffic.
- **Tested in Chrome only** (desktop and a phone-sized viewport).

## Testing

```bash
cd backend && python manage.py test     # 115 tests
cd frontend && npm test                 # 20 tests
cd frontend && npm run build            # type-checks, then builds
cd frontend && npm run lint
```

The backend tests concentrate on the logic the task weights most: every risk boundary and load rule, checkpoint placement and ETAs, the ranking and its explanations, the weather client (batching, caching, errors), route selection, and the heatmap grid. Provider calls are mocked, so the suite needs no network or API keys.

## Project layout

```
backend/
  api/index.py             Vercel serverless entry point (vercel.json configures it)
  config/                  Django settings and root URLs
  routing/
    views.py               HTTP layer: validation, error mapping, JSON shape
    serializers.py         Request validation
    services/
      ors.py               OpenRouteService client (geocoding, truck directions)
      route_generation.py  Three distinct routes, with via-point top-up
      checkpoints.py       Checkpoint placement and ETAs
      weather.py           Open-Meteo client (batching, caching)
      risk.py              Thresholds and load rules (pure functions)
      analysis.py          Routes + weather -> risk per checkpoint and route
      recommendation.py    Ranking and the explanation text
      heatmap.py           Corridor grid and hourly risk
      geo.py               Distance, interpolation and overlap helpers
    tests/
frontend/src/
  App.tsx                  State for the search; wires the pieces together
  api.ts, types.ts         Backend client and response types
  useHeatmap.ts            Background heatmap loading with retry
  components/              Form, map, heat layer, summary cards, tables
docs/                      Deployment guide and walkthrough outline
```

## Configuration

| Variable | Where | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | backend | Django secret. Required when `DEBUG` is not `True` |
| `DEBUG` | backend | `True` for local development |
| `ALLOWED_HOSTS` | backend | Comma-separated hostnames  |
| `CORS_ALLOWED_ORIGINS` | backend | Comma-separated frontend origins |
| `ORS_API_KEY` | backend | OpenRouteService key (geocoding and routing) |
| `ORS_BASE_URL` | backend | Optional override of the ORS base URL |
| `WEATHER_BASE_URL` | backend | Optional override of the Open-Meteo forecast URL |
| `VITE_API_URL` | frontend | Backend base URL, baked in at build time |
