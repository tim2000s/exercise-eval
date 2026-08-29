"""Glucose units.

Nightscout stores sgv in mg/dL whatever the site displays, Health Connect stores blood glucose
in mmol/L, and the guidelines are written in both. Converting once at each boundary and working
in a single unit internally is the only way to keep that straight; this package works in mmol/L
because that is what most of the guideline text is written in and what a UK reader reads.

The conversion factor is 18.0182 mg/dL per mmol/L, the molar mass of glucose divided by ten.
Published tables were rounded with 18, so a guideline's own printed pair of figures will not
always agree with an exact conversion of either one. Where that happens the guideline's printed
figure is used rather than a recomputed one, since the printed figure is what a clinician reads.
"""

from __future__ import annotations

MGDL_PER_MMOL = 18.0182

# The rounding a guideline used when it printed both units. Kept separate so that reproducing a
# published table is not confused with converting a measurement.
GUIDELINE_ROUNDING = 18.0


def mgdl_to_mmol(mgdl: float | None) -> float | None:
    """Convert a measurement. Returns None unchanged, since a missing reading is not zero."""
    return None if mgdl is None else mgdl / MGDL_PER_MMOL


def mmol_to_mgdl(mmol: float | None) -> float | None:
    return None if mmol is None else mmol * MGDL_PER_MMOL


def rate_mgdl_min_to_mmol_min(rate: float | None) -> float | None:
    """Convert a rate of change. The factor is the same; the units of the result are not."""
    return None if rate is None else rate / MGDL_PER_MMOL


def fmt(mmol: float | None, units: str = "mmol", dp: int | None = None) -> str:
    """Format a glucose value for display in the reader's preferred units.

    mmol/L is shown to one decimal place and mg/dL to none, which is how each is conventionally
    reported and roughly matches the resolution the sensors actually deliver.
    """
    if mmol is None:
        return "no reading"
    if units == "mgdl":
        return f"{mmol * MGDL_PER_MMOL:.{0 if dp is None else dp}f} mg/dL"
    return f"{mmol:.{1 if dp is None else dp}f} mmol/L"


def fmt_rate(mmol_per_min: float | None, units: str = "mmol") -> str:
    """Format a rate of change per hour, which is the scale a person thinks in."""
    if mmol_per_min is None:
        return "not measurable"
    per_hour = mmol_per_min * 60
    if units == "mgdl":
        return f"{per_hour * MGDL_PER_MMOL:+.0f} mg/dL/h"
    return f"{per_hour:+.1f} mmol/L/h"
