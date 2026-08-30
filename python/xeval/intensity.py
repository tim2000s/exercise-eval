"""How hard a session actually was, from heart rate rather than from its label.

A jog and a threshold run both carry the label RUNNING and behave differently, so the activity
type is treated as a prior and heart rate, where it exists, overrides it. Where no heart rate
exists the prior is all there is and the report says so, because a recommendation resting on a
label alone deserves less confidence than one resting on a measurement.

Intensity is expressed as a fraction of heart rate reserve rather than as a fraction of maximum
heart rate. Heart rate reserve is the closer proxy for fraction of VO2max, which is the variable
the exercise physiology in this field is written in, and it accounts for the resting heart rate
of a trained person rather than treating them as unfit.

The distinction the glucose response turns on is not simply hard against easy. Continuous work
at a moderate fraction of reserve lowers glucose; brief work at a high fraction raises it
through the sympathoadrenal response; and intermittent work does both, which is why a measure of
how much the heart rate moved about within the session is computed alongside its mean.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Intensity:
    """What a session's heart rate says about it."""

    #: Mean fraction of heart rate reserve across the session, 0 to 1. None without heart rate.
    mean_hrr: float | None
    peak_hrr: float | None
    #: Fraction of the session spent above 0.8 of reserve, which is where the counterregulatory
    #: response starts to dominate the insulin-independent uptake.
    fraction_high: float | None
    #: Coefficient of variation of heart rate within the session. A steady effort sits near
    #: 0.05; interval work runs well above it.
    variation: float | None
    band: str
    #: aerobic, anaerobic, mixed, resistance or low, after heart rate has had its say.
    modality: str
    #: measured, label-only, or absent. Carried into every recommendation that depends on it.
    basis: str
    notes: tuple[str, ...] = ()

    @property
    def is_measured(self) -> bool:
        return self.basis == "measured"


#: American College of Sports Medicine bands, as fractions of heart rate reserve.
BANDS: tuple[tuple[str, float, float], ...] = (
    ("very light", 0.0, 0.30),
    ("light", 0.30, 0.40),
    ("moderate", 0.40, 0.60),
    ("vigorous", 0.60, 0.90),
    ("near maximal", 0.90, 10.0),
)

#: Above this fraction of reserve, a session is doing enough anaerobic work for the
#: catecholamine response to start opposing the fall in glucose.
HIGH_INTENSITY_FRACTION = 0.80

#: Coefficient of variation above which a session is treated as intermittent rather than steady.
#: This is a working threshold chosen from the shape of the data rather than a published cut
#: point, and it is stated as such wherever it changes a recommendation.
INTERVAL_CV_THRESHOLD = 0.12


def estimate_hr_max(age_years: float | None) -> float | None:
    """Estimate maximum heart rate from age.

    Uses 208 minus 0.7 times age (Tanaka et al. 2001, meta-analysis of 351 studies and 492
    groups), rather than the older 220 minus age, which overestimates in young adults and
    underestimates past about 40. Either way the estimate carries a standard deviation of
    roughly 10 beats per minute between individuals, so a measured maximum from a hard session
    is always preferred where one exists.
    """
    if age_years is None or age_years <= 0:
        return None
    return 208.0 - 0.7 * age_years


def _percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile. Written out because numpy is not assumed under Pyodide."""
    if not values:
        raise ValueError("no values")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def analyse(
    hr_samples: list[dict],
    *,
    label_modality: str = "unknown",
    resting_hr: float | None = None,
    max_hr: float | None = None,
    age_years: float | None = None,
    duration_min: float | None = None,
    summary_avg_hr: float | None = None,
    summary_max_hr: float | None = None,
) -> Intensity:
    """Combine the activity label with whatever heart rate evidence exists.

    hr_samples are dicts with t in epoch milliseconds and bpm. An empty list is expected and
    handled: many sessions arrive from apps that never wrote heart rate.

    Where no series exists but a summary average and maximum do, as a Strava activity carries
    before its stream is fetched, those are used instead. That gives a defensible mean fraction
    of reserve, and nothing else: a mean says nothing about whether the session was steady or
    intervals, so the variation is left unknown and the modality falls back to the label rather
    than being inferred from a shape that was not measured.
    """
    notes: list[str] = []

    usable = [s["bpm"] for s in hr_samples if s.get("bpm") and 30 <= s["bpm"] <= 230]
    if len(usable) < 5:
        if hr_samples:
            notes.append(
                f"Only {len(usable)} usable heart rate readings, so intensity comes from the "
                f"activity label alone."
            )
        if summary_avg_hr:
            return _from_summary(
                summary_avg_hr, summary_max_hr, label_modality, resting_hr, max_hr, age_years,
                notes,
            )
        return Intensity(
            mean_hrr=None, peak_hrr=None, fraction_high=None, variation=None,
            band="not measured", modality=label_modality,
            basis="label-only" if label_modality != "unknown" else "absent",
            notes=tuple(notes),
        )

    if max_hr is None:
        max_hr = estimate_hr_max(age_years)
        if max_hr is not None:
            notes.append(
                f"Maximum heart rate estimated as {max_hr:.0f} bpm from age using Tanaka's "
                f"equation. Between individuals that estimate carries a standard deviation of "
                f"about 10 bpm, so the intensity fractions below are approximate."
            )
    if max_hr is None:
        # Without a ceiling, the peak observed in the session is the only anchor available. It
        # underestimates reserve for an easy session, which biases intensity upwards, so the
        # note says so rather than letting the number stand unqualified.
        max_hr = max(usable)
        notes.append(
            "No age or maximum heart rate was given, so the session's own peak was used as the "
            "ceiling. That understates the reserve of an easy session and therefore overstates "
            "its intensity. Entering an age in the settings removes this."
        )

    if resting_hr is None:
        # The lowest few readings in a session are not a resting heart rate, but they bound it.
        resting_hr = min(_percentile(usable, 0.02), 70.0)
        notes.append(
            f"No resting heart rate was available, so {resting_hr:.0f} bpm was assumed from the "
            f"lowest readings in the session."
        )

    reserve = max_hr - resting_hr
    if reserve < 20:
        notes.append(
            "The gap between resting and maximum heart rate is implausibly small, so the "
            "intensity fractions are unreliable. Check the age and resting heart rate settings."
        )
        reserve = max(reserve, 20.0)

    fractions = [max(0.0, (b - resting_hr) / reserve) for b in usable]
    mean_hrr = sum(fractions) / len(fractions)
    peak_hrr = _percentile(fractions, 0.95)  # 95th centile, so one spurious spike does not set it
    fraction_high = sum(1 for f in fractions if f >= HIGH_INTENSITY_FRACTION) / len(fractions)

    mean_bpm = sum(usable) / len(usable)
    sd = math.sqrt(sum((b - mean_bpm) ** 2 for b in usable) / len(usable))
    variation = sd / mean_bpm if mean_bpm else 0.0

    band = next(name for name, lo, hi in BANDS if lo <= mean_hrr < hi)

    modality = _modality_from_measurement(
        label_modality, mean_hrr, peak_hrr, fraction_high, variation, duration_min, notes
    )

    return Intensity(
        mean_hrr=mean_hrr, peak_hrr=peak_hrr, fraction_high=fraction_high,
        variation=variation, band=band, modality=modality, basis="measured",
        notes=tuple(notes),
    )


def _from_summary(
    avg_hr: float,
    max_session_hr: float | None,
    label_modality: str,
    resting_hr: float | None,
    max_hr: float | None,
    age_years: float | None,
    notes: list[str],
) -> Intensity:
    """Intensity from an average and a maximum, with no series behind them."""
    if max_hr is None:
        max_hr = estimate_hr_max(age_years)
    if max_hr is None:
        # Without a ceiling there is no reserve to take a fraction of, and a session maximum is
        # not one: taking it as the ceiling would call every session maximal.
        notes.append(
            "This session has an average heart rate but no series and no age, so no fraction of "
            "reserve can be worked out. Entering an age in the settings would allow one."
        )
        return Intensity(
            mean_hrr=None, peak_hrr=None, fraction_high=None, variation=None,
            band="not measured", modality=label_modality, basis="label-only",
            notes=tuple(notes),
        )
    if resting_hr is None:
        resting_hr = 70.0
        notes.append(
            "No resting heart rate was available, so 70 bpm was assumed for this session's "
            "intensity."
        )
    reserve = max(20.0, max_hr - resting_hr)
    mean_hrr = max(0.0, (avg_hr - resting_hr) / reserve)
    peak_hrr = (max(0.0, (max_session_hr - resting_hr) / reserve)
                if max_session_hr else None)
    band = next(name for name, lo, hi in BANDS if lo <= mean_hrr < hi)

    notes.append(
        "Intensity for this session comes from the average and maximum heart rate in the "
        "activity summary rather than from a recorded series. That fixes how hard it was on "
        "average and says nothing about whether it was steady or intervals, so the kind of work "
        "is still taken from the activity label."
    )
    return Intensity(
        mean_hrr=mean_hrr, peak_hrr=peak_hrr, fraction_high=None, variation=None,
        band=band, modality=label_modality, basis="summary", notes=tuple(notes),
    )


def _modality_from_measurement(
    label_modality: str,
    mean_hrr: float,
    peak_hrr: float,
    fraction_high: float,
    variation: float,
    duration_min: float | None,
    notes: list[str],
) -> str:
    """Decide the glycaemic modality, letting heart rate override the label where they disagree.

    Resistance work is left alone. Its heart rate signature, a moderate mean with wide swings,
    is close to interval work, and the label is the more reliable discriminator there. Nothing
    in heart rate distinguishes a set of deadlifts from a hill rep.
    """
    if label_modality == "resistance":
        return "resistance"

    intermittent = variation >= INTERVAL_CV_THRESHOLD and fraction_high >= 0.10
    sustained_hard = mean_hrr >= 0.75

    if sustained_hard and (duration_min or 0) <= 30:
        if label_modality != "anaerobic":
            notes.append(
                f"Labelled {label_modality} but the heart rate says otherwise: a mean of "
                f"{mean_hrr * 100:.0f} percent of reserve sustained over a short session "
                f"behaves like anaerobic work, which tends to raise glucose rather than lower "
                f"it."
            )
        return "anaerobic"

    if intermittent:
        if label_modality == "aerobic":
            notes.append(
                f"Labelled as continuous aerobic work, but heart rate varied by "
                f"{variation * 100:.0f} percent and {fraction_high * 100:.0f} percent of the "
                f"session sat above 80 percent of reserve. That is an intermittent pattern, and "
                f"the glucose response to it sits between the aerobic and anaerobic cases."
            )
        return "mixed"

    if mean_hrr < 0.30:
        if label_modality not in {"low", "unknown"}:
            notes.append(
                f"Labelled {label_modality} but the mean heart rate reached only "
                f"{mean_hrr * 100:.0f} percent of reserve, which is below the threshold at "
                f"which a meaningful glucose effect would be expected."
            )
        return "low"

    if label_modality in {"unknown", "mixed"}:
        return "aerobic" if not intermittent else "mixed"

    return label_modality


def describe(intensity: Intensity) -> str:
    """One sentence a reader can act on."""
    if intensity.basis == "summary":
        peak = (f", peaking at {intensity.peak_hrr * 100:.0f} percent"
                if intensity.peak_hrr is not None else "")
        return (
            f"{intensity.band.capitalize()} effort on the summary figures, averaging "
            f"{intensity.mean_hrr * 100:.0f} percent of heart rate reserve{peak}. No recorded "
            f"series, so it is treated as {intensity.modality} work on the activity label."
        )
    if not intensity.is_measured:
        if intensity.basis == "absent":
            return "No heart rate and no recognised activity type, so intensity is unknown."
        return (
            f"No heart rate for this session. Treated as {intensity.modality} work on the "
            f"activity label alone."
        )
    return (
        f"{intensity.band.capitalize()} effort, averaging "
        f"{intensity.mean_hrr * 100:.0f} percent of heart rate reserve and peaking at "
        f"{intensity.peak_hrr * 100:.0f} percent, with "
        f"{intensity.fraction_high * 100:.0f} percent of the session above 80 percent. "
        f"Treated as {intensity.modality} work."
    )
