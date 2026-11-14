# Weather-Aware Truck Routing (React + Django)

Helps a truck driver pick the safest of three routes using the weather the truck will actually
meet, based on departure time, load weight and travel time.

Enter origin, destination, departure date/time and load weight. The app returns three routes,
weather risk at checkpoints every 10/25/50 miles (using each checkpoint's ETA), a recommendation,
and a 0-48 h weather heatmap with a forecast slider.

## Run locally

```bash
# backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver            # http://localhost:8000

# frontend (dev server with API proxy, http://localhost:5173)
cd frontend && npm install && npm run dev

# or build once and let Django serve it at http://localhost:8000
cd frontend && npm run build
```

Tests: `python manage.py test` (risk rules, checkpointing, ETA-based weather lookup, recommendation).
Frontend lint: `cd frontend && npm run lint`.

Hosting: `render.yaml` is a ready Render blueprint (gunicorn serves the API and the built React app
from one origin via WhiteNoise). No API keys are needed.

## API

`POST /api/trucking/plan/`

```json
{"origin": "Chicago, IL", "destination": "Denver, CO",
 "departure": "2026-11-15T08:00:00Z", "load_lbs": 42000, "interval_miles": 25}
```

Returns `routes[]` (each with GeoJSON geometry, distance, duration, arrival, `miles_by_level`,
`average_risk`, `rank`, `recommended`, and `checkpoints[]` with ETA, risk, wind/rain/snow and a
49-value hourly `forecast` of risk levels), plus `recommended_route_id` and a plain-English
`recommendation`. Errors are JSON `{"error": ...}` (400 bad input, 422 no route / forecast
out of range, 502/503 upstream service problems).

## How it works

| Step | Implementation |
|---|---|
| Place input | Origin/destination are type-ahead dropdowns (`GET /api/trucking/suggest/?q=`, Photon). Pick a suggestion (sent as exact coordinates) or just type any text |
| Geocoding | Nominatim for typed text (or pass `lat,lon`) |
| 3 routes | OSRM public server: `alternatives` plus via-point routes when OSRM offers fewer than 3; near-duplicate corridors (>90% shared) are dropped ([trucking/routes.py](trucking/routes.py)) |
| Checkpoints | Every 10/25/50 miles plus the destination. ETA = departure + route duration x fraction of distance ([trucking/planner.py](trucking/planner.py)) |
| Weather | Open-Meteo hourly wind (mph), rain and snowfall (in/hr); one batched, cached request set per trip. Each checkpoint reads the hour of **its ETA**; coordinates snap to a 0.1 degree grid (~ the model resolution) ([trucking/weather.py](trucking/weather.py)) |
| Risk | Worst of wind/rain/snow band, then load rules applied ([trucking/risk.py](trucking/risk.py)) |
| Recommendation | Sort by No-Travel miles, Severe miles, High miles, average risk, duration |
| Map | Leaflet (canvas renderer): routes, risk-coloured checkpoints with popups, heatmap via `leaflet.heat` |
| Heatmap slider | Backend returns risk for hours 0-48 after departure per checkpoint, so dragging the slider only swaps heat-point weights client-side (no requests) |

### Risk rules

Band edges: a value on a boundary takes the higher band (wind 35 = High, rain 0.25 = High).
Rain "No Travel" is strictly > 1.00 in/hr, snow strictly > 3.0 in/hr.
Load rules: wind >= 55 -> No Travel; 45-54 mph with > 30,000 lb -> No Travel;
35-44 mph with > 40,000 lb -> at least Severe.

### Recommendation details

Each checkpoint owns the road around it (halfway to its neighbours), so "Severe miles" etc. are
mileage-weighted. The brief's order is followed (Severe miles, High miles, average risk, time);
I rank **No-Travel miles first**, since a closed road must never beat a merely severe one.
Average risk is the mileage-weighted level (0 = Low ... 4 = No Travel).

## Assumptions and limitations

- Weather: Open-Meteo has a forecast of ~16 days; departures outside it return an error. The free tier
  is rate limited, so results are cached (15 min per trip, 30 min per weather point).
- Snow uses forecast snowfall (inches of snow per hour); rain uses the model's rain amount.
- ETA assumes constant average speed along the route (OSRM's total duration); no traffic or HOS breaks.
- Route diversity depends on the public OSRM demo server; for long trips a cold request takes ~6-10 s
  (mostly upstream calls). Repeats are served from cache instantly.
- Times in the UI are shown in the browser's timezone; the API works in UTC.
