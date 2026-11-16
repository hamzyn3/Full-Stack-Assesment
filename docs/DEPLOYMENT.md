# Deployment (Vercel)

The repo is a monorepo, so it is deployed as **two Vercel projects** from the same GitHub repository:

| Project | Root Directory | What it is |
| --- | --- | --- |
| `truck-routing-api` | `backend` | Django as a Python serverless function ([backend/api/index.py](../backend/api/index.py), configured by [backend/vercel.json](../backend/vercel.json)) |
| `truck-routing-web` | `frontend` | The Vite build of the React app ([frontend/vercel.json](../frontend/vercel.json)) |

> This setup has not been run on Vercel from this repo yet. The backend imports and the tests pass locally, but expect to adjust if Vercel's Python runtime behaves differently.

## Before you start

- Push the repository to GitHub.
- Get a free [OpenRouteService](https://openrouteservice.org/dev/#/signup) API key (use a fresh one, never one that was committed).
- Create a Vercel account and connect it to GitHub.

## Steps

The two projects need each other's URLs, so this is done in two passes.

### 1. Deploy the API

1. Vercel dashboard: **Add New > Project**, import the repository.
2. Set **Root Directory** to `backend`. Framework preset: **Other**.
3. Add environment variables:
   - `DEBUG` = `False`
   - `SECRET_KEY` = a long random string (`python -c "import secrets; print(secrets.token_urlsafe(50))"`)
   - `ORS_API_KEY` = your OpenRouteService key
   - `ALLOWED_HOSTS` = the API's hostname, e.g. `truck-routing-api.vercel.app` (or `.vercel.app` to allow any Vercel subdomain)
   - `CORS_ALLOWED_ORIGINS` = leave for the second pass
4. Deploy. Check `https://<api>.vercel.app/api/health/` returns `{"status":"ok"}`.

### 2. Deploy the frontend

1. **Add New > Project**, import the same repository again.
2. Set **Root Directory** to `frontend`. The Vite preset is detected.
3. Add `VITE_API_URL` = the API's URL from step 1 (no trailing slash).
4. Deploy and note the site's URL.

### 3. Point the API at the site

1. On the API project, set `CORS_ALLOWED_ORIGINS` to the frontend's URL (scheme and host, no trailing slash).
2. **Redeploy** the API (Deployments > ... > Redeploy), because environment changes only apply to new deployments.
3. Add the live URL to the README.

If you change `VITE_API_URL` later, redeploy the frontend: Vite bakes it into the JavaScript at build time.

## Check it worked

1. `https://<api>/api/health/` returns `{"status":"ok"}`.
2. Open the site, pick Dallas to Atlanta, leave the defaults, and search.
3. Three routes, the recommendation and the heatmap slider should appear, with no red errors in the browser console.

## Serverless behaviour to know about

- **Function timeout.** A search makes several routing and weather calls. [backend/vercel.json](../backend/vercel.json) sets `maxDuration` to 60 s, which the Hobby plan allows. If a search times out (a 504), check the function logs.
- **Cold starts.** The first request after idle is slower. The frontend pings `/api/health/` on load to warm it. Open the app a minute before a demo or recording.
- **Cache.** The 30-minute weather cache lives in each function instance's memory, so it helps only while an instance stays warm.
- **Quotas.** See "Assumptions and limitations" in the README. Do not run several searches back to back in a demo.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Browser console shows a CORS error | `CORS_ALLOWED_ORIGINS` does not exactly match the site's origin, or the API was not redeployed after changing it |
| "Could not reach the server" | `VITE_API_URL` is wrong or empty, or the frontend was not rebuilt after setting it |
| API returns 400 on every request | The host is not in `ALLOWED_HOSTS` |
| 500 on every request, log says "SECRET_KEY ... required" | `SECRET_KEY` missing while `DEBUG` is not `True` |
| 503 "ORS_API_KEY is not configured" | The key is missing on the API project |
| 503 "weather provider's rate limit" | Too many searches in a minute; wait and retry |
| 504 / function timeout | A slow provider; retry, or lower the checkpoint density |
| 422 about dates | The departure is outside the weather provider's forecast window |

## Other hosts

Nothing here is Vercel-specific except `vercel.json` and `backend/api/index.py`. On a regular server, run `gunicorn config.wsgi:application` with the same environment variables.
