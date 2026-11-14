import json
from datetime import datetime, timezone

import requests
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .geo import RoutingError, suggest_places

from .planner import plan


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


@csrf_exempt
@require_POST
def plan_trip(request):
    """POST /api/trucking/plan/ {origin, destination, departure (ISO 8601), load_lbs, interval_miles}"""
    try:
        body = json.loads(request.body)
        origin, destination = str(body["origin"]).strip(), str(body["destination"]).strip()
        departure = datetime.fromisoformat(str(body["departure"]).replace("Z", "+00:00"))
        load_lbs, interval = float(body["load_lbs"]), int(body.get("interval_miles", 25))
    except (ValueError, KeyError, TypeError):
        return _error("Required JSON fields: origin, destination, departure (ISO 8601), load_lbs; optional interval_miles (10/25/50).")
    if not origin or not destination:
        return _error("origin and destination are required.")
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)
    departure = departure.astimezone(timezone.utc)

    key = f"trip:{origin.lower()}|{destination.lower()}|{departure:%Y%m%d%H}|{load_lbs}|{interval}"
    result = cache.get(key)
    if result is None:
        try:
            result = plan(origin, destination, departure, load_lbs, interval)
        except RoutingError as exc:
            return _error(str(exc), exc.status)
        except requests.RequestException:
            return _error("Routing or weather service is unavailable; try again.", 502)
        cache.set(key, result, 900)
    return JsonResponse(result)


@require_GET
def suggest(request):
    """GET /api/trucking/suggest/?q=chic -> {"suggestions": [{label, lat, lon}]}"""
    query = request.GET.get("q", "").strip()
    if len(query) < 3:
        return JsonResponse({"suggestions": []})
    try:
        return JsonResponse({"suggestions": suggest_places(query)})
    except requests.RequestException:
        return JsonResponse({"suggestions": []})  # typing freely must keep working
