"""Tests for the conversion layer and for reading a Nightscout profile at a point in time.

Both are small enough to look obviously correct and both are load-bearing: every threshold in
the guidelines is quoted in one unit and compared against a measurement stored in the other,
and every basal comparison depends on picking the right entry out of a schedule.
"""

import datetime as dt

import pytest
from xeval.nightscout_profile import basal_rate_at, carb_ratio_at, isf_at
from xeval.units import (MGDL_PER_MMOL, fmt, fmt_rate, mgdl_to_mmol, mmol_to_mgdl,
                         rate_mgdl_min_to_mmol_min)


def test_the_conversion_factor_is_the_molar_one_not_a_round_number():
    assert MGDL_PER_MMOL == pytest.approx(18.0182)
    # The pairs the guidelines print, which were rounded with 18, still land in the right place.
    assert mgdl_to_mmol(180) == pytest.approx(9.99, abs=0.02)
    assert mgdl_to_mmol(70) == pytest.approx(3.88, abs=0.02)
    assert mgdl_to_mmol(54) == pytest.approx(3.00, abs=0.02)
    assert mmol_to_mgdl(7.0) == pytest.approx(126.1, abs=0.2)
    assert mmol_to_mgdl(15.0) == pytest.approx(270.3, abs=0.3)


def test_conversion_round_trips():
    for v in (2.5, 3.9, 7.0, 10.0, 22.0):
        assert mmol_to_mgdl(mgdl_to_mmol(mmol_to_mgdl(v))) == pytest.approx(mmol_to_mgdl(v))


def test_a_missing_reading_stays_missing_rather_than_becoming_zero():
    assert mgdl_to_mmol(None) is None
    assert mmol_to_mgdl(None) is None
    assert rate_mgdl_min_to_mmol_min(None) is None
    assert fmt(None) == "no reading"
    assert fmt_rate(None) == "not measurable"


def test_display_uses_the_resolution_each_unit_is_conventionally_reported_at():
    assert fmt(5.62, "mmol") == "5.6 mmol/L"
    assert fmt(5.62, "mgdl") == "101 mg/dL"
    # A rate is shown per hour, which is the scale a person thinks in.
    assert fmt_rate(-0.05, "mmol") == "-3.0 mmol/L/h"
    assert fmt_rate(-0.05, "mgdl") == "-54 mg/dL/h"
    assert fmt_rate(0.05, "mmol").startswith("+")


SCHEDULE = [
    {"secondsFromMidnight": 0, "value": 0.70},
    {"secondsFromMidnight": 6 * 3600, "value": 1.10},
    {"secondsFromMidnight": 22 * 3600, "value": 0.60},
]


def at(hour, minute=0):
    return dt.datetime(2026, 8, 3, hour, minute).timestamp() * 1000


def test_a_schedule_returns_the_entry_in_force_not_the_next_one():
    p = {"basal": SCHEDULE}
    assert basal_rate_at(p, at(0, 30)) == 0.70
    assert basal_rate_at(p, at(5, 59)) == 0.70
    assert basal_rate_at(p, at(6, 0)) == 1.10
    assert basal_rate_at(p, at(21, 59)) == 1.10
    assert basal_rate_at(p, at(23, 30)) == 0.60


def test_a_schedule_that_does_not_start_at_midnight_wraps_from_the_previous_day():
    # An 03:00 lookup must find the 22:00 entry still running, not fall through to nothing.
    partial = [{"secondsFromMidnight": 8 * 3600, "value": 2.0},
               {"secondsFromMidnight": 22 * 3600, "value": 1.4}]
    p = {"basal": partial}
    assert basal_rate_at(p, at(3)) == 1.4
    assert basal_rate_at(p, at(9)) == 2.0
    assert basal_rate_at(p, at(23)) == 1.4


def test_a_single_entry_schedule_applies_all_day():
    p = {"basal": [{"secondsFromMidnight": 0, "value": 0.85}]}
    for h in (0, 6, 13, 23):
        assert basal_rate_at(p, at(h)) == 0.85


def test_no_profile_and_an_empty_schedule_both_return_nothing_rather_than_a_default():
    assert basal_rate_at(None, at(12)) is None
    assert basal_rate_at({}, at(12)) is None
    assert basal_rate_at({"basal": []}, at(12)) is None
    assert carb_ratio_at(None, at(12)) is None
    assert isf_at(None, at(12)) is None


def test_the_three_schedules_are_read_independently():
    p = {
        "basal": [{"secondsFromMidnight": 0, "value": 0.9}],
        "carbRatio": [{"secondsFromMidnight": 0, "value": 8.0},
                      {"secondsFromMidnight": 12 * 3600, "value": 11.0}],
        "isf": [{"secondsFromMidnight": 0, "value": 2.4}],
    }
    assert basal_rate_at(p, at(14)) == 0.9
    assert carb_ratio_at(p, at(9)) == 8.0
    assert carb_ratio_at(p, at(14)) == 11.0
    assert isf_at(p, at(14)) == 2.4
