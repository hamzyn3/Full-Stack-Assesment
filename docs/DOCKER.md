# Running in containers

The Dockerfiles run the whole app locally with one command, so nothing needs installing except Docker. They are **not used by the Vercel deployment**, which builds from source ([DEPLOYMENT.md](DEPLOYMENT.md)).

| File | What it builds |
| --- | --- |
| [backend/Dockerfile](../backend/Dockerfile) | Django served by gunicorn on port 8000, as a non-root user |
| [frontend/Dockerfile](../frontend/Dockerfile) | Builds the Vite app, then serves it with nginx ([nginx.conf](../frontend/nginx.conf)) |
| [docker-compose.yml](../docker-compose.yml) | Starts both |

## Run it

```bash
cp backend/.env.example backend/.env    # then set ORS_API_KEY
docker compose up --build
```

- App: http://localhost:8080
- API: http://localhost:8000/api/health/

Stop with Ctrl+C, then `docker compose down`.

## Notes

- `VITE_API_URL` is baked into the JavaScript at **build** time (it is a build argument in the compose file). If the API address changes, rebuild the frontend: `docker compose up --build`.
- `CORS_ALLOWED_ORIGINS` in the compose file must match the address you open the app on (`http://localhost:8080`).
- `.dockerignore` keeps `.env` and `.venv` out of the images, so your key is passed at run time and never baked in.
- `.vercelignore` files keep the Docker files out of Vercel's builds.
- To host the containers, use a container host (Google Cloud Run, Fly.io, Railway). Pass the same environment variables to the backend and `VITE_API_URL` as a build argument to the frontend.
