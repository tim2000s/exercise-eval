"""Tests for the intensity estimator and the insulin reconstruction."""

import math

import pytest
from xeval import insulin as I
from xeval import intensity as X

import synthetic as syn

MIN = 60_000
HOUR = 3_600_000


def hr(fn, n=180):
    return [{"t": i * 10_000, "bpm": fn(i)} for i in range(n)]


# ---- intensity ------------------------------------------------------------------------------

def test_tanaka_is_used_rather_than_220_minus_age():
    assert X.estimate_hr_max(45) == pytest.approx(176.5)
    assert X.estimate_hr_max(20) == pytest.approx(194.0)
    # It differs from 220 minus age at both ends, which is the whole reason for using it.
    assert abs(X.estimate_hr_max(20) - (220 - 20)) > 5
    assert abs(X.estimate_hr_max(65) - (220 - 65)) > 5
    assert X.estimate_hr_max(None) is None
    assert X.estimate_hr_max(0) is None


def test_a_session_with_no_heart_rate_falls_back_to_the_label_and_says_so():
    i = X.analyse([], label_modality="aerobic")
    assert i.basis == "label-only"
    assert not i.is_measured
    assert i.modality == "aerobic"
    assert i.mean_hrr is None


def test_too_few_readings_is_treated_as_no_heart_rate():
    i = X.analyse([{"t": 0, "bpm": 150}, {"t": 1000, "bpm": 151}], label_modality="aerobic")
    assert not i.is_measured
    assert any("usable heart rate readings" in n for n in i.notes)


def test_implausible_readings_are_discarded():
    samples = hr(lambda i: 500 if i % 2 else 145)
    i = X.analyse(samples, label_modality="aerobic", resting_hr=52, age_years=45,
                  duration_min=30)
    assert i.is_measured
    assert i.peak_hrr < 1.2, "a 500 bpm artefact must not set the peak"


def test_interval_work_labelled_as_a_run_is_reclassified_as_mixed():
    samples = hr(lambda i: 175 if (i // 6) % 2 else 115)
    i = X.analyse(samples, label_modality="aerobic", resting_hr=52, age_years=45,
                  duration_min=40)
    assert i.modality == "mixed"
    assert i.variation > X.INTERVAL_CV_THRESHOLD
    assert any("intermittent pattern" in n for n in i.notes)


def test_steady_work_labelled_as_a_run_stays_aerobic():
    samples = hr(lambda i: 145 + 4 * math.sin(i / 20))
    i = X.analyse(samples, label_modality="aerobic", resting_hr=52, age_years=45,
                  duration_min=45)
    assert i.modality == "aerobic"
    assert i.variation < X.INTERVAL_CV_THRESHOLD


def test_a_short_session_at_a_high_fraction_of_reserve_is_treated_as_anaerobic():
    samples = hr(lambda i: 172, 60)
    i = X.analyse(samples, label_modality="aerobic", resting_hr=52, age_years=45,
                  duration_min=20)
    assert i.modality == "anaerobic"


def test_resistance_keeps_its_label_because_heart_rate_cannot_distinguish_it():
    samples = hr(lambda i: 175 if (i // 6) % 2 else 110)
    i = X.analyse(samples, label_modality="resistance", resting_hr=52, age_years=45,
                  duration_min=40)
    assert i.modality == "resistance"


def test_a_gentle_session_labelled_hard_is_downgraded_and_the_note_says_why():
    samples = hr(lambda i: 78)
    i = X.analyse(samples, label_modality="aerobic", resting_hr=52, age_years=45,
                  duration_min=60)
    assert i.modality == "low"
    assert any("below the threshold" in n for n in i.notes)


def test_missing_age_uses_the_session_peak_and_flags_the_bias_it_introduces():
    samples = hr(lambda i: 120)
    i = X.analyse(samples, label_modality="aerobic", resting_hr=52, duration_min=45)
    assert i.is_measured
    assert any("overstates its intensity" in n for n in i.notes)


# ---- insulin --------------------------------------------------------------------------------

def test_the_iob_curve_is_monotonic_and_bounded():
    prev = 1.1
    for m in range(0, 320, 5):
        f = I.iob_fraction(m, dia_hours=5.0, peak_minutes=75)
        assert 0.0 <= f <= 1.0
        assert f <= prev + 1e-9, f"IOB rose between {m - 5} and {m} minutes"
        prev = f
    assert I.iob_fraction(0) == 1.0
    assert I.iob_fraction(300) == 0.0
    assert I.iob_fraction(600) == 0.0


def test_the_exponential_curve_has_a_meaningful_tail_where_the_bilinear_one_does_not():
    # The tail is the part that matters: a session three hours after a bolus sits in it.
    assert I.iob_fraction(180, dia_hours=5.0, peak_minutes=75) > 0.10
    # A faster insulin clears sooner at the same duration of action.
    fast = I.iob_fraction(180, dia_hours=5.0, peak_minutes=I.PEAK_MINUTES["ultra-rapid"])
    slow = I.iob_fraction(180, dia_hours=5.0, peak_minutes=I.PEAK_MINUTES["rapid"])
    assert fast < slow


def test_a_nonsensical_peak_setting_is_clamped_rather_than_returning_a_negative_fraction():
    for peak in (0, -10, 1000):
        f = I.iob_fraction(60, dia_hours=5.0, peak_minutes=peak)
        assert 0.0 <= f <= 1.0


def test_insulin_on_board_separates_what_the_person_gave_from_what_the_loop_gave():
    doses = [
        {"t": 0, "insulinU": 6.0, "automatic": False},
        {"t": 2 * HOUR, "insulinU": 0.2, "automatic": True},
        {"t": 2 * HOUR, "insulinU": 0.2, "automatic": True},
    ]
    iob = I.iob_at(3 * HOUR, doses)
    assert iob["manual"] > 0.5
    assert 0.1 < iob["automatic"] < 0.5
    assert iob["total"] == pytest.approx(iob["manual"] + iob["automatic"])


def test_doses_outside_the_duration_of_action_contribute_nothing():
    doses = [{"t": 0, "insulinU": 10.0, "automatic": False}]
    assert I.iob_at(6 * HOUR, doses, dia_hours=5.0)["total"] == 0.0
    # A dose in the future is not counted either.
    assert I.iob_at(0, [{"t": HOUR, "insulinU": 5.0}])["total"] == 0.0


def test_carbohydrate_on_board_decays_linearly_and_hits_zero_at_the_absorption_time():
    doses = [{"t": 0, "carbsG": 60}]
    assert I.cob_at(0, doses) == pytest.approx(60)
    assert I.cob_at(90 * MIN, doses) == pytest.approx(30)
    assert I.cob_at(180 * MIN, doses) == 0.0


def test_a_temp_basal_is_read_against_the_profile_rate_with_its_lead_time():
    tbr = [{"kind": "temp-basal", "t": -90 * MIN, "rateUph": 0.3, "durationMin": 180}]
    b = I.basal_action(0, 45 * MIN, tbr, profile_basal_uph=1.0)
    assert b.fraction_of_profile == pytest.approx(0.3)
    assert b.lead_time_min == pytest.approx(90)
    assert b.mechanism == "temp basal"
    assert "70 percent" in b.detail


def test_a_reduction_starting_after_the_session_has_a_negative_lead_time():
    tbr = [{"kind": "temp-basal", "t": 10 * MIN, "rateUph": 0.3, "durationMin": 120}]
    b = I.basal_action(0, 45 * MIN, tbr, profile_basal_uph=1.0)
    assert b.lead_time_min == pytest.approx(-10)
    assert "after the session began" in b.detail


def test_an_expired_temp_basal_does_not_count_as_a_reduction():
    tbr = [{"kind": "temp-basal", "t": -180 * MIN, "rateUph": 0.3, "durationMin": 30}]
    b = I.basal_action(0, 45 * MIN, tbr, profile_basal_uph=1.0)
    assert b.fraction_of_profile == pytest.approx(1.0)
    assert b.mechanism == "none"


def test_a_profile_switch_counts_when_no_temp_basal_covers_the_window():
    sw = [{"kind": "profile-switch", "t": -60 * MIN, "percentage": 70, "durationMin": 180}]
    b = I.basal_action(0, 45 * MIN, sw, profile_basal_uph=1.0)
    assert b.mechanism == "profile switch"
    assert b.fraction_of_profile == pytest.approx(0.7)


def test_no_profile_basal_means_no_comparison_rather_than_a_wrong_one():
    b = I.basal_action(0, 45 * MIN, [], profile_basal_uph=None)
    assert b.fraction_of_profile is None
    assert b.mechanism == "unknown"


def test_a_reduced_bolus_is_recovered_by_comparing_against_the_carbohydrate_ratio():
    t = [{"kind": "dose", "t": -90 * MIN, "insulinU": 3.0, "carbsG": 60, "automatic": False}]
    b = I.bolus_actions(0, t, carb_ratio_g_per_u=10.0)[0]
    assert b.insulin_expected_u == pytest.approx(6.0)
    assert b.reduction_fraction == pytest.approx(0.5)
    assert b.minutes_before == pytest.approx(90)
    assert "indistinguishable from the record" in b.caveat


def test_a_bolus_with_no_carbohydrate_is_not_scored_as_a_reduction():
    t = [{"kind": "dose", "t": -60 * MIN, "insulinU": 2.0, "automatic": False}]
    b = I.bolus_actions(0, t, carb_ratio_g_per_u=10.0)[0]
    assert b.reduction_fraction is None
    assert "may have been a correction" in b.caveat


def test_automatic_microboluses_are_not_treated_as_meal_boluses():
    t = [{"kind": "dose", "t": -60 * MIN, "insulinU": 0.2, "automatic": True}]
    assert I.bolus_actions(0, t, carb_ratio_g_per_u=10.0) == []


def test_an_activity_temp_target_is_recognised_as_announcing_exercise():
    t = [{"kind": "temp-target", "t": -45 * MIN, "reason": "Activity",
          "targetTopMmol": 8.3, "durationMin": 120}]
    tt = I.temp_target_action(0, 45 * MIN, t)
    assert tt["announced_as_exercise"] is True
    assert tt["lead_time_min"] == pytest.approx(45)


def test_a_hypo_temp_target_is_not_an_exercise_announcement():
    t = [{"kind": "temp-target", "t": -10 * MIN, "reason": "Hypo",
          "targetTopMmol": 6.9, "durationMin": 45}]
    tt = I.temp_target_action(0, 45 * MIN, t)
    assert tt["announced_as_exercise"] is False
    assert tt["reason"] == "Hypo"


def test_a_temp_basal_at_the_profile_rate_is_not_a_reduction():
    # A pump running a temp basal identical to the profile rate has changed nothing, and a
    # detection threshold set anywhere above 1.0 would wrongly call this a reduction.
    tbr = [{"kind": "temp-basal", "t": -90 * MIN, "rateUph": 1.0, "durationMin": 180}]
    b = I.basal_action(0, 45 * MIN, tbr, profile_basal_uph=1.0)
    assert b.mechanism == "none"
    assert b.lead_time_min is None
    assert b.fraction_of_profile == pytest.approx(1.0)


def test_a_temp_basal_slightly_below_the_profile_rate_is_not_called_a_reduction():
    # Five percent is within the noise of a pump rounding to its delivery increment.
    tbr = [{"kind": "temp-basal", "t": -90 * MIN, "rateUph": 0.98, "durationMin": 180}]
    b = I.basal_action(0, 45 * MIN, tbr, profile_basal_uph=1.0)
    assert b.mechanism == "none"


def test_a_temp_basal_above_the_profile_rate_is_reported_as_an_increase():
    tbr = [{"kind": "temp-basal", "t": -30 * MIN, "rateUph": 1.6, "durationMin": 120}]
    b = I.basal_action(0, 45 * MIN, tbr, profile_basal_uph=1.0)
    assert b.mechanism == "increased"
    assert b.fraction_of_profile == pytest.approx(1.6)
    assert "above the profile rate" in b.detail
