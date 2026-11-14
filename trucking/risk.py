"""Weather risk classification for a single checkpoint (pure functions)."""
from bisect import bisect_right

LEVELS = ["Low", "Moderate", "High", "Severe", "No Travel"]
LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL = range(5)

# Lower bound of Moderate, High, Severe, No Travel. A value on a boundary
# falls in the higher band (wind 35 is High; rain 0.25 is High).
WIND_BOUNDS = [25, 35, 45, 55]
RAIN_BOUNDS = [0.10, 0.25, 0.50]  # "No Travel" is strictly > 1.00
SNOW_BOUNDS = [0.5, 1.0, 2.0]  # "No Travel" is strictly > 3.0


def wind_level(mph):
    return bisect_right(WIND_BOUNDS, mph)


def _precip_level(value, bounds, no_travel_above):
    if value > no_travel_above:
        return NO_TRAVEL
    return min(bisect_right(bounds, value), SEVERE)


def rain_level(inches_per_hr):
    return _precip_level(inches_per_hr, RAIN_BOUNDS, 1.00)


def snow_level(inches_per_hr):
    return _precip_level(inches_per_hr, SNOW_BOUNDS, 3.0)


def classify(wind_mph, rain_in_hr, snow_in_hr, load_lbs):
    """Return (level 0-4, driver) where driver names what set the level."""
    candidates = [(wind_level(wind_mph), "wind"), (rain_level(rain_in_hr), "rain"), (snow_level(snow_in_hr), "snow")]

    # Load-based escalation of wind risk.
    if wind_mph >= 55:
        candidates.append((NO_TRAVEL, "wind"))
    elif wind_mph >= 45 and load_lbs > 30000:
        candidates.append((NO_TRAVEL, "wind + heavy load"))
    elif wind_mph >= 35 and load_lbs > 40000:
        candidates.append((SEVERE, "wind + heavy load"))

    level, driver = max(candidates, key=lambda c: c[0])
    return level, (driver if level > LOW else "none")
