"""Shared helpers: HTTP identity, errors, geocoding and a local metric projection."""
import re
from functools import lru_cache

import numpy as np
import requests

EARTH_RADIUS_MI = 3958.8
HTTP_HEADERS = {"User-Agent": "weather-aware-truck-routing/1.0"}
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
LATLON = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class RoutingError(Exception):
    """A problem the caller can act on (bad input, no route, forecast unavailable)."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@lru_cache(maxsize=512)
def geocode(text):
    """(lat, lon) for 'lat,lon' or a free-text place name."""
    match = LATLON.match(text)
    if match:
        return float(match.group(1)), float(match.group(2))
    resp = requests.get(NOMINATIM_URL, params={"q": text, "format": "json", "limit": 1},
                        headers=HTTP_HEADERS, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise RoutingError(f"Could not find a location for '{text}'.")
    return float(results[0]["lat"]), float(results[0]["lon"])


def project(lat, lon, ref_lat):
    """Equirectangular projection to miles; accurate enough at a few-mile scale."""
    lat, lon = np.radians(lat), np.radians(lon)
    return np.column_stack((lon * np.cos(np.radians(ref_lat)) * EARTH_RADIUS_MI, lat * EARTH_RADIUS_MI))


PHOTON_URL = "https://photon.komoot.io/api/"


@lru_cache(maxsize=1024)
def suggest_places(query, limit=6):
    """Autocomplete suggestions [{label, lat, lon}] from Photon (built for type-ahead)."""
    resp = requests.get(PHOTON_URL, params={"q": query, "limit": limit + 4, "lang": "en"},
                        headers=HTTP_HEADERS, timeout=8)
    resp.raise_for_status()
    seen, out = set(), []
    for feature in resp.json().get("features", []):
        props = feature["properties"]
        if props.get("type") == "house" or not props.get("name"):
            continue
        parts = [props["name"], props.get("city") if props.get("city") != props["name"] else None,
                 props.get("state"), props.get("country")]
        label = ", ".join(p for p in parts if p)
        if label in seen:
            continue
        seen.add(label)
        lon, lat = feature["geometry"]["coordinates"]
        out.append({"label": label, "lat": round(lat, 5), "lon": round(lon, 5)})
    return out[:limit]
