# Deployment

The repo includes a [Render](https://render.com) blueprint ([render.yaml](../render.yaml)) that creates two services:

| Service | Type | What it runs |
| --- | --- | --- |
| `truck-routing-api` | Web service (Python) | Django via gunicorn, health check at `/api/health/` |
| `truck-routing-web` | Static site | The Vite build of the React app |

> The blueprint and the production settings were rehearsed locally (gunicorn with `DEBUG=False`, a strict CORS origin, and the built frontend served separately). The deployment itself has to be done from your own Render account, so the blueprint has not been run on Render yet. Expect to adjust if Render's schema has changed.

## Before you start

- Push the repository to GitHub.
- Get a free [OpenRouteService](https://openrouteservice.org/dev/#/signup) API key.
- Create a Render account and connect it to GitHub.

## Steps

The two services need each other's URLs, so this is done in two passes.

1. **Create the blueprint.** In Render: **New > Blueprint**, pick the repository, and Render reads `render.yaml`.
2. **Fill in the prompts.** Enter `ORS_API_KEY`. Leave `CORS_ALLOWED_ORIGINS` and `VITE_API_URL` blank for now (you can use a placeholder such as `https://example.com`). `SECRET_KEY` is generated for you.
3. **Wait for the first deploy.** Note the two URLs Render assigns, for example `https://truck-routing-api.onrender.com` and `https://truck-routing-web.onrender.com`. If a name is already taken, Render adds a suffix; use whatever it shows.
4. **Point each service at the other.**
   - On the **API** service, set `CORS_ALLOWED_ORIGINS` to the static site's URL (no trailing slash).
   - On the **static site**, set `VITE_API_URL` to the API's URL (no trailing slash).
5. **Redeploy both.** The API restarts when its environment changes. The static site must be **rebuilt** (Manual Deploy > Deploy latest commit), because Vite bakes `VITE_API_URL` into the JavaScript at build time.
6. **Add the live URL to the README.**

## Check it worked

1. `https://<api>/api/health/` returns `{"status":"ok"}`.
2. Open the static site. Pick Dallas to Atlanta, leave the defaults, and search.
3. Three routes, the recommendation and the heatmap slider should appear, with no red errors in the browser console.

## Free-tier behaviour

- **Cold starts.** A free web service sleeps after about 15 minutes idle and takes 30-60 seconds to wake. The frontend pings `/api/health/` as soon as the page loads, so it starts waking while the user fills in the form. Open the app yourself a minute before a demo or a recording.
- **Weather and routing quotas.** See "Assumptions and limitations" in the README. Do not run several searches back to back during a demo; the heatmap's retry button recovers from a weather rate limit after about a minute.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Browser console shows a CORS error | `CORS_ALLOWED_ORIGINS` on the API does not exactly match the site's origin (scheme and host, no path, no trailing slash) |
| "Could not reach the server" in the app | `VITE_API_URL` is wrong or empty, or the static site was not rebuilt after setting it |
| API returns 400 on every request | The request's host is not in `ALLOWED_HOSTS`. Render's own hostname is added automatically; add custom domains to `ALLOWED_HOSTS` |
| 503 "ORS_API_KEY is not configured" | The key is missing on the API service |
| 503 "weather provider's rate limit" | Too many searches in a minute; wait and retry |
| 422 about dates | The departure is outside the weather provider's forecast window (about two weeks ahead, a few months back) |
| API fails to start with "SECRET_KEY ... required" | `SECRET_KEY` is missing while `DEBUG` is not `True` |

## Other hosts

Nothing is Render-specific except `render.yaml` and the optional `RENDER_EXTERNAL_HOSTNAME` handling in `backend/config/settings.py`.

- **Backend** (Railway, Fly.io, a VM): install `backend/requirements.txt`, run `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`, and set `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` and `ORS_API_KEY`.
- **Frontend** (Vercel, Netlify, any static host): build command `npm ci && npm run build`, publish directory `dist`, environment variable `VITE_API_URL`.
