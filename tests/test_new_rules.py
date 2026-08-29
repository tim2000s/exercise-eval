"""Tests for the rules added from the insulin, carbohydrate and automated-delivery literature.

Each asserts a specific published number or a specific conditional, so that a change to either
the constant or the logic that reads it shows up as a failure rather than as different prose.
"""

import pytest
from xeval import guidelines as G
from xeval.report import analyse

import synthetic as syn

MIN = 60_000
HOUR = 3_600_000


def run(builder, **overrides):
    entries, treatments, session = builder()
    settings = dict(syn.SETTINGS)
    settings.update(overrides)
    return analyse({"sessions": [session], "entries": entries, "treatments": treatments,
                    "profile": syn.PROFILE, "settings": settings})


def keys(result, i=0):
    return {f["key"] for f in result["sessions"][i]["findings"]}


def find(result, prefix, i=0):
    return next(f for f in result["sessions"][i]["findings"] if f["key"].startswith(prefix))


# ---- the bolus reduction table ----------------------------------------------------------------

def test_the_bolus_table_reproduces_the_published_cells():
    # Rabasa-Lhoret Table 1, as reproduced by Riddell 2017 Table 5.
    assert G.bolus_reduction_for(0.25, 60)["reduction"] == pytest.approx(0.50)
    assert G.bolus_reduction_for(0.50, 30)["reduction"] == pytest.approx(0.50)
    assert G.bolus_reduction_for(0.50, 60)["reduction"] == pytest.approx(0.75)
    assert G.bolus_reduction_for(0.75, 30)["reduction"] == pytest.approx(0.75)


def test_the_extrapolated_cell_is_marked_as_such():
    # The authors marked this cell with an asterisk; the reproductions dropped it.
    cell = G.bolus_reduction_for(0.25, 30)
    assert cell["reduction"] == pytest.approx(0.25)
    assert cell["measured"] is False
    assert "extrapolated" in cell["note"]
    # Every other populated cell was measured.
    for v, d in [(0.25, 60), (0.50, 30), (0.50, 60), (0.75, 30)]:
        assert G.bolus_reduction_for(v, d)["measured"] is True


def test_the_untested_cell_returns_no_recommendation_rather_than_a_guess():
    cell = G.bolus_reduction_for(0.75, 60)
    assert cell["reduction"] is None
    assert "not studied" in cell["note"]


def test_no_reduction_is_recommended_above_eighty_percent_of_vo2max():
    cell = G.bolus_reduction_for(0.85, 30)
    assert cell["reduction"] == 0.0
    assert "commonly rises" in cell["note"]


def test_no_intensity_estimate_means_no_table_lookup():
    assert G.bolus_reduction_for(None, 60) is None


def test_a_full_bolus_before_a_moderate_hour_is_raised_to_a_risk_finding():
    """The arm of the trial testing exactly this was abandoned after three of four participants
    needed intravenous dextrose, so it should not be reported as a mild suggestion.

    The heart rate is set to about half of reserve, since that is the intensity the abandoned
    arm used. At 52 resting and an estimated maximum of 176, half of reserve is around 114 bpm.
    """
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    s = dict(s, end=s["start"] + 60 * MIN,
             hr=syn.hr_series(s["start"], 60, lambda m: 114))
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert r["sessions"][0]["intensity"]["mean_hrr"] == pytest.approx(0.5, abs=0.06)
    f = find(r, "bolus-full")
    assert f["severity"] == "risk"
    assert "abandoned" in f["guidance"]
    assert "64 to 16 episodes" in f["guidance"]


def test_a_hard_hour_lands_in_the_cell_the_trial_never_tested_and_says_so():
    """At about 80 percent of reserve for an hour there is no published cell, and the tool must
    say that rather than interpolating one."""
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    s = dict(s, end=s["start"] + 60 * MIN)   # the fixture runs at about 79 percent of reserve
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    f = find(r, "bolus-full")
    assert f["severity"] == "adjustment"
    assert "not studied" in f["guidance"]


def test_the_bolus_advice_says_a_reduction_raises_the_starting_point_not_the_slope():
    """The mechanism is the part most often misreported, and it changes what a reader does."""
    r = run(syn.aerobic_fall_with_overnight_low)
    f = find(r, "bolus-full")
    assert "did not slow the fall" in f["guidance"] or "raising the level" in f["action"]


# ---- the expected response --------------------------------------------------------------------

def test_the_expected_rate_is_quoted_with_its_confidence_interval():
    r = run(syn.aerobic_fall_with_overnight_low)
    f = next(f for f in r["sessions"][0]["findings"] if f["key"].startswith("expected-"))
    assert "95 percent CI" in f["guidance"] or "95 percent CI" in f["observed"]


def test_resistance_work_gets_no_expectation_because_the_pooled_result_spans_zero():
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    s = dict(s, typeName="STRENGTH_TRAINING", modality="resistance")
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert "expected-resistance" in keys(r)
    f = find(r, "expected-resistance")
    assert "p=0.30" in f["guidance"]
    assert "spans zero" in f["guidance"]


def test_the_insulin_on_board_band_is_quoted_against_the_published_gradient():
    r = run(syn.aerobic_fall_with_overnight_low)
    f = next(f for f in r["sessions"][0]["findings"] if f["key"].startswith("expected-"))
    # 6 U given 90 minutes before leaves well over 2 U active, the top band.
    assert "-1.44" in f["guidance"] or "-1.44" in f["observed"] or "insulin on board" in f["guidance"]


def test_the_dose_response_bands_are_monotonic_and_cover_every_amount():
    previous = 1.0
    for lo, hi, change, (ci_lo, ci_hi) in G.IOB_DOSE_RESPONSE:
        assert change <= previous, "a larger insulin dose must not produce a smaller fall"
        assert ci_lo <= change <= ci_hi, "the point estimate must lie inside its interval"
        previous = change
    assert G.IOB_DOSE_RESPONSE[-1][1] == float("inf"), "the top band must be unbounded"


# ---- basal lead time --------------------------------------------------------------------------

def test_a_late_basal_reduction_is_reported_with_the_measurement_behind_it():
    entries, treatments, s = syn.well_managed_aerobic()
    # Move the reduction from 90 minutes ahead to 10 minutes ahead.
    treatments = [dict(t, t=s["start"] - 10 * MIN) if t.get("kind") == "temp-basal" else t
                  for t in treatments]
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert "basal-late" in keys(r)
    f = find(r, "basal-late")
    assert "4.9 percent" in f["guidance"], "the McAuley measurement should be quoted"
    assert "1 of 17" in f["guidance"]


def test_a_ninety_minute_lead_time_is_not_flagged():
    r = run(syn.well_managed_aerobic)
    assert "basal-late" not in keys(r)


def test_a_suspension_is_distinguished_from_a_reduction():
    entries, treatments, s = syn.well_managed_aerobic()
    treatments = [dict(t, rateUph=0.0) if t.get("kind") == "temp-basal" else t
                  for t in treatments]
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert "basal-suspended" in keys(r)
    f = find(r, "basal-suspended")
    assert "43 to 16 percent" in f["guidance"]
    assert "quadrupled" in f["guidance"]


# ---- announcing exercise to a closed loop -------------------------------------------------------

def test_a_missing_announcement_is_an_adjustment_when_a_meal_bolus_was_still_active():
    r = run(syn.aerobic_fall_with_overnight_low)
    assert "no-temp-target" in keys(r)
    f = find(r, "no-temp-target")
    assert f["severity"] == "adjustment"
    assert "13.0 to 7.0 percent" in f["guidance"]


def test_a_missing_announcement_is_only_an_observation_when_little_insulin_was_on_board():
    """Two randomised trials found no benefit from announcing a session begun at least three
    hours after the last bolus, and one measured a cost. The tool should not recommend it there."""
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    r = analyse({"sessions": [s], "entries": entries, "treatments": [],  # no bolus at all
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    k = keys(r)
    assert "no-temp-target-low-iob" in k
    assert "no-temp-target" not in k
    f = find(r, "no-temp-target-low-iob")
    assert f["severity"] == "observation"
    assert "p=0.40" in f["guidance"]
    assert "15.7" in f["action"], "the measured cost of announcing unnecessarily should be given"


def test_an_activity_target_set_late_is_flagged_but_the_advice_depends_on_insulin_on_board():
    entries, treatments, s = syn.well_managed_aerobic()
    treatments = [dict(t, t=s["start"] - 5 * MIN) if t.get("kind") == "temp-target" else t
                  for t in treatments]
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    f = find(r, "temp-target")
    assert f["severity"] == "adjustment"
    assert "60 minutes" in f["action"]
    assert "matters most" in f["action"], "a 3 U bolus 90 min before is still active"


def test_the_androidaps_consequences_of_a_temp_target_are_stated():
    r = run(syn.well_managed_aerobic)
    f = find(r, "temp-target")
    assert "super micro boluses" in f["guidance"]
    assert "autosens" in f["guidance"]


def test_the_androidaps_sensitivity_formula_matches_the_documented_values():
    # From determine-basal.js with the default half-basal exercise target of 160 mg/dL.
    assert G.aaps_sensitivity_ratio(120) == pytest.approx(0.75, abs=0.005)
    assert G.aaps_sensitivity_ratio(140) == pytest.approx(0.60, abs=0.005)
    assert G.aaps_sensitivity_ratio(160) == pytest.approx(0.50, abs=0.005)
    assert G.aaps_sensitivity_ratio(180) == pytest.approx(0.43, abs=0.005)
    # A different half-basal target moves the whole curve.
    assert G.aaps_sensitivity_ratio(140, half_basal_target_mgdl=200) > G.aaps_sensitivity_ratio(140)


# ---- carbohydrate scaled by insulin on board ----------------------------------------------------

def test_carbohydrate_advice_scales_with_the_insulin_still_active():
    r = run(syn.aerobic_fall_with_overnight_low)
    f = next((f for f in r["sessions"][0]["findings"] if f["key"].startswith("carb-")), None)
    assert f is not None
    assert "four-fold gradient" in f["guidance"]
    # 78 kg at 0.3 and 1.0 g/kg/h.
    assert "23 g" in f["guidance"] and "78 g" in f["guidance"]


def test_the_measured_requirement_falls_as_time_since_the_dose_rises():
    values = [g for _, g, _ in G.CARB_BY_TIME_SINCE_INSULIN]
    assert values == sorted(values, reverse=True)
    assert values[0] / values[-1] > 4, "the published gradient is about four-fold"


# ---- treating a low ------------------------------------------------------------------------------

def test_hypoglycaemia_treatment_uses_the_measured_rise_not_the_folklore_figure():
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    treatments = treatments + [{"kind": "dose", "t": s["start"] + 40 * MIN, "carbsG": 20,
                               "automatic": False, "eventType": "Carb Correction"}]
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert "hypo-treatment" in keys(r)
    f = find(r, "hypo-treatment")
    assert "1.0 ± 0.29" in f["guidance"]
    assert "cannot be" in f["guidance"] and "traced" in f["guidance"]
    # 0.3 g/kg for a 78 kg person.
    assert "23 g" in f["guidance"]
    assert "No measurement exists" in f["action"]


def test_no_treatment_finding_where_there_was_no_low():
    r = run(syn.well_managed_aerobic)
    assert "hypo-treatment" not in keys(r)


def _session_falling_at(rate_mmol_per_hour, duration_min=45, start_mmol=9.0):
    """Build a session whose glucose falls at a chosen rate, to test the expectation branches."""
    base = syn.day_start()
    start = base + 18 * HOUR
    end = start + duration_min * MIN

    def g(h):
        if h < 18.0:
            return start_mmol
        if h < 18.0 + duration_min / 60:
            return start_mmol + rate_mmol_per_hour * (h - 18.0)
        return start_mmol + rate_mmol_per_hour * (duration_min / 60)

    entries = syn.cgm(base, 34, g)
    session = {"id": "x", "start": start, "end": end, "typeName": "RUNNING",
               "modality": "aerobic",
               "hr": syn.hr_series(start, duration_min, lambda m: 145)}
    return entries, session


def test_a_session_inside_the_published_range_is_reported_as_inside():
    # The pooled figure for aerobic work is -4.43 mmol/L/h, 95 percent CI -6.06 to -2.79.
    entries, s = _session_falling_at(-4.4)
    r = analyse({"sessions": [s], "entries": entries, "treatments": [],
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    k = keys(r)
    assert "expected-within" in k, f"got {k}"
    assert "expected-outside" not in k
    f = find(r, "expected-within")
    assert "-4.4" in f["guidance"] and "-6.1" in f["guidance"]


def test_a_session_falling_faster_than_the_range_is_reported_as_outside():
    entries, s = _session_falling_at(-9.0)
    r = analyse({"sessions": [s], "entries": entries, "treatments": [],
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert "expected-outside" in keys(r)
    f = find(r, "expected-outside")
    assert "fell more steeply" in f["headline"]
    # The limits on any such comparison must travel with it.
    assert "0.12" in f["guidance"], "the within-person repeatability should be quoted"
    assert "not a pattern" in f["action"]


def test_a_session_holding_up_better_than_the_range_is_also_reported_as_outside():
    entries, s = _session_falling_at(-0.5)
    r = analyse({"sessions": [s], "entries": entries, "treatments": [],
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert "expected-outside" in keys(r)
    assert "held up better" in find(r, "expected-outside")["headline"]


def test_the_expectation_is_withheld_where_sensor_coverage_is_poor():
    entries, s = _session_falling_at(-9.0)
    # Keep only two readings inside the session window.
    sparse = [e for e in entries if not (s["start"] < e["t"] < s["end"])]
    sparse += [{"t": s["start"] + 60_000, "mmol": 9.0}, {"t": s["end"] - 60_000, "mmol": 3.0}]
    sparse.sort(key=lambda e: e["t"])
    r = analyse({"sessions": [s], "entries": sparse, "treatments": [],
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    k = keys(r)
    assert "expected-within" not in k and "expected-outside" not in k, \
        "a poorly covered session must not be compared against the published range"
