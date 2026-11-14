"""Fetch up to 3 distinct driving routes between two points via OSRM."""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests

from .geo import HTTP_HEADERS, RoutingError, project

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
METERS_PER_MILE = 1609.344
OVERLAP_LIMIT = 0.9  # a route sharing more than this with another is a duplicate


def _osrm(points, alternatives=False):
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    resp = requests.get(
        OSRM_URL.format(coords=coords),
        params={"overview": "full", "geometries": "geojson", "alternatives": "3" if alternatives else "false"},
        headers=HTTP_HEADERS, timeout=30,
    )
    data = resp.json()
    if data.get("code") != "Ok":
        raise RoutingError(f"No drivable route found: {data.get('message', data.get('code'))}", 422)
    return [
        {"geometry": [[lat, lon] for lon, lat in r["geometry"]["coordinates"]],
         "miles": r["distance"] / METERS_PER_MILE, "seconds": r["duration"]}
        for r in data["routes"]
    ]


def _overlap(a, b):
    """Fraction of route a's points lying within 1.5 miles of route b."""
    a_pts, b_pts = np.array(a["geometry"][::20]), np.array(b["geometry"][::5])
    ref = a_pts[:, 0].mean()
    a_xy, b_xy = project(a_pts[:, 0], a_pts[:, 1], ref), project(b_pts[:, 0], b_pts[:, 1], ref)
    nearest = np.linalg.norm(a_xy[:, None, :] - b_xy[None, :, :], axis=2).min(axis=1)
    return float((nearest < 1.5).mean())


def _is_new(route, kept):
    return all(_overlap(route, k) < OVERLAP_LIMIT and _overlap(k, route) < OVERLAP_LIMIT for k in kept)


def _via_points(start, finish, offset_fraction):
    """Waypoints left/right of the midpoint, to force a different corridor."""
    mid = ((start[0] + finish[0]) / 2, (start[1] + finish[1]) / 2)
    d_lat, d_lon = finish[0] - start[0], finish[1] - start[1]
    return [(mid[0] + sign * offset_fraction * d_lon, mid[1] - sign * offset_fraction * d_lat) for sign in (1, -1)]


def _try(points):
    try:
        return _osrm(points)[0]
    except RoutingError:
        return None


def fetch_routes(start, finish, count=3):
    """Up to `count` distinct routes. All OSRM calls run concurrently."""
    vias = [v for fraction in (0.12, 0.25) for v in _via_points(start, finish, fraction)]
    with ThreadPoolExecutor(max_workers=len(vias) + 1) as pool:
        alternatives = pool.submit(_osrm, [start, finish], True)
        steered = [pool.submit(_try, [start, via, finish]) for via in vias]
        routes = []
        for r in alternatives.result():  # raises RoutingError if there is no route at all
            if _is_new(r, routes):
                routes.append(r)
        # OSRM often offers fewer alternatives than requested; fill with via-point routes.
        for future in steered:
            candidate = future.result()
            if len(routes) >= count:
                break
            if candidate and candidate["miles"] <= 1.6 * routes[0]["miles"] and _is_new(candidate, routes):
                routes.append(candidate)
    return routes[:count]
