"""What happened to glucose around a session, measured rather than assumed.

This module makes no recommendations. It reports the trajectory, the excursions and the
exposures, and it is explicit about coverage: a nadir computed from a series with a
forty-minute gap in it is not a nadir, and saying so is more useful than reporting a number
that happens to be the lowest of what survived.

Interstitial glucose is not blood glucose during exercise. The pooled mean absolute relative
difference across exercise types is about 13.6 percent and the lag lengthens from around five
minutes at rest to twelve to twenty-four minutes while glucose is moving. Every figure here is
therefore a sensor figure, and where one is close to a threshold that matters the report says
how far the sensor could be out.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

MS_PER_MIN = 60_000.0
MS_PER_HOUR = 3_600_000.0

#: Level 1 and level 2 hypoglycaemia, as the international consensus defines them.
HYPO_L1_MMOL = 3.9   # 70 mg/dL
HYPO_L2_MMOL = 3.0   # 54 mg/dL
HYPER_MMOL = 10.0    # 180 mg/dL

#: A reading is considered to cover the five minutes that follow it. Two readings more than
#: this far apart leave a gap, and a gap is reported rather than interpolated across.
MAX_GAP_MIN = 20.0

#: A hypoglycaemic excursion has to last this long to be counted, matching the definition used
#: in T1DEXI and in the CGM consensus, so that one aberrant reading does not become an event.
MIN_EVENT_MIN = 15.0


@dataclass(frozen=True)
class Window:
    """Glucose over one interval, with an honest account of how well it was covered."""

    label: str
    start_ms: float
    end_ms: float
    n: int
    coverage: float                 # fraction of the interval with readings
    largest_gap_min: float
    first_mmol: float | None
    last_mmol: float | None
    mean_mmol: float | None
    nadir_mmol: float | None
    nadir_at_ms: float | None
    peak_mmol: float | None
    time_below_l1: float            # fraction of covered time
    time_below_l2: float
    time_in_range: float
    time_above: float
    hypo_events: int
    #: Change from first to last, in mmol/L. Positive means glucose rose.
    change_mmol: float | None
    #: Mean rate over the window, mmol/L per minute.
    rate_mmol_min: float | None

    @property
    def is_reliable(self) -> bool:
        """Whether the window is covered well enough for its numbers to be quoted plainly."""
        return self.coverage >= 0.7 and self.largest_gap_min <= 45

    def coverage_note(self) -> str | None:
        if self.n == 0:
            return f"No sensor readings at all in the {self.label} window."
        if self.is_reliable:
            return None
        return (
            f"The {self.label} window has {self.coverage * 100:.0f} percent sensor coverage "
            f"with a largest gap of {self.largest_gap_min:.0f} minutes. Figures from it are "
            f"indicative rather than measured."
        )


def _slice(entries: list[dict], start_ms: float, end_ms: float) -> list[dict]:
    """Readings within an interval. Entries are assumed sorted by t, which the client guarantees."""
    times = [e["t"] for e in entries]
    lo = bisect.bisect_left(times, start_ms)
    hi = bisect.bisect_right(times, end_ms)
    return entries[lo:hi]


def summarise(entries: list[dict], start_ms: float, end_ms: float, label: str) -> Window:
    """Reduce a slice of CGM to the figures the report needs, coverage included."""
    span_min = max(1e-9, (end_ms - start_ms) / MS_PER_MIN)
    rows = _slice(entries, start_ms, end_ms)

    if not rows:
        return Window(label, start_ms, end_ms, 0, 0.0, span_min, None, None, None, None, None,
                      None, 0.0, 0.0, 0.0, 0.0, 0, None, None)

    # Each reading covers the interval to the next one, capped so that a long gap contributes
    # its true absence rather than being smeared across the window.
    covered = 0.0
    largest_gap = max(
        (rows[0]["t"] - start_ms) / MS_PER_MIN,
        (end_ms - rows[-1]["t"]) / MS_PER_MIN,
    )
    weights: list[float] = []
    for i, r in enumerate(rows):
        if i + 1 < len(rows):
            gap = (rows[i + 1]["t"] - r["t"]) / MS_PER_MIN
        else:
            gap = min(MAX_GAP_MIN, (end_ms - r["t"]) / MS_PER_MIN)
        largest_gap = max(largest_gap, gap)
        w = min(gap, MAX_GAP_MIN)
        weights.append(w)
        covered += w

    values = [r["mmol"] for r in rows]
    total_w = sum(weights) or 1.0

    def frac(pred) -> float:
        return sum(w for v, w in zip(values, weights) if pred(v)) / total_w

    nadir_i = min(range(len(values)), key=lambda i: values[i])
    change = values[-1] - values[0]

    return Window(
        label=label, start_ms=start_ms, end_ms=end_ms, n=len(rows),
        coverage=min(1.0, covered / span_min), largest_gap_min=largest_gap,
        first_mmol=values[0], last_mmol=values[-1],
        mean_mmol=sum(v * w for v, w in zip(values, weights)) / total_w,
        nadir_mmol=values[nadir_i], nadir_at_ms=rows[nadir_i]["t"],
        peak_mmol=max(values),
        time_below_l1=frac(lambda v: v < HYPO_L1_MMOL),
        time_below_l2=frac(lambda v: v < HYPO_L2_MMOL),
        time_in_range=frac(lambda v: HYPO_L1_MMOL <= v <= HYPER_MMOL),
        time_above=frac(lambda v: v > HYPER_MMOL),
        hypo_events=count_events(rows, HYPO_L1_MMOL),
        change_mmol=change,
        rate_mmol_min=change / span_min if span_min > 0 else None,
    )


def count_events(rows: list[dict], threshold_mmol: float,
                 min_minutes: float = MIN_EVENT_MIN) -> int:
    """Count excursions below a threshold that lasted long enough to be events.

    An excursion ends when glucose has been back above the threshold for fifteen minutes, so a
    reading that bounces above it briefly does not split one event into two.
    """
    events = 0
    below_since: float | None = None
    above_since: float | None = None

    for r in rows:
        if r["mmol"] < threshold_mmol:
            above_since = None
            if below_since is None:
                below_since = r["t"]
            elif (r["t"] - below_since) / MS_PER_MIN >= min_minutes - 1e-9:
                pass  # already counted on the transition below
        else:
            if below_since is not None:
                if above_since is None:
                    above_since = r["t"]
                if (r["t"] - above_since) / MS_PER_MIN >= min_minutes:
                    duration = (above_since - below_since) / MS_PER_MIN
                    if duration >= min_minutes:
                        events += 1
                    below_since = None
                    above_since = None
    if below_since is not None and rows:
        if (rows[-1]["t"] - below_since) / MS_PER_MIN >= min_minutes:
            events += 1
    return events


def steepest_fall(entries: list[dict], start_ms: float, end_ms: float,
                  span_min: float = 30.0) -> float | None:
    """The fastest sustained fall over any window of the given span, in mmol/L per minute.

    The mean rate across a whole session hides the part that matters. A session that fell
    steeply for twenty minutes and then flattened has the same mean rate as one that drifted
    down throughout, and only the first is a near miss.
    """
    rows = _slice(entries, start_ms, end_ms)
    if len(rows) < 3:
        return None
    worst = None
    j = 0
    for i in range(len(rows)):
        while j < len(rows) and (rows[j]["t"] - rows[i]["t"]) / MS_PER_MIN < span_min:
            j += 1
        if j >= len(rows):
            break
        dt = (rows[j]["t"] - rows[i]["t"]) / MS_PER_MIN
        if dt <= 0:
            continue
        rate = (rows[j]["mmol"] - rows[i]["mmol"]) / dt
        if worst is None or rate < worst:
            worst = rate
    return worst


def carbs_in_window(treatments: list[dict], start_ms: float, end_ms: float) -> float:
    return sum(t.get("carbsG") or 0 for t in treatments
               if t.get("kind") == "dose" and start_ms <= t["t"] < end_ms)


def insulin_in_window(treatments: list[dict], start_ms: float, end_ms: float) -> dict:
    manual = sum(t.get("insulinU") or 0 for t in treatments
                 if t.get("kind") == "dose" and not t.get("automatic")
                 and start_ms <= t["t"] < end_ms)
    auto = sum(t.get("insulinU") or 0 for t in treatments
               if t.get("kind") == "dose" and t.get("automatic")
               and start_ms <= t["t"] < end_ms)
    return {"manual": manual, "automatic": auto, "total": manual + auto}


@dataclass
class SessionGlucose:
    """Every glucose window the evaluation and the recommendations depend on."""

    during: Window
    recovery: Window          # the first 90 minutes after, where EASD/ISPAD sets a floor
    late: Window              # 7 to 11 hours after, the delayed peak McMahon measured
    overnight: Window | None  # midnight to 06:00 following, where a session ran late enough
    antecedent: Window        # the 24 hours before, which predicts nocturnal risk
    steepest_fall_mmol_min: float | None
    carbs_during_g: float
    carbs_recovery_g: float
    insulin_during: dict
    notes: list[str] = field(default_factory=list)


def evaluate_session(entries: list[dict], treatments: list[dict],
                     start_ms: float, end_ms: float) -> SessionGlucose:
    """Assemble every window for one session.

    The overnight window is only computed where the session ended early enough for the delayed
    risk period to reach into the night. Midday exercise produces a single continuous elevation
    in glucose requirement lasting about eleven hours with no separate late peak, which is why
    a lunchtime session gets no overnight assessment rather than an empty one.
    """
    during = summarise(entries, start_ms, end_ms, "session")
    recovery = summarise(entries, end_ms, end_ms + 90 * MS_PER_MIN, "first 90 minutes after")
    late = summarise(entries, end_ms + 7 * MS_PER_HOUR, end_ms + 11 * MS_PER_HOUR,
                     "7 to 11 hours after")
    antecedent = summarise(entries, start_ms - 24 * MS_PER_HOUR, start_ms, "24 hours before")

    notes: list[str] = []

    # Midnight to 06:00 on the night following the session, in the browser's local time. The
    # window is only meaningful when the session finished before it began.
    import datetime as _dt
    end_local = _dt.datetime.fromtimestamp(end_ms / 1000)
    night_start = _dt.datetime(end_local.year, end_local.month, end_local.day) + _dt.timedelta(days=1)
    if end_local.hour < 6:
        night_start -= _dt.timedelta(days=1)
    night_start_ms = night_start.timestamp() * 1000
    overnight = None
    if night_start_ms > end_ms:
        overnight = summarise(entries, night_start_ms, night_start_ms + 6 * MS_PER_HOUR,
                              "midnight to 06:00")
    else:
        notes.append(
            "This session ran into the small hours, so there is no following overnight window "
            "to assess separately."
        )

    for w in (during, recovery, late, antecedent, overnight):
        if w is not None:
            n = w.coverage_note()
            if n:
                notes.append(n)

    return SessionGlucose(
        during=during, recovery=recovery, late=late, overnight=overnight, antecedent=antecedent,
        steepest_fall_mmol_min=steepest_fall(entries, start_ms, end_ms),
        carbs_during_g=carbs_in_window(treatments, start_ms, end_ms),
        carbs_recovery_g=carbs_in_window(treatments, end_ms, end_ms + 90 * MS_PER_MIN),
        insulin_during=insulin_in_window(treatments, start_ms, end_ms),
        notes=notes,
    )
