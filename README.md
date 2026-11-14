# Weather-Aware Truck Routing (React + Django)

A web app that helps a truck driver choose the safest route. It generates three route options,
checks the weather the truck will actually meet (at its estimated arrival time at each checkpoint),
scores the risk using the load-aware rules, and recommends the best route.

**Inputs:** origin, destination, departure date/time, load weight.
**Outputs:** 3 routes on a map, risk-coloured checkpoints with ETAs, route summaries, a
recommendation, and a weather heatmap with a 0-48 hour forecast slider.

## Contents

1. [Features](#1-features)
2. [Tech stack](#2-tech-stack)
3. [Project structure](#3-project-structure)
4. [Setup and run locally](#4-setup-and-run-locally)
5. [How to use the app](#5-how-to-use-the-app)
6. [How it works, step by step](#6-how-it-works-step-by-step)
7. [Risk rules](#7-risk-rules)
8. [Route recommendation](#8-route-recommendation)
9. [API reference](#9-api-reference)
10. [Testing](#10-testing)
11. [Deployment](#11-deployment)
12. [Assumptions and limitations](#12-assumptions-and-limitations)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Features

- Origin/destination type-ahead dropdowns (pick a suggestion, or type any text)
- Departure date/time and load weight inputs
- 3 distinct route options from a routing API
- Weather sampled every **10 / 25 / 50 miles**, using each checkpoint's **ETA**
- Risk classification (Low / Moderate / High / Severe / No Travel) with load-based rules
- Recommended route balancing weather risk and travel time
- Map with all routes, checkpoints (risk colour, ETA, wind/rain/snow popups) and route summaries
- Weather heatmap along the corridor with a **0-48 hour** forecast slider
- No API keys required (all third-party services are free and keyless)

## 2. Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Django 5.2, NumPy, Requests, Gunicorn, WhiteNoise |
| Frontend | React 19, Vite, Leaflet, leaflet.heat |
| Routing | [OSRM](https://project-osrm.org/) public server |
| Geocoding | [Nominatim](https://nominatim.org/) (typed text) and [Photon](https://photon.komoot.io/) (type-ahead) |
| Weather | [Open-Meteo](https://open-meteo.com/) hourly forecast |

## 3. Project structure

```
.
├── manage.py
├── requirements.txt
├── render.yaml              # deployment blueprint (Render)
├── config/                  # Django project settings and URLs
├── trucking/                # backend app
│   ├── risk.py              # risk bands + load rules (pure functions)
│   ├── routes.py            # fetch 3 distinct routes from OSRM
│   ├── weather.py           # batched, cached Open-Meteo requests
│   ├── planner.py           # checkpoints, ETAs, scoring, recommendation
│   ├── geo.py               # geocoding, suggestions, shared helpers
│   ├── views.py / urls.py   # API endpoints
│   └── tests.py             # unit tests
└── frontend/                # React app (Vite)
    └── src/
        ├── App.jsx          # state and layout
        ├── api.js           # API client
        ├── risk.js          # level names, colours, formatting
        └── components/      # TripForm, PlaceInput, RouteList, MapView, HeatSlider
```

## 4. Setup and run locally

**Prerequisites:** Python 3.11+, Node.js 20+, internet access (for the free map, routing and weather services).

**Step 1. Clone the repository**
```bash
git clone <your-repo-url>
cd Weather-Aware-Truck-Routing-React-Django
```

**Step 2. Create the Python environment and install dependencies**
```bash
python3 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Step 3. Build the frontend**
```bash
cd frontend
npm install
npm run build
cd ..
```

**Step 4. Start the server**
```bash
python manage.py runserver
```

**Step 5. Open the app** at http://localhost:8000

### Optional: frontend dev mode (live reload)

Keep the Django server running, then in a second terminal:
```bash
cd frontend
npm run dev                   # http://localhost:5173 (proxies /api to Django on :8000)
```

## 5. How to use the app

1. **Enter Origin and Destination.** Type at least 3 characters and pick a suggestion from the
   dropdown (exact location), or type any text and it will be geocoded when you submit.
2. **Choose the Departure date/time** (shown in your browser's timezone).
3. **Enter the Load weight in lb.** Heavy loads make wind more dangerous (see [Risk rules](#7-risk-rules)).
4. **Pick the checkpoint interval**: every 10, 25 or 50 miles.
5. Click **Find safest route** (the first request takes roughly 6-10 seconds for long trips).
6. **Read the recommendation** card, then compare the three route cards (distance, duration,
   arrival time, miles by risk level, average risk). The recommended route is badged.
7. **Click a route card or a route line** on the map to select it and see its checkpoint table
   (mile, ETA, risk, wind, rain, snow).
8. **Click a checkpoint dot** on the map for a popup with its ETA and weather details.
9. **Drag the slider** at the bottom of the map from 0 to 48 hours to see how the weather risk
   along the corridor changes over time. Use the checkbox to turn the heatmap on or off.

## 6. How it works, step by step

1. **Input handling.** The browser sends origin, destination, departure (UTC), load and interval to
   `POST /api/trucking/plan/`. Suggestions picked from the dropdown are sent as `lat,lon`.
2. **Geocoding.** Typed text is geocoded with Nominatim; both places are looked up in parallel.
3. **Three routes.** OSRM's `alternatives` option is used first. OSRM often returns fewer than 3, so
   extra routes are requested via waypoints offset left and right of the midpoint. Near-duplicate
   corridors (more than 90% shared road) are dropped. All OSRM calls run concurrently.
4. **Checkpoints.** Each route is sampled every 10/25/50 miles plus the destination.
   **ETA** = departure + route duration x (checkpoint mile / total miles).
5. **Weather.** Open-Meteo hourly wind (mph), rain and snowfall (inches/hr) are fetched for all
   checkpoints in batches (cached). Each checkpoint reads the forecast hour that matches **its own ETA**.
6. **Risk.** Wind, rain and snow are each banded, the worst wins, then the load rules can escalate it.
7. **Summaries.** Each checkpoint owns the road around it (halfway to its neighbours), so miles at each
   risk level and the average risk are mileage-weighted.
8. **Recommendation.** Routes are ranked (see [section 8](#8-route-recommendation)) and the best is flagged.
9. **Heatmap data.** For every checkpoint the backend also returns its risk for each of the 49 hours
   after departure. Moving the slider only re-weights the heat points in the browser (no new requests),
   so it stays smooth.

## 7. Risk rules

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind | < 25 mph | 25-34 | 35-44 | 45-54 | >= 55 mph |
| Rain | < 0.10 in/hr | 0.10-0.25 | 0.25-0.50 | 0.50-1.00 | > 1.00 |
| Snow | < 0.5 in/hr | 0.5-1.0 | 1.0-2.0 | 2.0-3.0 | > 3.0 |

**Load rules**
- Wind >= 55 mph: **No Travel** for any load
- Wind 45-54 mph and load > 30,000 lb: **No Travel**
- Wind 35-44 mph and load > 40,000 lb: **Severe**

A value exactly on a boundary falls in the higher band (wind 35 = High, rain 0.25 = High). Rain and
snow "No Travel" are strictly above 1.00 and 3.0.

## 8. Route recommendation

Routes are ranked by, in order:
1. No Travel miles (fewest)
2. Severe miles (fewest)
3. High miles (fewest)
4. Lowest average risk (mileage-weighted, 0 = Low ... 4 = No Travel)
5. Shortest travel time

The brief lists Severe, High, average risk, then time. I put **No Travel miles first** because a
closed road should never beat a route that is merely severe. The response includes a plain-English
explanation of the choice.

## 9. API reference

### `POST /api/trucking/plan/`

Request:
```json
{
  "origin": "Chicago, IL",
  "destination": "Denver, CO",
  "departure": "2026-11-15T08:00:00Z",
  "load_lbs": 42000,
  "interval_miles": 25
}
```
`origin`/`destination` accept text or `"lat,lon"`. `interval_miles` is 10, 25 or 50 (default 25).

Response (abridged): `recommended_route_id`, `recommendation`, and `routes[]`, each with
`name`, `distance_miles`, `duration_hours`, `arrival`, `miles_by_level`, `average_risk`, `rank`,
`recommended`, `travel_allowed`, GeoJSON `geometry`, and `checkpoints[]` (`mile`, `lat`, `lon`,
`eta`, `risk`, `driver`, `wind_mph`, `rain_in_hr`, `snow_in_hr`, 49-value `forecast`).

Errors are JSON `{"error": "..."}`: `400` bad input, `422` no route or forecast out of range,
`502`/`503` upstream service problem.

Example:
```bash
curl -X POST http://localhost:8000/api/trucking/plan/ \
  -H 'content-type: application/json' \
  -d '{"origin":"Chicago, IL","destination":"Denver, CO","departure":"2026-11-15T08:00:00Z","load_lbs":42000,"interval_miles":25}'
```

### `GET /api/trucking/suggest/?q=<text>`

Returns `{"suggestions": [{"label", "lat", "lon"}]}` for type-ahead. Needs 3+ characters; returns an
empty list if the suggestion service is unavailable.

## 10. Testing

```bash
python manage.py test           # backend unit tests (13)
cd frontend && npm run lint     # frontend lint
```

The tests cover every risk threshold and boundary, the load rules, checkpoint spacing, ETA-based
weather lookup, the 48-hour forecast series, route ranking (safer-but-slower wins, ties fall back to
travel time) and the suggestions endpoint. They use mocked routes and weather, so they run offline
in about a second.

## 11. Deployment

`render.yaml` is a [Render](https://render.com) blueprint. Gunicorn serves both the API and the built
React app from one origin (via WhiteNoise), so no CORS setup is needed.

1. Push this repo to GitHub.
2. In Render choose **New > Blueprint** and select the repo.
3. Render runs the build (`pip install`, `npm ci`, `npm run build`) and starts Gunicorn.
4. Open the URL Render provides.

To simulate the same commands locally:
```bash
pip install -r requirements.txt && (cd frontend && npm ci && npm run build)
DEBUG=0 SECRET_KEY=test-key gunicorn config.wsgi --workers 2 --threads 4 --timeout 120
```

Environment variables: `DEBUG` (`0` in production), `SECRET_KEY`, `ALLOWED_HOSTS` (comma-separated).

## 12. Assumptions and limitations

- **Forecast range:** Open-Meteo covers about 16 days; departures outside it return an error.
- **Rate limits:** the free services are rate limited, so results are cached (15 min per trip,
  30 min per weather point) and weather requests retry politely on HTTP 429.
- **Weather grid:** coordinates snap to a 0.1 degree grid (~7 miles), about the forecast resolution.
- **Snow and rain:** snow uses forecast snowfall (inches of snow per hour); rain uses the model's rain amount.
- **ETA:** assumes constant average speed (OSRM's total duration); no traffic, breaks or hours-of-service.
- **Speed:** a cold request on a long trip takes ~6-10 s, mostly upstream calls to the free public
  servers. Repeats are served from cache.
- **Timezones:** the UI shows times in the browser's timezone; the API works in UTC.

## 13. Troubleshooting

| Problem | Fix |
|---|---|
| Page is blank or shows a Django 404 at `/` | Build the frontend: `cd frontend && npm run build`, then restart the server |
| "Weather service rate limit reached" | Wait a minute and retry; results are cached afterwards |
| "Forecast only covers about 15 days ahead" | Choose a nearer departure date |
| No suggestions appear | Type 3+ characters; typing the full place name and submitting still works |
| Slow first request | Expected on long trips (free public APIs); the same trip repeats instantly |
| `npm run dev` shows API errors | Make sure `python manage.py runserver` is running on port 8000 |
