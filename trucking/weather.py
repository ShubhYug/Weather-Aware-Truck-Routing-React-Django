"""Hourly weather from Open-Meteo (free, no key), batched across locations."""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from .geo import RoutingError

URL = "https://api.open-meteo.com/v1/forecast"
BATCH = 50
TTL_SECONDS = 1800
_cache = {}


def _get(params, attempts=4):
    """GET with backoff on Open-Meteo's 429 rate limit."""
    for attempt in range(attempts):
        resp = requests.get(URL, params=params, timeout=30)
        if resp.status_code != 429 or attempt == attempts - 1:
            return resp
        time.sleep(1.5 * (attempt + 1))


def _fetch_batch(points, start_date, end_date):
    resp = _get({
        "latitude": ",".join(f"{p[0]:.1f}" for p in points),
        "longitude": ",".join(f"{p[1]:.1f}" for p in points),
        "hourly": "wind_speed_10m,rain,snowfall",
        "wind_speed_unit": "mph", "precipitation_unit": "inch", "timezone": "UTC",
        "start_date": start_date, "end_date": end_date,
    })
    if resp.status_code == 400:
        raise RoutingError(f"Weather forecast unavailable for those dates: {resp.json().get('reason', '')}", 422)
    if resp.status_code == 429:
        raise RoutingError("Weather service rate limit reached; retry in a minute.", 503)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


def fetch_hourly(points, start, end):
    """Hourly series per point, starting 00:00 UTC on start's date.

    Returns (origin_datetime, [{"wind": [...], "rain": [...], "snow": [...]}, ...]) aligned with points.
    Points snap to a 0.1 degree grid (~7 mi, about the forecast model's resolution), which
    also dedupes nearby checkpoints and shared route segments.
    """
    start_date, end_date = start.date().isoformat(), end.date().isoformat()
    keys = [(round(lat, 1), round(lon, 1)) for lat, lon in points]
    now = time.time()
    missing = sorted({k for k in keys if (k, start_date, end_date) not in _cache or _cache[(k, start_date, end_date)][0] < now})

    batches = [missing[i:i + BATCH] for i in range(0, len(missing), BATCH)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for batch, result in zip(batches, pool.map(lambda b: _fetch_batch(b, start_date, end_date), batches)):
            for key, loc in zip(batch, result):
                h = loc["hourly"]
                clean = lambda xs: [x if x is not None else 0.0 for x in xs]
                _cache[(key, start_date, end_date)] = (now + TTL_SECONDS, {
                    "wind": clean(h["wind_speed_10m"]), "rain": clean(h["rain"]), "snow": clean(h["snowfall"])})

    origin = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    return origin, [_cache[(k, start_date, end_date)][1] for k in keys]
