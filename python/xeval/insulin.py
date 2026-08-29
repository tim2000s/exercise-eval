"""Insulin on board, and what was done to insulin around a session.

Two questions are answered here. How much rapid-acting insulin was still active when the
session started, which decides how far glucose is likely to fall for a given amount of work.
And what the person actually did to their insulin beforehand, which is what the tool is asked
to evaluate.

The second question is harder than it looks, because Nightscout records what was delivered, not
what would have been delivered otherwise. A basal reduction is visible as a temp basal against
the profile rate, and a profile switch below 100 percent is visible directly, but a bolus
reduction is only recoverable by comparing the dose given against the dose the person's own
carbohydrate ratio and correction factor imply. That comparison is made here and its
assumptions are stated, because a meal whose carbohydrate was underestimated looks identical to
a meal whose bolus was deliberately reduced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MS_PER_MIN = 60_000.0

#: Time to peak activity, in minutes, for the insulins people actually use. These are the
#: values AndroidAPS and oref use for their exponential curves.
PEAK_MINUTES = {
    "rapid": 75,        # aspart, lispro, glulisine
    "ultra-rapid": 55,  # Fiasp, Lyumjev
}


def iob_fraction(minutes_since: float, dia_hours: float = 5.0, peak_minutes: float = 75.0) -> float:
    """Fraction of a bolus still to act, on the exponential model used by oref and AndroidAPS.

    The older bilinear model is not used because it understates tail activity, and the tail is
    exactly the part that matters here: a session starting three hours after a meal bolus sits
    in the tail, and whether that tail holds 5 or 15 percent of the dose changes the advice.

    Returns 1.0 at the moment of the dose and 0.0 at or beyond the duration of action.
    """
    end = dia_hours * 60.0
    if minutes_since <= 0:
        return 1.0
    if minutes_since >= end:
        return 0.0
    if not 0 < peak_minutes < end / 2:
        # The closed form below requires the peak to sit inside the first half of the curve.
        # Clamping is preferable to returning a negative fraction from a nonsensical setting.
        peak_minutes = min(max(peak_minutes, 1.0), end / 2 - 1.0)

    tau = peak_minutes * (1 - peak_minutes / end) / (1 - 2 * peak_minutes / end)
    a = 2 * tau / end
    s = 1 / (1 - a + (1 + a) * math.exp(-end / tau))
    t = minutes_since
    remaining = 1 - s * (1 - a) * (
        ((t * t) / (tau * end * (1 - a)) - t / tau - 1) * math.exp(-t / tau) + 1
    )
    return min(1.0, max(0.0, remaining))


def iob_at(
    when_ms: float,
    doses: list[dict],
    *,
    dia_hours: float = 5.0,
    peak_minutes: float = 75.0,
    include_automatic: bool = True,
) -> dict:
    """Insulin still active at an instant, split by whether the person or the loop gave it.

    The split matters for a report about decisions. Ten units the person bolused for a meal and
    ten units a closed loop delivered as microboluses represent the same insulin and different
    choices, and only the first can be adjusted in advance of a session.
    """
    manual = 0.0
    automatic = 0.0
    for d in doses:
        units = d.get("insulinU")
        if not units:
            continue
        mins = (when_ms - d["t"]) / MS_PER_MIN
        if mins < 0 or mins >= dia_hours * 60:
            continue
        active = units * iob_fraction(mins, dia_hours, peak_minutes)
        if d.get("automatic"):
            automatic += active
        else:
            manual += active
    total = manual + (automatic if include_automatic else 0.0)
    return {"total": total, "manual": manual, "automatic": automatic}


def cob_at(when_ms: float, doses: list[dict], absorption_min: float = 180.0) -> float:
    """Carbohydrate still to absorb, on a linear model.

    A linear decay is deliberate. The physiology is not linear, but the alternatives need a
    glycaemic index and a gastric emptying rate that this tool does not have, and a more
    elaborate curve fitted to nothing would give a false impression of precision. The figure is
    used to say whether a session started on a full stomach, not to dose from.
    """
    total = 0.0
    for d in doses:
        carbs = d.get("carbsG")
        if not carbs:
            continue
        mins = (when_ms - d["t"]) / MS_PER_MIN
        if mins < 0 or mins >= absorption_min:
            continue
        total += carbs * (1 - mins / absorption_min)
    return total


@dataclass(frozen=True)
class BasalAction:
    """What happened to basal insulin around a session."""

    #: Mean delivered basal as a fraction of the profile rate over the window, 1.0 being no change.
    fraction_of_profile: float | None
    #: Minutes before session start at which the reduction began. Negative means it began after
    #: the session had already started, which is the common and least effective case.
    lead_time_min: float | None
    #: How the reduction was made, for the report to name it correctly.
    mechanism: str
    detail: str


def basal_action(
    session_start_ms: float,
    session_end_ms: float,
    treatments: list[dict],
    profile_basal_uph: float | None,
    *,
    lookback_min: float = 180.0,
) -> BasalAction:
    """Reconstruct the delivered basal rate around a session and compare it to the profile.

    Temp basals are read in preference to profile switches because they are what the pump
    actually did. A percentage profile switch is counted where no temp basal covers the window,
    which is the AndroidAPS pattern of switching to a reduced profile for a planned session.
    """
    window_start = session_start_ms - lookback_min * MS_PER_MIN
    tbrs = [t for t in treatments if t.get("kind") == "temp-basal"
            and t["t"] < session_end_ms
            and t["t"] + (t.get("durationMin") or 0) * MS_PER_MIN > window_start]
    switches = [t for t in treatments if t.get("kind") in {"profile-switch", "effective-profile-switch"}
                and t["t"] < session_end_ms
                and t["t"] > window_start - 24 * 3600 * 1000]

    if profile_basal_uph is None or profile_basal_uph <= 0:
        return BasalAction(None, None, "unknown",
                           "No basal rate in the Nightscout profile, so no comparison is possible.")

    # Build the delivered rate over one-minute steps across the session itself. Stepping rather
    # than integrating analytically keeps overlapping and superseded temp basals correct without
    # having to reason about their ordering.
    steps = max(1, int((session_end_ms - session_start_ms) / MS_PER_MIN))
    delivered = []
    for i in range(steps):
        t = session_start_ms + i * MS_PER_MIN
        rate = profile_basal_uph
        for tbr in tbrs:
            dur = (tbr.get("durationMin") or 0) * MS_PER_MIN
            if tbr["t"] <= t < tbr["t"] + dur and tbr.get("rateUph") is not None:
                rate = tbr["rateUph"]
        delivered.append(rate)
    fraction = (sum(delivered) / len(delivered)) / profile_basal_uph

    # A temp basal only counts as this session's reduction if it was still running when the
    # session began, or began during it. One that started and finished inside the lookback
    # window belongs to something else, and reporting it here would contradict the delivered
    # rate computed above, which correctly shows no reduction.
    reducing = [
        t for t in tbrs
        if t.get("rateUph") is not None
        and t["rateUph"] < profile_basal_uph * 0.95
        and t["t"] + (t.get("durationMin") or 0) * MS_PER_MIN > session_start_ms
    ]
    lead_time = None
    mechanism = "none"
    detail = "Basal insulin was left at the profile rate."

    if reducing:
        first = min(reducing, key=lambda t: t["t"])
        lead_time = (session_start_ms - first["t"]) / MS_PER_MIN
        mechanism = "temp basal"
        pct = (1 - first["rateUph"] / profile_basal_uph) * 100
        detail = (
            f"A temp basal cut the rate by {pct:.0f} percent, starting "
            f"{abs(lead_time):.0f} minutes "
            f"{'before' if lead_time >= 0 else 'after'} the session began."
        )
    elif switches:
        reduced = [s for s in switches if (s.get("percentage") or 100) < 95]
        if reduced:
            first = min(reduced, key=lambda s: s["t"])
            lead_time = (session_start_ms - first["t"]) / MS_PER_MIN
            mechanism = "profile switch"
            fraction = (first.get("percentage") or 100) / 100.0
            detail = (
                f"A profile switch to {first['percentage']} percent began "
                f"{abs(lead_time):.0f} minutes "
                f"{'before' if lead_time >= 0 else 'after'} the session."
            )
    if fraction > 1.05:
        mechanism = "increased"
        detail = f"Basal ran {(fraction - 1) * 100:.0f} percent above the profile rate."

    return BasalAction(fraction, lead_time, mechanism, detail)


@dataclass(frozen=True)
class BolusAction:
    """A meal bolus near the session, and how it compared to the person's own ratios."""

    at_ms: float
    minutes_before: float
    carbs_g: float | None
    insulin_given_u: float
    insulin_expected_u: float | None
    #: 0.25 means the dose was a quarter smaller than the ratios imply.
    reduction_fraction: float | None
    caveat: str


def bolus_actions(
    session_start_ms: float,
    treatments: list[dict],
    carb_ratio_g_per_u: float | None,
    *,
    window_hours: float = 3.0,
) -> list[BolusAction]:
    """Find meal boluses shortly before a session and estimate how far each was reduced.

    The estimate compares the insulin given against carbohydrate divided by the person's own
    carbohydrate ratio. That comparison carries a real ambiguity which the caveat names: a meal
    whose carbohydrate was underestimated, a dose that also covered a correction, and a dose
    deliberately reduced for exercise all look the same from the outside. The tool reports the
    arithmetic and lets the reader decide which it was.
    """
    out: list[BolusAction] = []
    window_start = session_start_ms - window_hours * 3600 * 1000

    for d in treatments:
        if d.get("kind") != "dose" or d.get("automatic"):
            continue
        if not (window_start <= d["t"] < session_start_ms):
            continue
        insulin = d.get("insulinU") or 0.0
        carbs = d.get("carbsG")
        if insulin <= 0:
            continue

        expected = None
        reduction = None
        caveat = ""
        if carbs and carb_ratio_g_per_u:
            expected = carbs / carb_ratio_g_per_u
            reduction = 1 - (insulin / expected) if expected > 0 else None
            caveat = (
                "Compared against carbohydrate divided by the profile carbohydrate ratio. A "
                "meal whose carbohydrate was underestimated, a dose that also covered a "
                "correction, and a dose deliberately reduced for exercise are "
                "indistinguishable from the record."
            )
        elif not carbs:
            caveat = (
                "No carbohydrate was recorded with this dose, so there is nothing to compare "
                "it against. It may have been a correction."
            )
        else:
            caveat = "No carbohydrate ratio in the Nightscout profile, so no comparison is possible."

        out.append(BolusAction(
            at_ms=d["t"],
            minutes_before=(session_start_ms - d["t"]) / MS_PER_MIN,
            carbs_g=carbs,
            insulin_given_u=insulin,
            insulin_expected_u=expected,
            reduction_fraction=reduction,
            caveat=caveat,
        ))

    out.sort(key=lambda b: b.at_ms)
    return out


def temp_target_action(session_start_ms: float, session_end_ms: float,
                       treatments: list[dict]) -> dict | None:
    """Find a temporary target covering the session, which on a closed loop is the real lever.

    A temp target with reason Activity is the strongest available signal that exercise was
    announced to the system, because it is the thing that actually changed the algorithm's
    behaviour rather than merely recording an intention.
    """
    candidates = []
    for t in treatments:
        if t.get("kind") != "temp-target":
            continue
        dur = (t.get("durationMin") or 0) * MS_PER_MIN
        if t["t"] < session_end_ms and t["t"] + dur > session_start_ms - 2 * 3600 * 1000:
            candidates.append(t)
    if not candidates:
        return None
    best = min(candidates, key=lambda t: abs(t["t"] - session_start_ms))
    return {
        "at_ms": best["t"],
        "lead_time_min": (session_start_ms - best["t"]) / MS_PER_MIN,
        "reason": best.get("reason"),
        "target_mmol": best.get("targetTopMmol"),
        "duration_min": best.get("durationMin"),
        "announced_as_exercise": best.get("reason") == "Activity",
    }
