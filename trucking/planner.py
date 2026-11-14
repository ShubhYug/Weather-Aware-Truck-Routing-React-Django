"""Checkpoint sampling, risk scoring and route recommendation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import numpy as np

from .geo import EARTH_RADIUS_MI, RoutingError, geocode

from .risk import HIGH, LEVELS, NO_TRAVEL, SEVERE, classify
from .routes import fetch_routes
from .weather import fetch_hourly

FORECAST_HOURS = 48
ALLOWED_INTERVALS = (10, 25, 50)
MAX_FORECAST_DAYS = 15


def _cumulative_miles(geometry, total_miles):
    pts = np.array(geometry)
    lat1, lon1, lat2, lon2 = map(np.radians, (pts[:-1, 0], pts[:-1, 1], pts[1:, 0], pts[1:, 1]))
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    seg = 2 * EARTH_RADIUS_MI * np.arcsin(np.sqrt(h))
    cum = np.concatenate(([0.0], np.cumsum(seg)))
    return pts, cum * (total_miles / cum[-1])


def sample_checkpoints(route, interval):
    """Checkpoints every `interval` miles (plus the destination), each owning the road around it."""
    total = route["miles"]
    pts, cum = _cumulative_miles(route["geometry"], total)
    marks = list(np.arange(0, total, interval)) + [total]
    lats, lons = np.interp(marks, cum, pts[:, 0]), np.interp(marks, cum, pts[:, 1])
    checkpoints = []
    for i, mile in enumerate(marks):
        lo = 0.0 if i == 0 else (marks[i - 1] + mile) / 2
        hi = total if i == len(marks) - 1 else (mile + marks[i + 1]) / 2
        checkpoints.append({"mile": float(mile), "lat": float(lats[i]), "lon": float(lons[i]), "span_miles": hi - lo})
    return checkpoints


def _hour_index(moment, origin, series_len):
    idx = int((moment - origin).total_seconds() // 3600)
    return max(0, min(idx, series_len - 1))


def _score(series, idx, load):
    level, driver = classify(series["wind"][idx], series["rain"][idx], series["snow"][idx], load)
    return level, driver, {"wind_mph": round(series["wind"][idx], 1), "rain_in_hr": round(series["rain"][idx], 2),
                           "snow_in_hr": round(series["snow"][idx], 2)}


def _rank_key(summary):
    """Lower is better. No-Travel miles come first: a closed road beats any Severe tie-break."""
    m = summary["miles_by_level"]
    return (m["No Travel"], m["Severe"], m["High"], summary["average_risk"], summary["duration_hours"])


def plan(origin_text, destination_text, departure, load_lbs, interval):
    if interval not in ALLOWED_INTERVALS:
        raise RoutingError(f"interval_miles must be one of {ALLOWED_INTERVALS}.")
    if load_lbs < 0:
        raise RoutingError("load_lbs must be positive.")
    with ThreadPoolExecutor(max_workers=2) as pool:
        start, finish = pool.map(geocode, (origin_text, destination_text))
    routes = fetch_routes(start, finish)

    for r in routes:
        r["checkpoints"] = sample_checkpoints(r, interval)
    longest_hours = max(r["seconds"] for r in routes) / 3600
    window_end = departure + timedelta(hours=max(FORECAST_HOURS, longest_hours) + 1)
    first_hour = departure.replace(minute=0, second=0, microsecond=0)
    if window_end > first_hour + timedelta(days=MAX_FORECAST_DAYS):
        raise RoutingError(f"Forecast only covers about {MAX_FORECAST_DAYS} days ahead.")

    all_points = [(c["lat"], c["lon"]) for r in routes for c in r["checkpoints"]]
    origin, series = fetch_hourly(all_points, departure, window_end)
    series_iter = iter(series)
    base = _hour_index(first_hour, origin, 10**9)

    results = []
    for n, route in enumerate(routes):
        counts = {name: 0.0 for name in LEVELS}
        weighted, worst = 0.0, None
        out_points = []
        for c in route["checkpoints"]:
            s = next(series_iter)
            eta = departure + timedelta(seconds=route["seconds"] * c["mile"] / route["miles"])
            level, driver, obs = _score(s, _hour_index(eta, origin, len(s["wind"])), load_lbs)
            counts[LEVELS[level]] += c["span_miles"]
            weighted += level * c["span_miles"]
            point = {"mile": round(c["mile"], 1), "lat": round(c["lat"], 4), "lon": round(c["lon"], 4),
                     "eta": eta.isoformat(), "risk": LEVELS[level], "risk_level": level, "driver": driver, **obs,
                     # Heatmap: risk at this spot for each hour from departure, independent of ETA.
                     "forecast": [_score(s, _hour_index(first_hour + timedelta(hours=h), origin, len(s["wind"])), load_lbs)[0]
                                  for h in range(FORECAST_HOURS + 1)]}
            out_points.append(point)
            if worst is None or level > worst["risk_level"]:
                worst = point
        hours = route["seconds"] / 3600
        results.append({
            "id": n, "name": f"Route {chr(65 + n)}",
            "distance_miles": round(route["miles"], 1), "duration_hours": round(hours, 2),
            "arrival": (departure + timedelta(hours=hours)).isoformat(),
            "miles_by_level": {k: round(v, 1) for k, v in counts.items()},
            "average_risk": round(weighted / route["miles"], 3),
            "max_risk": worst["risk"], "worst_checkpoint": {"mile": worst["mile"], "risk": worst["risk"], "driver": worst["driver"]},
            "travel_allowed": counts["No Travel"] == 0,
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in route["geometry"]]},
            "checkpoints": out_points,
        })

    ranked = sorted(results, key=_rank_key)
    best = ranked[0]
    for r in results:
        r["recommended"] = r is best
        r["rank"] = ranked.index(r) + 1
    return {
        "origin": {"query": origin_text, "lat": start[0], "lon": start[1]},
        "destination": {"query": destination_text, "lat": finish[0], "lon": finish[1]},
        "departure": departure.isoformat(), "load_lbs": load_lbs, "interval_miles": interval,
        "recommended_route_id": best["id"], "recommendation": _explain(best, ranked),
        "routes": results,
    }


def _explain(best, ranked):
    if not best["travel_allowed"]:
        return f"{best['name']} is the least bad option, but every route has No Travel conditions for this load. Delay departure."
    m = best["miles_by_level"]
    text = (f"{best['name']}: {m['Severe']:.0f} Severe mi, {m['High']:.0f} High mi, average risk {best['average_risk']:.2f}, "
            f"{best['duration_hours']:.1f} h.")
    if len(ranked) > 1:
        text += " Chosen over " + ", ".join(r["name"] for r in ranked[1:]) + " on weather risk first, travel time last."
    return text
