from datetime import datetime, timezone
from unittest import mock

from django.test import SimpleTestCase

from . import planner
from .risk import HIGH, LOW, MODERATE, NO_TRAVEL, SEVERE, classify


class RiskTests(SimpleTestCase):
    def test_wind_bands_light_load(self):
        for wind, expected in [(24.9, LOW), (25, MODERATE), (34.9, MODERATE), (35, HIGH), (44.9, HIGH),
                               (45, SEVERE), (54.9, SEVERE), (55, NO_TRAVEL)]:
            self.assertEqual(classify(wind, 0, 0, 10000)[0], expected, wind)

    def test_rain_bands(self):
        for rain, expected in [(0.09, LOW), (0.10, MODERATE), (0.25, HIGH), (0.50, SEVERE), (1.00, SEVERE), (1.01, NO_TRAVEL)]:
            self.assertEqual(classify(0, rain, 0, 10000)[0], expected, rain)

    def test_snow_bands(self):
        for snow, expected in [(0.4, LOW), (0.5, MODERATE), (1.0, HIGH), (2.0, SEVERE), (3.0, SEVERE), (3.1, NO_TRAVEL)]:
            self.assertEqual(classify(0, 0, snow, 10000)[0], expected, snow)

    def test_load_rules(self):
        self.assertEqual(classify(55, 0, 0, 1000)[0], NO_TRAVEL)  # any load
        self.assertEqual(classify(50, 0, 0, 30001)[0], NO_TRAVEL)
        self.assertEqual(classify(50, 0, 0, 30000)[0], SEVERE)  # not over 30,000
        self.assertEqual(classify(40, 0, 0, 40001)[0], SEVERE)
        self.assertEqual(classify(40, 0, 0, 40000)[0], HIGH)

    def test_worst_condition_wins(self):
        self.assertEqual(classify(10, 0.3, 2.5, 10000), (SEVERE, "snow"))


def straight_route(miles, hours, lon0=-100.0):
    """A due-east line of roughly `miles` length (1 deg lon ~ 55 mi at 40N)."""
    n = 50
    return {"geometry": [[40.0, lon0 + i * miles / 55.0 / (n - 1)] for i in range(n)], "miles": miles, "seconds": hours * 3600}


def flat_series(wind=0.0, rain=0.0, snow=0.0, hours=100):
    return {"wind": [wind] * hours, "rain": [rain] * hours, "snow": [snow] * hours}


class PlannerTests(SimpleTestCase):
    departure = datetime(2026, 1, 10, 6, 30, tzinfo=timezone.utc)

    def run_plan(self, routes, series_for, load=20000, interval=50):
        """series_for(route_index, checkpoint_index) -> hourly series."""
        counts = [len(planner.sample_checkpoints(r, interval)) for r in routes]
        series = [series_for(i, j) for i, n in enumerate(counts) for j in range(n)]
        with mock.patch.object(planner, "geocode", return_value=(40.0, -100.0)), \
                mock.patch.object(planner, "fetch_routes", return_value=routes), \
                mock.patch.object(planner, "fetch_hourly", return_value=(datetime(2026, 1, 10, tzinfo=timezone.utc), series)):
            return planner.plan("A", "B", self.departure, load, interval)

    def test_checkpoints_every_interval_plus_destination(self):
        cps = planner.sample_checkpoints(straight_route(120, 2), 50)
        self.assertEqual([c["mile"] for c in cps], [0, 50, 100, 120])
        self.assertAlmostEqual(sum(c["span_miles"] for c in cps), 120)

    def test_safer_route_wins_even_if_slower(self):
        fast, slow = straight_route(100, 2), straight_route(150, 3)
        result = self.run_plan([fast, slow], lambda i, j: flat_series(wind=50 if i == 0 else 5), load=35000)
        self.assertEqual(result["recommended_route_id"], 1)  # fast route is No Travel (50 mph, >30k lb)
        self.assertFalse(result["routes"][0]["travel_allowed"])

    def test_ties_on_risk_fall_back_to_travel_time(self):
        result = self.run_plan([straight_route(150, 3), straight_route(100, 2)], lambda i, j: flat_series())
        self.assertEqual(result["recommended_route_id"], 1)

    def test_weather_uses_eta_at_each_checkpoint(self):
        # Storm only in hour 8 (UTC). Departure 06:30, 4 h route: checkpoint at mile 100 is reached ~08:30.
        stormy = flat_series()
        stormy["wind"][8] = 60
        result = self.run_plan([straight_route(200, 4)], lambda i, j: stormy)
        risks = {c["mile"]: c["risk"] for c in result["routes"][0]["checkpoints"]}
        self.assertEqual(risks[0], "Low")       # 06:30
        self.assertEqual(risks[100], "No Travel")  # 08:30 -> hour 8
        self.assertEqual(risks[200], "Low")     # 10:30

    def test_forecast_series_covers_48_hours_from_departure(self):
        series = flat_series()
        series["wind"][6 + 5] = 40
        result = self.run_plan([straight_route(100, 2)], lambda i, j: series, load=50000)
        forecast = result["routes"][0]["checkpoints"][0]["forecast"]
        self.assertEqual(len(forecast), 49)
        self.assertEqual(forecast[5], 3)  # Severe: 35-44 mph with >40,000 lb
        self.assertEqual(forecast[4], 0)

    def test_bad_interval_rejected(self):
        with self.assertRaises(planner.RoutingError):
            planner.plan("A", "B", self.departure, 1000, 30)


class SuggestApiTests(SimpleTestCase):
    def test_short_query_returns_nothing_without_upstream_call(self):
        with mock.patch("trucking.views.suggest_places") as upstream:
            res = self.client.get("/api/trucking/suggest/?q=ch")
        self.assertEqual(res.json(), {"suggestions": []})
        upstream.assert_not_called()

    def test_returns_suggestions(self):
        found = [{"label": "Chicago, Illinois, United States", "lat": 41.9, "lon": -87.6}]
        with mock.patch("trucking.views.suggest_places", return_value=found):
            res = self.client.get("/api/trucking/suggest/?q=chicago")
        self.assertEqual(res.json(), {"suggestions": found})
