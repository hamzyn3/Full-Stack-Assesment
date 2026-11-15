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

## Environment variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | backend | Django secret (required when `DEBUG=False`) |
| `DEBUG` | backend | `True` for local development |
| `ALLOWED_HOSTS` | backend | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | backend | Comma-separated frontend origins |
| `ORS_API_KEY` | backend | OpenRouteService key (used from Step 2) |
| `VITE_API_URL` | frontend | Backend base URL |
