"""End-to-end tests. Each fixture was built with a known answer, so these assert that the
report reaches it, and that it does not reach it on the fixture built not to."""

import pytest
from xeval.report import analyse

import synthetic as syn


def run(builder, **overrides):
    entries, treatments, session = builder()
    settings = dict(syn.SETTINGS)
    settings.update(overrides)
    return analyse({
        "sessions": [session], "entries": entries, "treatments": treatments,
        "profile": syn.PROFILE, "settings": settings,
    })


def keys(result, i=0):
    return {f["key"] for f in result["sessions"][i]["findings"]}


def find(result, key, i=0):
    return next(f for f in result["sessions"][i]["findings"] if f["key"] == key)


# ---- the unadjusted evening run --------------------------------------------------------------

def test_the_unadjusted_run_is_reported_as_hypoglycaemia_during_the_session():
    r = run(syn.aerobic_fall_with_overnight_low)
    assert "hypo-during" in keys(r)
    f = find(r, "hypo-during")
    assert f["severity"] == "hypoglycaemia"
    assert "suspend exercise" in f["guidance"].lower()
    assert f["citations"], "a hypoglycaemia finding must cite its guidance"


def test_the_unadjusted_run_flags_the_overnight_excursion_and_names_the_delayed_window():
    r = run(syn.aerobic_fall_with_overnight_low)
    assert "overnight-hypo" in keys(r)
    f = find(r, "overnight-hypo")
    assert "7 to 11 hours" in f["guidance"]
    # The snack must not be offered as sufficient on its own.
    assert "snack alone does not reliably prevent" in f["action"]


def test_the_unadjusted_run_flags_the_absent_basal_reduction():
    r = run(syn.aerobic_fall_with_overnight_low)
    assert "basal-none" in keys(r)
    assert "basal-reduced" not in keys(r)


def test_the_unadjusted_run_flags_the_full_meal_bolus_before_it():
    r = run(syn.aerobic_fall_with_overnight_low)
    bolus_keys = [k for k in keys(r) if k.startswith("bolus-full")]
    assert bolus_keys, "a full bolus 90 minutes before an aerobic session should be flagged"
    f = next(f for f in r["sessions"][0]["findings"] if f["key"] in bolus_keys)
    assert f["provisional"] is True, "the comparison rests on an assumption and must say so"
    assert "underestimated" in f["guidance"]


def test_the_unadjusted_run_flags_the_missing_temp_target():
    r = run(syn.aerobic_fall_with_overnight_low)
    assert "no-temp-target" in keys(r)


def test_insulin_on_board_at_the_start_is_reported():
    r = run(syn.aerobic_fall_with_overnight_low)
    iob = r["sessions"][0]["insulin"]["iobAtStart"]
    assert iob["total"] > 2.0, "6 U given 90 minutes earlier leaves substantial insulin active"
    assert "iob-high" in keys(r)


# ---- the same session done well ---------------------------------------------------------------

def test_the_well_managed_run_produces_no_hypoglycaemia_finding():
    r = run(syn.well_managed_aerobic)
    k = keys(r)
    assert "hypo-during" not in k
    assert "hypo-recovery" not in k
    assert "overnight-hypo" not in k


def test_the_well_managed_run_recognises_the_basal_reduction_and_its_lead_time():
    r = run(syn.well_managed_aerobic)
    assert "basal-reduced" in keys(r)
    assert "basal-late" not in keys(r), "a 90 minute lead time should not be flagged as late"
    b = r["sessions"][0]["insulin"]["basal"]
    assert b["fraction_of_profile"] == pytest.approx(0.3)
    assert b["lead_time_min"] == pytest.approx(90)


def test_the_well_managed_run_recognises_the_activity_temp_target():
    r = run(syn.well_managed_aerobic)
    assert "temp-target" in keys(r)
    assert "no-temp-target" not in keys(r)
    assert r["sessions"][0]["insulin"]["tempTarget"]["announced_as_exercise"] is True


def test_the_well_managed_run_recognises_the_reduced_bolus():
    r = run(syn.well_managed_aerobic)
    assert any(k.startswith("bolus-reduced") for k in keys(r))
    b = r["sessions"][0]["insulin"]["boluses"][0]
    assert b["reduction_fraction"] == pytest.approx(0.5)


def test_the_two_runs_differ_in_the_way_the_fixtures_were_built_to_differ():
    bad = keys(run(syn.aerobic_fall_with_overnight_low))
    good = keys(run(syn.well_managed_aerobic))
    assert "hypo-during" in bad and "hypo-during" not in good
    assert "basal-none" in bad and "basal-reduced" in good


# ---- other shapes -----------------------------------------------------------------------------

def test_a_short_hard_session_that_raised_glucose_is_not_reported_as_needing_carbohydrate():
    r = run(syn.anaerobic_rise)
    k = keys(r)
    assert "carb-none" not in k
    assert "hypo-during" not in k
    assert r["sessions"][0]["intensity"]["modality"] == "anaerobic"
    assert r["sessions"][0]["glucose"]["during"]["change_mmol"] > 2.0


def test_antecedent_time_below_range_is_surfaced_as_the_strongest_predictor():
    r = run(syn.antecedent_hypo_day)
    assert "antecedent-tbr" in keys(r)
    f = find(r, "antecedent-tbr")
    assert f["severity"] == "risk"
    assert "11.7 to 22.9 percent" in f["guidance"]


def test_a_clean_antecedent_day_gets_the_reassuring_finding_instead():
    r = run(syn.well_managed_aerobic)
    assert "antecedent-ok" in keys(r)
    assert "antecedent-tbr" not in keys(r)


# ---- structure and honesty --------------------------------------------------------------------

def test_findings_are_ordered_with_the_most_serious_first():
    r = run(syn.aerobic_fall_with_overnight_low)
    order = [f["severity"] for f in r["sessions"][0]["findings"]]
    ranks = {"hypoglycaemia": 0, "risk": 1, "adjustment": 2, "observation": 3, "data": 4}
    assert order == sorted(order, key=lambda s: ranks[s])


def test_every_finding_that_gives_guidance_names_where_the_guidance_came_from():
    r = run(syn.aerobic_fall_with_overnight_low)
    for f in r["sessions"][0]["findings"]:
        if f["severity"] in {"hypoglycaemia", "risk"} and f["guidance"]:
            assert f["citations"], f"{f['key']} gives guidance with no citation"


def test_the_bibliography_lists_only_sources_actually_cited_and_records_their_design():
    r = run(syn.aerobic_fall_with_overnight_low)
    bib = r["bibliography"]
    assert bib, "a report with findings should cite something"
    for entry in bib:
        assert entry["design"] in {"trial", "observational", "clamp", "consensus", "guideline"}
        assert "is_evidence" in entry
    # Consensus and measurement must be distinguishable to the reader.
    assert any(e["is_evidence"] for e in bib)
    assert any(not e["is_evidence"] for e in bib)


def test_a_session_without_heart_rate_marks_its_intensity_findings_provisional():
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    s = dict(s, hr=[])
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert r["sessions"][0]["intensity"]["basis"] == "label-only"
    assert "no-hr" in {f["key"] for f in r["sessions"][0]["findings"]}
    assert any(f["provisional"] for f in r["sessions"][0]["findings"])


def test_a_session_with_no_cgm_at_all_reports_that_rather_than_inventing_numbers():
    _, treatments, s = syn.aerobic_fall_with_overnight_low()
    r = analyse({"sessions": [s], "entries": [], "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    k = {f["key"] for f in r["sessions"][0]["findings"]}
    assert "start-unknown" in k
    assert "hypo-during" not in k
    assert r["sessions"][0]["glucose"]["during"]["nadir_mmol"] is None


def test_a_broken_session_does_not_take_the_whole_report_down():
    entries, treatments, good = syn.well_managed_aerobic()
    bad = {"id": "broken", "start": "not a number", "end": None, "modality": "aerobic"}
    r = analyse({"sessions": [bad, good], "entries": entries, "treatments": treatments,
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    assert r["sessions"][0]["error"]
    assert r["sessions"][1]["findings"], "the good session must still be analysed"


def test_no_profile_means_no_basal_comparison_rather_than_a_wrong_one():
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    r = analyse({"sessions": [s], "entries": entries, "treatments": treatments,
                 "profile": None, "settings": syn.SETTINGS})
    k = {f["key"] for f in r["sessions"][0]["findings"]}
    assert "basal-unknown" in k
    assert "basal-none" not in k


# ---- the cross-session summary -----------------------------------------------------------------

def test_a_pattern_is_not_claimed_from_too_few_sessions():
    r = run(syn.well_managed_aerobic)
    group = r["summary"]["groups"][0]
    assert group["sufficient"] is False
    assert "too few to describe a pattern" in group["note"]
    assert "iqr_change_mmol" not in group


def test_a_median_is_reported_once_there_are_enough_sessions():
    entries, treatments, s = syn.aerobic_fall_with_overnight_low()
    # Six copies of the same session, offset by a day each so they do not overlap.
    day = 24 * 3_600_000
    sessions, all_entries = [], []
    for k in range(6):
        sessions.append(dict(s, id=f"s{k}", start=s["start"] + k * day, end=s["end"] + k * day,
                             hr=[{"t": p["t"] + k * day, "bpm": p["bpm"]} for p in s["hr"]]))
        all_entries += [{"t": e["t"] + k * day, "mmol": e["mmol"]} for e in entries]
    all_entries.sort(key=lambda e: e["t"])
    r = analyse({"sessions": sessions, "entries": all_entries, "treatments": [],
                 "profile": syn.PROFILE, "settings": syn.SETTINGS})
    group = next(g for g in r["summary"]["groups"] if g["modality"] == "aerobic")
    assert group["n"] == 6
    assert group["sufficient"] is True
    assert group["median_change_mmol"] < -4.0
    assert len(group["iqr_change_mmol"]) == 2


def test_the_summary_says_plainly_that_it_is_not_a_controlled_comparison():
    r = run(syn.well_managed_aerobic)
    assert "describe what happened rather than what the exercise caused" in r["summary"]["caveat"]


def test_a_poorly_covered_session_is_excluded_from_the_summary_rather_than_averaged_in():
    """A session whose sensor barely recorded anything must not contribute to a median.

    Its own findings still appear, with the coverage warning attached, because the reader
    should see that the session existed. What it must not do is move a group statistic.
    """
    entries, treatments, good = syn.well_managed_aerobic()

    # A second session a week later during which the sensor recorded almost nothing, and what
    # it did record is an implausibly large fall that would drag any median with it.
    day = 7 * 24 * 3_600_000
    sparse_start = good["start"] + day
    sparse_end = good["end"] + day
    sparse_entries = [
        {"t": sparse_start + 1_000, "mmol": 12.0},
        {"t": sparse_end - 1_000, "mmol": 2.5},
    ]
    sparse = dict(good, id="sparse", start=sparse_start, end=sparse_end,
                  hr=[{"t": p["t"] + day, "bpm": p["bpm"]} for p in good["hr"]])

    r = analyse({
        "sessions": [good, sparse],
        "entries": sorted(entries + sparse_entries, key=lambda e: e["t"]),
        "treatments": treatments, "profile": syn.PROFILE, "settings": syn.SETTINGS,
    })

    assert r["summary"]["sessions_analysed"] == 2
    assert r["summary"]["sessions_with_coverage"] == 1, \
        "the sparse session must not count towards coverage"
    aerobic = next(g for g in r["summary"]["groups"] if g["modality"] == "aerobic")
    assert aerobic["n"] == 1
    assert aerobic["median_change_mmol"] > -3.0, \
        "the sparse session's spurious fall must not enter the median"

    # It still gets its own findings, and they carry the coverage warning.
    sparse_result = r["sessions"][1]
    assert sparse_result["glucose"]["during"]["coverage"] < 0.5
    assert any(f["severity"] == "data" for f in sparse_result["findings"])
