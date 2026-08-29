"""Tests for the measurement layer. These assert numbers, not prose."""

import math

import pytest
from xeval.evaluate import (HYPO_L1_MMOL, count_events, evaluate_session, steepest_fall,
                            summarise)

import synthetic as syn

MIN = 60_000


def flat(base, hours, value):
    return syn.cgm(base, hours, lambda h: value)


def test_a_window_with_no_readings_reports_no_coverage_rather_than_zero():
    w = summarise([], 0, 60 * MIN, "empty")
    assert w.n == 0
    assert w.coverage == 0.0
    assert w.nadir_mmol is None
    assert not w.is_reliable
    assert "No sensor readings" in w.coverage_note()


def test_coverage_is_reported_honestly_when_a_gap_exists():
    base = syn.day_start()
    # One hour of readings, then a two-hour gap, then one more hour.
    entries = flat(base, 1, 7.0) + flat(base + 3 * 3_600_000, 1, 7.0)
    w = summarise(entries, base, base + 4 * 3_600_000, "gappy")
    assert w.coverage < 0.6
    assert w.largest_gap_min > 100
    assert not w.is_reliable
    assert "indicative rather than measured" in w.coverage_note()


def test_a_single_low_reading_is_not_an_event_but_a_sustained_one_is():
    base = syn.day_start()
    brief = [{"t": base + i * 5 * MIN, "mmol": 3.5 if i == 4 else 6.0} for i in range(20)]
    assert count_events(brief, HYPO_L1_MMOL) == 0

    sustained = [{"t": base + i * 5 * MIN, "mmol": 3.5 if 4 <= i <= 10 else 6.0}
                 for i in range(20)]
    assert count_events(sustained, HYPO_L1_MMOL) == 1


def test_two_separated_excursions_count_twice_and_a_brief_rebound_does_not_split_one():
    base = syn.day_start()
    # Low for 30 min, up for 60 min, low again for 30 min.
    def v(i):
        if 0 <= i < 6 or 18 <= i < 24:
            return 3.4
        return 6.5
    rows = [{"t": base + i * 5 * MIN, "mmol": v(i)} for i in range(30)]
    assert count_events(rows, HYPO_L1_MMOL) == 2

    # One reading above threshold in the middle of a long low does not make two events.
    def w(i):
        if 0 <= i < 12:
            return 4.1 if i == 6 else 3.4
        return 6.5
    rows2 = [{"t": base + i * 5 * MIN, "mmol": w(i)} for i in range(24)]
    assert count_events(rows2, HYPO_L1_MMOL) == 1


def test_steepest_fall_finds_the_steep_part_not_the_mean():
    base = syn.day_start()
    # Falls 3 mmol/L in the first 30 min, then flat for 90. Mean over 2 h is -1.5/h,
    # but the steepest 30-minute rate is -6.0/h.
    def g(h):
        return 10.0 - 3.0 * min(h, 0.5) / 0.5
    entries = syn.cgm(base, 2, g)
    rate = steepest_fall(entries, base, base + 2 * 3_600_000)
    assert rate == pytest.approx(-3.0 / 30, abs=0.02)
    mean_rate = (entries[-1]["mmol"] - entries[0]["mmol"]) / 120
    assert rate < mean_rate, "the steepest window must be steeper than the mean"


def test_steepest_fall_returns_none_when_there_is_nothing_to_measure():
    assert steepest_fall([], 0, 3_600_000) is None
    assert steepest_fall([{"t": 0, "mmol": 5.0}], 0, 3_600_000) is None


def test_the_evening_run_fixture_produces_the_excursions_it_was_built_to_produce():
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    r = evaluate_session(entries, treatments, s["start"], s["end"])

    assert r.during.first_mmol == pytest.approx(9.5, abs=0.2)
    assert r.during.nadir_mmol < 4.5
    assert r.during.change_mmol < -4.0
    assert r.during.coverage > 0.9

    assert r.overnight is not None
    assert r.overnight.nadir_mmol < HYPO_L1_MMOL
    assert r.overnight.hypo_events >= 1


def test_the_well_managed_fixture_does_not_produce_them():
    entries, treatments, s = syn.well_managed_aerobic()
    r = evaluate_session(entries, treatments, s["start"], s["end"])
    assert r.during.nadir_mmol > HYPO_L1_MMOL
    assert abs(r.during.change_mmol) < 2.0
    assert r.overnight.nadir_mmol > HYPO_L1_MMOL
    assert r.carbs_during_g == 20


def test_antecedent_time_below_range_is_measured_over_the_preceding_24_hours():
    entries, treatments, s = syn.antecedent_hypo_day()
    r = evaluate_session(entries, treatments, s["start"], s["end"])
    # Four hours below range out of the 24 before an 18:00 session is about 17 percent.
    assert 0.10 < r.antecedent.time_below_l1 < 0.25
    assert r.antecedent.hypo_events >= 1


def test_a_session_ending_after_midnight_has_no_following_overnight_window():
    base = syn.day_start()
    entries = flat(base, 30, 7.0)
    start = base + 23 * 3_600_000
    r = evaluate_session(entries, [], start, start + 2 * 3_600_000)
    assert r.overnight is None
    assert any("small hours" in n for n in r.notes)
