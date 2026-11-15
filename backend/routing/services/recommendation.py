"""Rank routes and explain the recommendation.

Preference order (from the task), with No Travel miles checked first because a
route that cannot be driven must never beat one that can:

    0. fewest No Travel miles
    1. fewest Severe miles
    2. fewest High miles
    3. lowest average risk
    4. shortest travel time

Miles are compared at 0.1 mi and average risk at 0.01 so float noise from
segment arithmetic cannot decide a tie.
"""

from dataclasses import dataclass

from .analysis import RouteAnalysis
from .risk import RiskLevel


def rank_key(analysis: RouteAnalysis) -> tuple:
    miles = analysis.miles_by_risk
    return (
        round(miles[RiskLevel.NO_TRAVEL], 1),
        round(miles[RiskLevel.SEVERE], 1),
        round(miles[RiskLevel.HIGH], 1),
        round(analysis.average_risk, 2),
        analysis.route.duration_seconds,
    )


@dataclass(frozen=True)
class Recommendation:
    ranked: list[RouteAnalysis]  # best first
    reason: str
    all_routes_blocked: bool

    @property
    def best(self) -> RouteAnalysis:
        return self.ranked[0]


def recommend(analyses: list[RouteAnalysis]) -> Recommendation:
    ranked = sorted(analyses, key=rank_key)
    best = ranked[0]
    return Recommendation(
        ranked=ranked,
        reason=_explain(ranked),
        all_routes_blocked=best.has_no_travel,
    )


def _explain(ranked: list[RouteAnalysis]) -> str:
    best = ranked[0]
    if len(ranked) == 1:
        return f"{best.route.name} is the only route available."

    other = ranked[1]
    a, b = rank_key(best), rank_key(other)
    names = f"{best.route.name} vs {other.route.name}"

    if best.has_no_travel:
        return (
            f"Every route has No Travel conditions; {best.route.name} has the fewest No Travel miles "
            f"({a[0]:.1f} vs {b[0]:.1f} on {other.route.name})."
        )
    if a[1] != b[1]:
        return f"Fewest Severe miles ({names}: {a[1]:.1f} vs {b[1]:.1f})."
    if a[2] != b[2]:
        return f"Same Severe miles, fewest High miles ({names}: {a[2]:.1f} vs {b[2]:.1f})."
    if a[3] != b[3]:
        return f"Same Severe and High miles, lowest average risk ({names}: {a[3]:.2f} vs {b[3]:.2f})."
    return "Routes have equal weather risk; this one has the shortest travel time."
