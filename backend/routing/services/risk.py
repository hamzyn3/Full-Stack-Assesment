"""Weather risk classification (pure functions, no I/O).

Threshold bands from the task:

    Wind   (mph)   : Low <25 | Moderate 25-34 | High 35-44 | Severe 45-54 | No Travel >=55
    Rain   (in/hr) : Low <0.10 | Moderate 0.10-0.25 | High 0.25-0.50 | Severe 0.50-1.00 | No Travel >1.0

Boundary decisions for continuous values (documented in the README):
  * Wind bands include their lower bound: 25 <= w < 35 is Moderate, w >= 55 is No Travel.
  * Rain bands include their upper bound, matching the table's ">1.0" for No Travel:
    0.10 <= r <= 0.25 is Moderate, 0.25 < r <= 0.50 is High, 0.50 < r <= 1.00 is Severe,
    r > 1.0 is No Travel; r < 0.10 is Low.

Load rules (wind-based escalation, never lowers a level):
  * wind >= 55 mph          -> No Travel for any load
  * 45 <= wind < 55, load > 30,000 lb -> No Travel
  * 35 <= wind < 45, load > 40,000 lb -> Severe
"""

from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def key(self) -> str:
        return self.name.lower()


WIND_MODERATE_MPH = 25
WIND_HIGH_MPH = 35
WIND_SEVERE_MPH = 45
WIND_NO_TRAVEL_MPH = 55

RAIN_MODERATE_IN_HR = 0.10
RAIN_HIGH_IN_HR = 0.25
RAIN_SEVERE_IN_HR = 0.50
RAIN_NO_TRAVEL_IN_HR = 1.00

HEAVY_LOAD_NO_TRAVEL_LB = 30_000  # with wind 45-54 mph
HEAVY_LOAD_SEVERE_LB = 40_000  # with wind 35-44 mph


def wind_level(wind_mph: float) -> RiskLevel:
    if wind_mph >= WIND_NO_TRAVEL_MPH:
        return RiskLevel.NO_TRAVEL
    if wind_mph >= WIND_SEVERE_MPH:
        return RiskLevel.SEVERE
    if wind_mph >= WIND_HIGH_MPH:
        return RiskLevel.HIGH
    if wind_mph >= WIND_MODERATE_MPH:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def rain_level(rain_in_hr: float) -> RiskLevel:
    if rain_in_hr > RAIN_NO_TRAVEL_IN_HR:
        return RiskLevel.NO_TRAVEL
    if rain_in_hr > RAIN_SEVERE_IN_HR:
        return RiskLevel.SEVERE
    if rain_in_hr > RAIN_HIGH_IN_HR:
        return RiskLevel.HIGH
    if rain_in_hr >= RAIN_MODERATE_IN_HR:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def load_escalation(wind_mph: float, load_lb: float) -> RiskLevel:
    """Minimum risk level that the load rules impose at this wind speed."""
    if wind_mph >= WIND_NO_TRAVEL_MPH:
        return RiskLevel.NO_TRAVEL
    if wind_mph >= WIND_SEVERE_MPH and load_lb > HEAVY_LOAD_NO_TRAVEL_LB:
        return RiskLevel.NO_TRAVEL
    if wind_mph >= WIND_HIGH_MPH and wind_mph < WIND_SEVERE_MPH and load_lb > HEAVY_LOAD_SEVERE_LB:
        return RiskLevel.SEVERE
    return RiskLevel.LOW


def classify(wind_mph: float, rain_in_hr: float, load_lb: float) -> RiskLevel:
    """Overall risk at a checkpoint: the worst of wind, rain and the load rules."""
    return max(wind_level(wind_mph), rain_level(rain_in_hr), load_escalation(wind_mph, load_lb))
