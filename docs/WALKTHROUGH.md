# Loom walkthrough outline (target 7-8 minutes, limit 5-10)

The task grades routes, weather, risk and recommendation logic at 40%, UI, map and heatmap smoothness at 40%, code quality at 15%, and documentation at 5%. The timings below follow those weights.

## Before recording

- Open the hosted app a minute early so the free-tier backend is awake.
- Have the repo open in an editor with these files ready: `risk.py`, `recommendation.py`, `checkpoints.py`, `heatmap.py`, `RouteMap.tsx`, `HeatLayer.tsx`.
- Have a terminal ready to run `python manage.py test` and `npm test`.
- Weather is live, so the numbers on screen will not match any script. Do a trial search first and pick a trip and departure time where the routes visibly differ. A long trip (for example Dallas to Atlanta, or Chicago to Houston) gives the most contrast. Use a heavy load (for example 42,000 lb) so the load rules can matter.
- Do not run more than two searches back to back; the free weather API rate-limits at about 600 locations a minute.

## Outline

**0:00 Intro (30 s).** What the app does and the stack: React + TypeScript + Leaflet, Django REST, OpenRouteService for truck routes, Open-Meteo for weather.

**0:30 A search (1 min).** Type an origin and destination using the suggestions, set the departure, load weight and the 10/25/50-mile checkpoint interval, and search. Point out the loading state.

**1:30 The result (1.5 min).** The three routes on the map, each in its own colour. The recommendation banner and its reason. The route cards: distance, drive time, arrival, the miles-by-risk bar. Click a card to select a route; click a checkpoint dot to show its ETA, wind, rain and risk.

**3:00 Risk and recommendation logic (2 min), the most important part.** Open `risk.py`: the thresholds, the three load rules, and the boundary decisions. Open `recommendation.py`: the ranking order (No Travel, Severe, High, average risk, time) and why No Travel comes first. Explain how a checkpoint's ETA is computed and how each checkpoint owns a stretch of road. Show the tests: run `python manage.py test` and mention the boundary and load-rule tests.

**5:00 Heatmap (1.5 min).** Drag the 0-48 hour slider and show the corridor changing. Explain that the browser fetches all 49 hours once and the slider only recolours circles already on the map, which is why it stays smooth. Show the toggle. Mention that it uses the same classifier as the routes.

**6:30 Code quality and performance (45 s).** Quick tour of `backend/routing/services/` (one module per concern, pure logic separate from I/O) and the frontend components. Mention canvas rendering, memoized layers and the 60 fps measurement.

**7:15 Hosting, limits and trade-offs (45 s).** Where it is deployed, the free-tier cold start, and the honest limitations: ETAs at average speed, the weather API rate limit, no authentication on the API.

**8:00 Wrap-up (15 s).**

## Things worth saying out loud

- The task's rain table overlaps at 0.25 in/hr and its wind bands have gaps for decimals; the boundaries chosen are documented in the README.
- A route with No Travel conditions is ranked below any drivable route. That is an addition to the task's list.
- Alternative routes on long trips are topped up with via-point routes because the routing provider only offers alternatives on short trips.
