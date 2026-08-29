"""Reading values out of a Nightscout profile at a point in time.

Separated from the Nightscout client because the client runs in JavaScript and this runs in
Python, and both need the same rule: a schedule entry applies from its own time until the next
one, and before the first entry of the day the last entry of the previous day is still in force.
"""

from __future__ import annotations

import datetime as dt


def _value_at(schedule, when_ms: float) -> float | None:
    if not schedule:
        return None
    local = dt.datetime.fromtimestamp(when_ms / 1000)
    seconds = local.hour * 3600 + local.minute * 60 + local.second
    # Wraps from the previous day, so a schedule that starts at 06:00 still covers 03:00.
    value = schedule[-1].get("value")
    for e in schedule:
        if e.get("secondsFromMidnight", 0) <= seconds:
            value = e.get("value")
        else:
            break
    return value


def basal_rate_at(profile: dict | None, when_ms: float) -> float | None:
    """Profile basal rate in U/h, before any temp basal or percentage switch."""
    if not profile:
        return None
    return _value_at(profile.get("basal"), when_ms)


def carb_ratio_at(profile: dict | None, when_ms: float) -> float | None:
    """Grams of carbohydrate per unit of insulin."""
    if not profile:
        return None
    return _value_at(profile.get("carbRatio"), when_ms)


def isf_at(profile: dict | None, when_ms: float) -> float | None:
    """Insulin sensitivity factor, in the profile's own units per unit of insulin."""
    if not profile:
        return None
    return _value_at(profile.get("isf"), when_ms)
