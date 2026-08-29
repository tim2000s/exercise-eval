"""Synthetic days with a known answer, so a test can assert what should have been found.

Each builder returns entries, treatments and one session. The glucose trajectories are shaped
by hand rather than simulated, because the point is to exercise the analysis against a known
answer, not to model physiology twice.
"""

from __future__ import annotations

import datetime as dt
import math

MIN = 60_000
HOUR = 3_600_000


def day_start(y=2026, m=8, d=3) -> float:
    return dt.datetime(y, m, d, 0, 0).timestamp() * 1000


def cgm(base_ms: float, hours: float, fn, step_min: int = 5) -> list[dict]:
    """Build a CGM series from a function of hours since base."""
    n = int(hours * 60 / step_min)
    return [{"t": base_ms + i * step_min * MIN, "mmol": fn(i * step_min / 60.0)}
            for i in range(n)]


def hr_series(start_ms: float, minutes: int, fn, step_s: int = 10) -> list[dict]:
    n = int(minutes * 60 / step_s)
    return [{"t": start_ms + i * step_s * 1000, "bpm": fn(i * step_s / 60.0)} for i in range(n)]


def aerobic_fall_with_overnight_low():
    """An evening run with no insulin reduction, a fall during, and a low at 03:00.

    This is the DirecNet shape: an unadjusted afternoon session followed by a delayed
    nocturnal excursion in the 7 to 11 hour window.
    """
    base = day_start()
    s_start = base + 18 * HOUR
    s_end = s_start + 45 * MIN

    def g(h):
        if h < 17.0:
            return 7.5 + 0.8 * math.sin(h / 2)
        if h < 18.0:
            return 9.5                      # a meal, fully bolused
        if h < 18.75:
            return 9.5 - 6.0 * ((h - 18.0) / 0.75)   # falls to 3.5 during the run
        if h < 20.0:
            return 3.5 + 3.4 * ((h - 18.75) / 1.25)
        if h < 26.0:
            return 6.9 - 0.35 * (h - 20.0)
        if h < 29.0:
            return 4.8 - 1.4 * math.sin((h - 26.0) / 3.0 * math.pi)   # nadir 3.4 near 03:30
        return 4.5 + 0.5 * (h - 29.0)

    entries = cgm(base, 34, g)
    treatments = [
        # A full meal bolus 90 minutes before, at the profile ratio of 10 g/U.
        {"kind": "dose", "t": s_start - 90 * MIN, "insulinU": 6.0, "carbsG": 60,
         "automatic": False, "eventType": "Meal Bolus"},
    ]
    session = {
        "id": "run-1", "start": s_start, "end": s_end, "typeName": "RUNNING",
        "modality": "aerobic", "title": "Evening run",
        "hr": hr_series(s_start, 45, lambda m: 150 + 5 * math.sin(m / 6)),
    }
    return entries, treatments, session


def well_managed_aerobic():
    """The same run done with a basal reduction started 90 minutes ahead and carbohydrate."""
    base = day_start()
    s_start = base + 18 * HOUR
    s_end = s_start + 45 * MIN

    def g(h):
        if h < 18.0:
            return 8.2
        if h < 18.75:
            return 8.2 - 1.4 * ((h - 18.0) / 0.75)
        if h < 30.0:
            return 6.8 + 0.4 * math.sin(h)
        return 6.5

    entries = cgm(base, 34, g)
    treatments = [
        {"kind": "dose", "t": s_start - 90 * MIN, "insulinU": 3.0, "carbsG": 60,
         "automatic": False, "eventType": "Meal Bolus"},
        {"kind": "temp-basal", "t": s_start - 90 * MIN, "rateUph": 0.3, "durationMin": 180,
         "eventType": "Temp Basal"},
        {"kind": "temp-target", "t": s_start - 45 * MIN, "reason": "Activity",
         "targetTopMmol": 8.3, "targetBottomMmol": 8.3, "durationMin": 120},
        {"kind": "dose", "t": s_start + 20 * MIN, "carbsG": 20, "automatic": False,
         "eventType": "Carb Correction"},
    ]
    session = {
        "id": "run-2", "start": s_start, "end": s_end, "typeName": "RUNNING",
        "modality": "aerobic", "title": "Evening run",
        "hr": hr_series(s_start, 45, lambda m: 148 + 5 * math.sin(m / 6)),
    }
    return entries, treatments, session


def anaerobic_rise():
    """A short hard interval session where glucose rises, as high-intensity work commonly does."""
    base = day_start()
    s_start = base + 7 * HOUR
    s_end = s_start + 25 * MIN

    def g(h):
        if h < 7.0:
            return 6.5
        if h < 7.5:
            return 6.5 + 4.0 * ((h - 7.0) / 0.5)     # rises to 10.5
        if h < 10.0:
            return 10.5 - 3.5 * ((h - 7.5) / 2.5)
        return 7.0

    entries = cgm(base, 30, g)
    session = {
        "id": "hiit-1", "start": s_start, "end": s_end,
        "typeName": "HIGH_INTENSITY_INTERVAL_TRAINING", "modality": "anaerobic",
        "hr": hr_series(s_start, 25, lambda m: 175 if int(m) % 2 else 130),
    }
    return entries, [], session


def antecedent_hypo_day():
    """A session preceded by substantial time below range, the strongest predictor available."""
    base = day_start()
    s_start = base + 18 * HOUR
    s_end = s_start + 60 * MIN

    def g(h):
        if 2.0 <= h < 6.0:
            return 3.4                       # four hours below range overnight
        if h < 18.0:
            return 7.0
        if h < 19.0:
            return 7.0 - 2.0 * (h - 18.0)
        return 5.5

    entries = cgm(base, 30, g)
    session = {
        "id": "run-3", "start": s_start, "end": s_end, "typeName": "RUNNING",
        "modality": "aerobic",
        "hr": hr_series(s_start, 60, lambda m: 145),
    }
    return entries, [], session


PROFILE = {
    "name": "Test",
    "units": "mmol",
    "dia": 5.0,
    "basal": [{"secondsFromMidnight": 0, "value": 1.0}],
    "carbRatio": [{"secondsFromMidnight": 0, "value": 10.0}],
    "isf": [{"secondsFromMidnight": 0, "value": 2.0}],
    "targetLow": [{"secondsFromMidnight": 0, "value": 5.5}],
    "targetHigh": [{"secondsFromMidnight": 0, "value": 8.0}],
}

SETTINGS = {"age_years": 45, "body_mass_kg": 78, "resting_hr": 52, "units": "mmol",
            "risk_group": "low"}
