"""Recommendations, each traceable to the guideline it came from.

The structure of every finding is the same: what happened, what the published guidance says
about it, and what to change next time. Keeping those three separate matters, because the first
is a measurement, the second is usually consensus rather than trial evidence, and the third is
an inference from both that the reader is entitled to disagree with.

Nothing here is individualised medical advice. The tool reads a record after the event and
compares it against published population-level guidance, without knowing the person's history,
their insulin sensitivity, what else was happening that day, or what their clinical team has
told them. Every finding says which guideline it rests on and how strong that guideline's own
evidence is, so a reader can weigh it rather than take it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import guidelines as G
from .evaluate import HYPO_L1_MMOL, HYPO_L2_MMOL, SessionGlucose
from .units import fmt, fmt_rate

MS_PER_MIN = 60_000.0

#: Ordering for the report. A finding that describes a hypoglycaemic event outranks one that
#: suggests a refinement, because a reader scanning the page should meet them in that order.
SEVERITY_ORDER = {"hypoglycaemia": 0, "risk": 1, "adjustment": 2, "observation": 3, "data": 4}


@dataclass
class Finding:
    """One observation and the advice that follows from it."""

    key: str
    severity: str
    headline: str
    #: What the record shows. Measurement only, no interpretation.
    observed: str
    #: What the published guidance says, with the citation in the text.
    guidance: str
    #: What to change. Empty where the record shows nothing that needs changing.
    action: str = ""
    citations: tuple[str, ...] = ()
    #: True where the finding rests on a label or an assumption rather than a measurement.
    provisional: bool = False

    def sort_key(self) -> tuple:
        return (SEVERITY_ORDER.get(self.severity, 9), self.key)


def _cite(*guides: G.Guideline) -> tuple[str, ...]:
    return tuple(dict.fromkeys(g.describe() for g in guides))


def recommend(
    *,
    glucose: SessionGlucose,
    intensity,
    basal,
    boluses: list,
    temp_target: dict | None,
    session,
    iob_at_start: dict,
    cob_at_start: float,
    risk_group: str = "low",
    body_mass_kg: float | None = None,
    is_child: bool = False,
    units: str = "mmol",
) -> list[Finding]:
    """Produce every finding for one session, ordered with the most serious first."""
    f: list[Finding] = []
    u = units

    f += _starting_glucose(glucose, intensity, risk_group, u)
    f += _hypoglycaemia(glucose, intensity, u)
    f += _antecedent_risk(glucose, u)
    f += _expected_response(glucose, intensity, iob_at_start, u)
    f += _basal(basal, intensity, session)
    f += _bolus(boluses, intensity, session)
    f += _iob(iob_at_start, cob_at_start, glucose, intensity)
    f += _carbohydrate(glucose, intensity, body_mass_kg, is_child, iob_at_start, u)
    f += _hypo_treatment(glucose, body_mass_kg, u)
    f += _overnight(glucose, session, intensity, basal, u)
    f += _temp_target(temp_target, session, iob_at_start, glucose, u)
    f += _sensor_caveats(glucose, intensity, u)

    f.sort(key=lambda x: x.sort_key())
    return f


# ---------------------------------------------------------------------------------------------

def _starting_glucose(g: SessionGlucose, intensity, risk_group: str, u: str) -> list[Finding]:
    start = g.during.first_mmol
    if start is None:
        return [Finding(
            "start-unknown", "data", "No sensor reading at the start of this session",
            observed="The CGM record has no reading in the minutes before the session began.",
            guidance="Every pre-exercise decision in the guidelines is keyed on a starting "
                     "glucose, so none of them can be applied to this session.",
            action="Check whether the sensor was in a warm-up period or out of range.",
        )]

    band = next(b for b in G.PRE_EXERCISE_BANDS if b.contains(start))
    aerobic_like = intensity.modality in {"aerobic", "mixed", "low"}
    advice = band.aerobic if aerobic_like else band.anaerobic

    thresholds = G.RISK_GROUPS[risk_group]
    findings = []

    if band.name in {"below target", "near target"}:
        findings.append(Finding(
            "start-low", "risk",
            f"Started at {fmt(start, u)}, in the {band.name} band",
            observed=f"Sensor glucose was {fmt(start, u)} when the session began, and the "
                     f"session was {intensity.modality} work.",
            guidance=f"The consensus band table puts this in {band.name} "
                     f"({band.printed_mgdl}), where the advice is: {band.action.lower()}. For "
                     f"{'aerobic' if aerobic_like else 'anaerobic'} work specifically: "
                     f"{advice.lower()}.",
            action=(
                f"Taking 10 to 20 g of glucose before starting would have moved the start into "
                f"the target band. On the {risk_group} risk setting the carbohydrate threshold "
                f"is {fmt(thresholds['carb_threshold_mmol'], u)}."
                if aerobic_like else
                "Anaerobic work can be started from this band, and glucose commonly rises "
                "during it, so no carbohydrate was necessarily needed."
            ),
            citations=_cite(G.PRE_EXERCISE_BANDS_SOURCE, G.RISK_GROUPS_SOURCE),
            provisional=not intensity.is_measured,
        ))
    elif band.name == "above target":
        findings.append(Finding(
            "start-high", "risk",
            f"Started at {fmt(start, u)}, above the ketone check threshold",
            observed=f"Sensor glucose was {fmt(start, u)} at the start.",
            guidance=(
                f"Above {fmt(G.KETONE_CHECK_THRESHOLD.value, u)} the guidance is to check blood "
                f"ketones if the hyperglycaemia is unexplained. Below 0.6 mmol/L, mild to "
                f"moderate aerobic exercise may start. Between 0.6 and 1.4 mmol/L the guidelines "
                f"conflict, and the conservative reading is to postpone. At or above 1.5 mmol/L "
                f"exercise is contraindicated. {G.KETONE_CHECK_THRESHOLD.note}"
            ),
            action=(
                "Intense or anaerobic work from this band tends to push glucose higher still. "
                f"Where a correction is given, the usual figure is {G.KETONE_CORRECTION_FRACTION.value:.0%} "
                f"of the normal correction dose. {G.KETONE_CORRECTION_FRACTION.note}"
            ),
            citations=_cite(G.KETONE_CHECK_THRESHOLD, G.KETONE_CORRECTION_FRACTION),
        ))
    else:
        findings.append(Finding(
            "start-ok", "observation",
            f"Started at {fmt(start, u)}, in the {band.name} band",
            observed=f"Sensor glucose was {fmt(start, u)} when the session began.",
            guidance=f"That sits in the {band.name} band ({band.printed_mgdl}), where "
                     f"{advice.lower()}.",
            citations=_cite(G.PRE_EXERCISE_BANDS_SOURCE),
        ))
    return findings


def _hypoglycaemia(g: SessionGlucose, intensity, u: str) -> list[Finding]:
    out = []
    d, r = g.during, g.recovery

    if d.nadir_mmol is not None and d.nadir_mmol < HYPO_L1_MMOL:
        level = "level 2" if d.nadir_mmol < HYPO_L2_MMOL else "level 1"
        out.append(Finding(
            "hypo-during", "hypoglycaemia",
            f"Glucose reached {fmt(d.nadir_mmol, u)} during the session",
            observed=f"The sensor nadir during the session was {fmt(d.nadir_mmol, u)}, which is "
                     f"{level} hypoglycaemia, with {d.time_below_l1 * 100:.0f} percent of the "
                     f"session below {fmt(HYPO_L1_MMOL, u)}.",
            guidance=(
                f"The guidance is to suspend exercise below {fmt(G.SUSPEND_THRESHOLD.value, u)} "
                f"and take oral carbohydrate, restarting near "
                f"{fmt(G.RESTART_THRESHOLD.value, u)} with a level or rising arrow, and not to "
                f"restart below {fmt(G.ABSOLUTE_FLOOR.value, u)} at all."
            ),
            action=(
                "The sensor reads low during exercise and lags behind blood glucose, so the "
                "true nadir was probably lower than this figure and reached sooner. Treating "
                "at the displayed value therefore treats late."
            ),
            citations=_cite(G.SUSPEND_THRESHOLD, G.RESTART_THRESHOLD, G.CGM_LAG_EXERCISE),
        ))

    if r.nadir_mmol is not None and r.nadir_mmol < HYPO_L1_MMOL:
        out.append(Finding(
            "hypo-recovery", "hypoglycaemia",
            f"Glucose fell to {fmt(r.nadir_mmol, u)} in the 90 minutes after",
            observed=f"The nadir in the first 90 minutes after the session was "
                     f"{fmt(r.nadir_mmol, u)}.",
            guidance="EASD/ISPAD sets a floor for the first 90 minutes after exercise of "
                     "4.4 mmol/L (80 mg/dL) at low hypoglycaemia risk, rising to 5.0 and then "
                     "5.6 mmol/L (90 and 100 mg/dL) at moderate and high risk.",
            action="Carbohydrate at the end of the session, rather than only during it, is the "
                   "adjustment this points to.",
            citations=_cite(G.RISK_GROUPS_SOURCE),
        ))

    if g.steepest_fall_mmol_min is not None and g.steepest_fall_mmol_min < -0.1111:
        out.append(Finding(
            "steep-fall", "risk",
            f"Glucose fell at up to {fmt_rate(g.steepest_fall_mmol_min, u)}",
            observed=f"The steepest sustained 30 minute fall during the session was "
                     f"{fmt_rate(g.steepest_fall_mmol_min, u)}, starting from "
                     f"{fmt(d.first_mmol, u)}.",
            guidance="A fall of this rate corresponds to a single or double down arrow. At that "
                     "rate the published carbohydrate response is 20 to 35 g taken immediately, "
                     "repeated every 15 to 20 minutes, with up to 20 minutes before the arrow "
                     "responds.",
            action="A fall this steep is easier to prevent than to catch. It points at the "
                   "insulin decisions before the session rather than at carbohydrate during it.",
            citations=_cite(G.CARB_BY_TREND_SOURCE, G.TREND_BANDS_SOURCE),
        ))
    return out


def _antecedent_risk(g: SessionGlucose, u: str) -> list[Finding]:
    a = g.antecedent
    if a.n == 0:
        return []
    tbr_pct = a.time_below_l1 * 100
    if tbr_pct < G.ANTECEDENT_TBR_THRESHOLD.value:
        return [Finding(
            "antecedent-ok", "observation",
            f"Little hypoglycaemia in the 24 hours before ({tbr_pct:.1f} percent)",
            observed=f"Time below {fmt(HYPO_L1_MMOL, u)} in the preceding 24 hours was "
                     f"{tbr_pct:.1f} percent.",
            guidance="Below the 4 percent mark, post-exercise nocturnal hypoglycaemia occurred "
                     "on 11.7 percent of nights in a cohort of 496 adults, against 22.9 percent "
                     "above it.",
            citations=_cite(G.ANTECEDENT_TBR_THRESHOLD),
        )]
    return [Finding(
        "antecedent-tbr", "risk",
        f"{tbr_pct:.0f} percent of the previous 24 hours was spent below {fmt(HYPO_L1_MMOL, u)}",
        observed=f"Time below range in the 24 hours before this session was {tbr_pct:.0f} "
                 f"percent, with a nadir of {fmt(a.nadir_mmol, u)} and {a.hypo_events} "
                 f"excursion{'s' if a.hypo_events != 1 else ''} lasting 15 minutes or more.",
        guidance=(
            "This is the strongest single predictor available from CGM alone. At or above 4 "
            "percent, level 1 nocturnal hypoglycaemia after exercise rose from 11.7 to 22.9 "
            "percent of nights and level 2 from 3.3 to 10.2 percent, both p<0.001. The "
            "mechanism is documented at the level of hormone concentrations: antecedent "
            "hypoglycaemia blunts the adrenaline, glucagon and cortisol responses to subsequent "
            "exercise, and the blunting is detectable from a previous nadir of only "
            "3.9 mmol/L (70 mg/dL). Severe hypoglycaemia within 24 hours is a contraindication "
            "to exercise."
        ),
        action="On a day following this much time below range, larger insulin reductions and "
               "more carbohydrate are warranted than the same session would need otherwise.",
        citations=_cite(G.ANTECEDENT_TBR_THRESHOLD, G.SEVERE_HYPO_CONTRAINDICATION),
    )]


def _expected_response(g: SessionGlucose, intensity, iob: dict, u: str) -> list[Finding]:
    """Compare the measured change against the published expectation for this kind of session.

    The expectation is quoted as an interval rather than a point, because the pooled confidence
    intervals are wide and the same person repeating the same session is only weakly predictive
    of themselves. Where the observed change sits outside the interval, that is worth knowing;
    where it sits inside, so is that, and neither is a judgement about the session.
    """
    d = g.during
    if d.change_mmol is None or not d.is_reliable:
        return []
    duration_h = (d.end_ms - d.start_ms) / MS_PER_MIN / 60
    if duration_h < 0.25:
        return []
    observed_rate = d.change_mmol / duration_h

    entry = G.EXPECTED_RATE_BY_MODALITY.get(intensity.modality)
    if entry is None:
        return []
    point, (lo, hi), significant = entry

    if not significant:
        return [Finding(
            "expected-resistance", "observation",
            f"Glucose changed by {d.change_mmol:+.1f} mmol/L, which resistance work makes hard "
            f"to call unusual",
            observed=f"Over {duration_h * 60:.0f} minutes glucose moved "
                     f"{d.change_mmol:+.1f} mmol/L, a rate of {observed_rate:+.1f} mmol/L per hour.",
            guidance="In the pooled analysis, resistance exercise did not differ significantly "
                     "from rest (p=0.30) and its confidence interval, -7.55 to +2.34 mmol/L per "
                     "hour, spans zero. There is no published expectation to compare this "
                     "against.",
            citations=_cite(G.EXPECTED_RATE_SOURCE),
            provisional=not intensity.is_measured,
        )]

    within = lo <= observed_rate <= hi
    iob_note = ""
    for lo_u, hi_u, adj, (ci_lo, ci_hi) in G.IOB_DOSE_RESPONSE:
        if lo_u <= iob["total"] < hi_u:
            iob_note = (
                f" With {iob['total']:.1f} U of insulin on board at the start, the measured "
                f"average change across 2,613 real-world sessions in that band was "
                f"{adj:+.2f} mmol/L (95 percent CI {ci_lo:+.2f} to {ci_hi:+.2f})."
            )
            break

    if within:
        return [Finding(
            "expected-within", "observation",
            f"Glucose fell at {observed_rate:+.1f} mmol/L per hour, within the published range",
            observed=f"Over {duration_h * 60:.0f} minutes glucose moved "
                     f"{d.change_mmol:+.1f} mmol/L, a rate of {observed_rate:+.1f} mmol/L per hour.",
            guidance=f"The pooled figure for {intensity.modality} work is {point:.1f} mmol/L per "
                     f"hour (95 percent CI {lo:.1f} to {hi:.1f}) under laboratory conditions with "
                     f"insulin on board. Real-world sessions of 10 to 30 minutes average about "
                     f"-2.2 mmol/L over the bout, roughly half the laboratory figure.{iob_note}",
            citations=_cite(G.EXPECTED_RATE_SOURCE, G.REAL_WORLD_CHANGE,
                            G.IOB_DOSE_RESPONSE_SOURCE),
            provisional=not intensity.is_measured,
        )]

    steeper = observed_rate < lo
    return [Finding(
        "expected-outside", "observation",
        f"Glucose {'fell more steeply' if steeper else 'held up better'} than the published "
        f"range for this kind of session",
        observed=f"Over {duration_h * 60:.0f} minutes glucose moved {d.change_mmol:+.1f} mmol/L, "
                 f"a rate of {observed_rate:+.1f} mmol/L per hour, against a pooled expectation "
                 f"of {point:.1f} (95 percent CI {lo:.1f} to {hi:.1f}).",
        guidance=(
            f"{iob_note.strip() or 'Insulin on board at the start was negligible.'} "
            "The predictors that actually separate sessions, in order, are the rate of change "
            "before the session, the starting glucose, glucose variability, the duration and "
            "insulin on board. Activity type and intensity did not reach significance at all in "
            "the analysis that ranked them. The same session repeated is only weakly predictive "
            "of itself: the intraclass correlation across repeats is 0.12, and ten men on an "
            "identical protocol fell at between 4.4 and 10.0 mmol/L per hour."
        ),
        action="One session outside the range is not a pattern. The comparison across sessions "
               "at the top of this report is the place to look for one.",
        citations=_cite(G.EXPECTED_RATE_SOURCE, G.PREDICTOR_RANKING,
                        G.WITHIN_PERSON_VARIABILITY),
        provisional=not intensity.is_measured,
    )]


def _hypo_treatment(g: SessionGlucose, body_mass_kg, u: str) -> list[Finding]:
    """Whether carbohydrate taken to treat a low was enough, given what it can be expected to do."""
    d = g.during
    if d.nadir_mmol is None or d.nadir_mmol >= HYPO_L1_MMOL:
        return []
    taken = g.carbs_during_g + g.carbs_recovery_g
    if taken <= 0:
        return []

    weight_based = (f"{G.WEIGHT_BASED_HYPO_TREATMENT.value * body_mass_kg:.0f} g"
                    if body_mass_kg else "0.3 g per kg of body mass")
    return [Finding(
        "hypo-treatment", "observation",
        f"{taken:.0f} g of carbohydrate was taken around the low",
        observed=f"The nadir was {fmt(d.nadir_mmol, u)} and {taken:.0f} g was logged during the "
                 f"session and the 90 minutes after it.",
        guidance=(
            f"Twenty grams given at the moment exercise stopped raised glucose by "
            f"1.0 ± 0.29 mmol/L at 15 minutes, with the first 1 mmol/L taking 16.5 ± 5.4 minutes "
            f"and the peak coming at 40 minutes. At rest, 15 g raises glucose by about 1.2 to "
            f"1.3 mmol/L at 10 to 15 minutes. The commonly quoted 2.1 mmol/L from 15 g cannot be "
            f"traced to a primary measurement. Weight-based dosing beat a fixed 15 g by "
            f"0.26 mmol/L at 10 minutes, which for you would be about {weight_based}."
        ),
        action="No measurement exists of how much glucose rises per gram while exercise "
               "continues. Every published figure was taken at rest or after stopping, so the "
               "amounts above are extrapolations into the situation they are most used in.",
        citations=_cite(G.HYPO_TREATMENT_RISE, G.WEIGHT_BASED_HYPO_TREATMENT,
                        G.HYPO_TREATMENT_UNDER_EXERCISE),
    )]


def _basal(basal, intensity, session) -> list[Finding]:
    if basal.fraction_of_profile is None:
        return [Finding(
            "basal-unknown", "data", "No basal rate available to compare against",
            observed="The Nightscout profile has no basal schedule, so delivered basal cannot "
                     "be compared to the profile rate.",
            guidance="", action="",
        )]

    reduction = 1 - basal.fraction_of_profile
    if intensity.modality in {"low"}:
        return []

    if reduction < 0.05:
        return [Finding(
            "basal-none", "adjustment", "Basal insulin was not reduced for this session",
            observed=basal.detail,
            guidance=(
                "For aerobic, resistance and mixed exercise the consensus is a basal reduction "
                "beginning before the session, with roughly 20 percent overnight afterwards. "
                "The whole evidence base for the overnight figure is two trials totalling 26 "
                "people, so it is a starting point rather than a target."
            ),
            action="A temp basal starting before the session is the adjustment with the most "
                   "evidence behind it for continuous aerobic work.",
            citations=_cite(G.OVERNIGHT_BASAL_REDUCTION),
            provisional=not intensity.is_measured,
        )]

    findings = [Finding(
        "basal-reduced", "observation",
        f"Basal was cut to {basal.fraction_of_profile * 100:.0f} percent of the profile rate",
        observed=basal.detail,
        guidance="A reduction of this kind is what the guidelines ask for.",
        citations=_cite(G.OVERNIGHT_BASAL_REDUCTION),
    )]

    if basal.lead_time_min is not None and basal.lead_time_min < 60:
        when = (f"{basal.lead_time_min:.0f} minutes before the session"
                if basal.lead_time_min >= 0
                else f"{-basal.lead_time_min:.0f} minutes after the session had started")
        findings.append(Finding(
            "basal-late", "adjustment", "The basal reduction started too late to have acted",
            observed=f"The reduction began {when}.",
            guidance=(
                "Lead time is not a refinement here, it is the whole mechanism. Halving a basal "
                "rate one hour before exercise removed 4.9 percent of circulating free insulin "
                "by the time exercise began, and the fall did not reach significance until 75 "
                "minutes. An 80 percent reduction 40, 20 or 0 minutes before showed no "
                "difference on its primary outcome. A 50 or 80 percent reduction 90 minutes "
                "before left 1 of 17 people hypoglycaemic, against 7 of 17 when the pump was "
                "suspended at the start."
            ),
            action=(
                "The same reduction 90 minutes earlier is the single change with the most "
                "evidence behind it. It cannot be made up for afterwards: an increase in basal "
                "reaches 80 percent of its new steady state in about 170 minutes, while a "
                "reduction does not get there within 300."
            ),
            citations=_cite(G.BASAL_LEAD_TIME, G.BASAL_LEAD_TIME_FLOOR, G.BASAL_ASYMMETRY),
        ))
    if basal.mechanism == "temp basal" and basal.fraction_of_profile is not None \
            and basal.fraction_of_profile <= 0.05:
        findings.append(Finding(
            "basal-suspended", "observation", "Basal delivery was suspended rather than reduced",
            observed=basal.detail,
            guidance=(
                "Suspending at exercise onset halved hypoglycaemia during exercise, from 43 to "
                "16 percent, and quadrupled hyperglycaemia afterwards, from 6 to 27 percent. "
                "Exercise itself raises plasma insulin by about 5 to 8 microunits per mL over "
                "the first 15 to 30 minutes as depot absorption accelerates, measured even in "
                "arms where the pump was stopped, so a suspension delivers a smaller and later "
                "fall in insulin than its nominal 100 percent implies."
            ),
            action="The consensus prefers a reduction started earlier to a suspension started "
                   "late, and caps a suspension at under two hours.",
            citations=_cite(G.PUMP_SUSPENSION, G.EXERCISE_RAISES_INSULIN),
        ))
    return findings


def _bolus(boluses: list, intensity, session) -> list[Finding]:
    """Assess each meal bolus shortly before the session against the published reduction table.

    The table is keyed on fraction of VO2max and duration. Fraction of heart rate reserve stands
    in for it, which is the Karvonen assumption and close enough for a table quantised at 25
    percentage points, but it means a session with no heart rate gets no comparison at all
    rather than a guessed one.
    """
    if not boluses:
        return []

    duration_min = (session["end"] - session["start"]) / MS_PER_MIN
    target = G.bolus_reduction_for(intensity.mean_hrr, duration_min) if intensity.is_measured else None

    out = []
    for b in boluses:
        if b.reduction_fraction is None:
            continue
        actual = b.reduction_fraction
        pct = actual * 100

        if target is None or target["reduction"] is None:
            recommended_text = (
                "The published table is keyed on exercise intensity, which cannot be estimated "
                "for this session without heart rate."
                if target is None else target["note"]
            )
            suffix = ""
        else:
            rec = target["reduction"]
            recommended_text = (
                f"For work at about {target['vo2'] * 100:.0f} percent of VO2max lasting "
                f"{target['duration']} minutes, begun within about 90 minutes of the meal, the "
                f"published reduction is {rec * 100:.0f} percent."
            )
            if not target["measured"]:
                recommended_text += " " + target["note"]
            gap = actual - rec
            if abs(gap) < 0.15:
                suffix = " That is close to the published figure."
            elif gap < 0:
                suffix = (f" The dose given was {abs(gap) * 100:.0f} percentage points less "
                          f"reduced than that.")
            else:
                suffix = (f" The dose given was {gap * 100:.0f} percentage points more reduced "
                          f"than that.")
            recommended_text += suffix

        if pct >= 15:
            out.append(Finding(
                f"bolus-reduced-{int(b.at_ms)}", "observation",
                f"The meal {b.minutes_before:.0f} minutes before was bolused "
                f"{pct:.0f} percent under the profile ratio",
                observed=f"{b.carbs_g:.0f} g of carbohydrate was covered with "
                         f"{b.insulin_given_u:.1f} U where the profile ratio implies "
                         f"{b.insulin_expected_u:.1f} U.",
                guidance=recommended_text + " " + b.caveat,
                action=(
                    "A reduced bolus does not slow the fall during exercise. In every arm of the "
                    "trial the table comes from, the fall was the same size on a reduced dose as "
                    "on a full one; what changed was that glucose was higher when exercise "
                    "began, so the same fall landed somewhere safer. The cost is a larger "
                    "postprandial rise beforehand."
                ),
                citations=_cite(G.BOLUS_REDUCTION_SOURCE, G.BOLUS_REDUCTION_MECHANISM),
                provisional=True,
            ))
        elif pct <= 5 and b.minutes_before <= 180:
            severity = "risk" if (target and (target["reduction"] or 0) >= 0.5) else "adjustment"
            out.append(Finding(
                f"bolus-full-{int(b.at_ms)}", severity,
                f"A full meal bolus was given {b.minutes_before:.0f} minutes before the session",
                observed=f"{b.carbs_g:.0f} g of carbohydrate was covered with "
                         f"{b.insulin_given_u:.1f} U, which is what the profile ratio implies.",
                guidance=(
                    recommended_text + " " +
                    "The arm of that trial testing an hour at half of VO2max on a full "
                    "breakfast bolus was abandoned: three of four participants needed "
                    "intravenous dextrose and the fourth finished at 3.5 mmol/L. Across the "
                    "trial, reducing the dose cut hypoglycaemia from 64 to 16 episodes per 100 "
                    "exercising sessions. " + b.caveat
                ),
                action=(
                    "Reducing this bolus acts on the cause rather than the effect, and it works "
                    "by raising the level exercise starts from rather than by making the fall "
                    "gentler."
                ),
                citations=_cite(G.BOLUS_REDUCTION_SOURCE, G.BOLUS_FULL_DOSE_HAZARD,
                                G.BOLUS_REDUCTION_MECHANISM),
                provisional=True,
            ))
    return out


def _iob(iob: dict, cob: float, g: SessionGlucose, intensity) -> list[Finding]:
    out = []
    if iob["total"] >= 1.0:
        detail = f"{iob['total']:.1f} U of rapid-acting insulin was still active at the start"
        if iob["automatic"] > 0.05:
            detail += (f", of which {iob['manual']:.1f} U was given by hand and "
                       f"{iob['automatic']:.1f} U by the loop")
        out.append(Finding(
            "iob-high", "risk", f"{iob['total']:.1f} U of insulin on board at the start",
            observed=detail + ".",
            guidance=(
                "Circulating insulin is what turns exercise into a fall in glucose. The same "
                "session started with little insulin on board behaves quite differently from "
                "one started in the peak of a meal bolus."
            ),
            action="Where a session is planned, moving it later in the action of the previous "
                   "bolus, or reducing that bolus, both lower the insulin on board at the start. "
                   "Only the second is available once the meal has been eaten.",
            citations=_cite(G.INSULIN_ON_BOARD_EFFECT),
        ))
    if cob >= 20:
        out.append(Finding(
            "cob", "observation", f"About {cob:.0f} g of carbohydrate still absorbing at the start",
            observed=f"On a linear absorption model over three hours, roughly {cob:.0f} g "
                     f"remained to absorb when the session began.",
            guidance="A linear model is used deliberately: the physiology is not linear, but a "
                     "more elaborate curve fitted to no glycaemic index would give a false "
                     "impression of precision. The figure says the session started on a full "
                     "stomach, not how much glucose to expect from it.",
        ))
    return out


def _carbohydrate(g: SessionGlucose, intensity, body_mass_kg, is_child, iob: dict,
                  u: str) -> list[Finding]:
    d = g.during
    duration_min = (d.end_ms - d.start_ms) / MS_PER_MIN
    taken = g.carbs_during_g

    if intensity.modality == "low" or duration_min < 20:
        return []

    # The two guideline families give carbohydrate in different currencies and diverge at the
    # extremes, so both are computed and both are shown.
    # Carbohydrate requirement scales with the insulin still active far more strongly than with
    # anything about the exercise itself, so that gradient is stated before the guideline bands.
    iob_note = ""
    if body_mass_kg and iob["total"] > 0.2:
        need_low = 0.3 * body_mass_kg
        need_high = 1.0 * body_mass_kg
        iob_note = (
            f" Requirement scales with the insulin still active rather than with the exercise: "
            f"measured at a fixed workload it ran from 0.63 g/kg an hour after a dose to "
            f"0.14 g/kg at five and a half hours, a four-fold gradient. For you that is roughly "
            f"{need_low:.0f} g per hour more than two hours after a bolus and up to "
            f"{need_high:.0f} g per hour with a bolus still peaking. There was "
            f"{iob['total']:.1f} U on board when this session began."
        )

    per_kg_note = ""
    if body_mass_kg:
        capped = min(body_mass_kg, G.ISPAD_WEIGHT_CAP_KG.value)
        # The 7.0 to 10.0 band with a steady trend and insulin on board, per 20 minutes.
        per_20 = G.CARB_PER_KG_BY_BAND_AND_TREND["7.0-10.0"]["steady"][0] * capped
        per_hour = per_20 * 3
        per_kg_note = (
            f" Scaled by body mass, the paediatric table gives {per_20:.0f} g per 20 minutes, "
            f"about {per_hour:.0f} g per hour, from the target band with a steady trend and "
            f"insulin still on board."
        )
        if body_mass_kg > G.ISPAD_WEIGHT_CAP_KG.value:
            per_kg_note += (
                f" That table caps body mass at {G.ISPAD_WEIGHT_CAP_KG.value:.0f} kg because "
                f"peak exogenous carbohydrate oxidation is 1.0 to 1.2 g per minute, so for a "
                f"heavier adult it reads low against the adult figures."
            )

    fell = d.change_mmol is not None and d.change_mmol < -2.0
    if fell and taken < 10:
        return [Finding(
            "carb-none", "adjustment",
            f"Glucose fell {abs(d.change_mmol):.1f} mmol/L with no carbohydrate recorded",
            observed=f"Glucose went from {fmt(d.first_mmol, u)} to {fmt(d.last_mmol, u)} over "
                     f"{duration_min:.0f} minutes and no carbohydrate was logged during the "
                     f"session.",
            guidance=(
                "At a threshold of 7.0 mmol/L (126 mg/dL) during exercise the published "
                "amounts are 10 to 15 g with a level arrow, 15 to 25 g taken immediately with a "
                "slight downward arrow, and 20 to 35 g with a steeper one, repeated every 15 to "
                "20 minutes." + per_kg_note + iob_note
            ),
            action="Carbohydrate taken during the session, or a larger insulin reduction before "
                   "it, would both have flattened this. Which is preferable depends on whether "
                   "the session was planned.",
            citations=_cite(G.CARB_BY_TREND_SOURCE, G.ISPAD_WEIGHT_CAP_KG,
                            G.CARB_BY_TIME_SINCE_INSULIN_SOURCE),
        )]
    if taken > 0:
        return [Finding(
            "carb-taken", "observation",
            f"{taken:.0f} g of carbohydrate was taken during the session",
            observed=f"{taken:.0f} g was logged during {duration_min:.0f} minutes of "
                     f"{intensity.modality} work, over which glucose changed by "
                     f"{d.change_mmol:+.1f} mmol/L.",
            guidance="The published amounts during exercise are 10 to 15 g with a level arrow, "
                     "rising to 20 to 35 g with a falling one, repeated every 15 to 20 minutes."
                     + per_kg_note + iob_note,
            citations=_cite(G.CARB_BY_TREND_SOURCE, G.CARB_BY_TIME_SINCE_INSULIN_SOURCE),
        )]
    return []


def _overnight(g: SessionGlucose, session, intensity, basal, u: str) -> list[Finding]:
    if g.overnight is None or g.overnight.n == 0:
        return []
    import datetime as _dt
    end_hour = _dt.datetime.fromtimestamp(session["end"] / 1000).hour
    late_session = end_hour >= 15

    o = g.overnight
    out = []

    if o.nadir_mmol is not None and o.nadir_mmol < HYPO_L1_MMOL:
        out.append(Finding(
            "overnight-hypo", "hypoglycaemia",
            f"Glucose reached {fmt(o.nadir_mmol, u)} between midnight and 06:00",
            observed=f"The overnight nadir was {fmt(o.nadir_mmol, u)}, with "
                     f"{o.time_below_l1 * 100:.0f} percent of the window below "
                     f"{fmt(HYPO_L1_MMOL, u)} and {o.hypo_events} excursion"
                     f"{'s' if o.hypo_events != 1 else ''} lasting 15 minutes or more.",
            guidance=(
                "Glucose requirement rises biphasically after late-afternoon exercise, with a "
                "second separate peak 7 to 11 hours after the session. For a session ending at "
                "17:00 that falls between about midnight and 04:00, which is where this "
                "excursion sits. The published response is a basal reduction of about 20 "
                "percent for 6 hours from bedtime."
            ),
            action=(
                "A snack alone does not reliably prevent this. In 21 adults neither a "
                "conventional snack nor cornstarch raised the overnight nadir, and in 10 men a "
                "low glycaemic index bedtime snack protected for about 8 hours but left "
                "nocturnal hypoglycaemia unchanged at 5 of 10 in both arms. The insulin "
                "reduction is the part with the evidence."
            ),
            citations=_cite(G.LATE_HYPO_WINDOW_HOURS, G.OVERNIGHT_BASAL_REDUCTION,
                            G.BEDTIME_SNACK_CAVEAT, G.BEDTIME_SNACK_CARB_PER_KG),
        ))
    elif late_session:
        out.append(Finding(
            "overnight-ok", "observation",
            f"Overnight nadir was {fmt(o.nadir_mmol, u)}",
            observed=f"Between midnight and 06:00 the nadir was {fmt(o.nadir_mmol, u)} with "
                     f"{o.time_below_l1 * 100:.0f} percent below range.",
            guidance="This is the window where the delayed peak in glucose requirement after "
                     "afternoon exercise falls, 7 to 11 hours after the session.",
            citations=_cite(G.LATE_HYPO_WINDOW_HOURS),
        ))

    if late_session and o.nadir_mmol is not None and o.nadir_mmol < 5.0:
        out.append(Finding(
            "bedtime", "adjustment", "Consider the bedtime position after an afternoon session",
            observed=f"The session ended at {end_hour:02d}:00 and the overnight nadir was "
                     f"{fmt(o.nadir_mmol, u)}.",
            guidance=(
                "Above 10 mmol/L (180 mg/dL) at bedtime no snack was needed in the trial these "
                "thresholds come from, between 7 and 10 mmol/L any snack sufficed, and below "
                "7 mmol/L (126 mg/dL) a standard or protein-containing snack was needed. That "
                "trial was in 15 adults on bedtime NPH and was not an exercise study. On "
                "exercise nights specifically, hypoglycaemia occurred fairly frequently even "
                "above 7.2 mmol/L (130 mg/dL), so a threshold that works on a sedentary night "
                "does not transfer."
            ),
            action="The overnight basal reduction has better evidence behind it than the snack.",
            citations=_cite(G.BEDTIME_SNACK_THRESHOLD, G.BEDTIME_GLUCOSE_CAVEAT,
                            G.OVERNIGHT_BASAL_REDUCTION),
        ))
    return out


def _temp_target(tt: dict | None, session, iob: dict, g: SessionGlucose,
                 u: str) -> list[Finding]:
    """Whether the session was announced, and whether announcing it would have mattered.

    The trial evidence splits cleanly on one variable. Announcing a session helps when a meal
    bolus is still active and does not measurably help when it is not: the two trials with a
    large effect placed exercise 90 minutes after a meal, and the two null trials placed it at
    least three hours after the last bolus, where time below range was already zero. Raising the
    target changes only future automated delivery, which is a small lever against insulin
    already in the tissue. So the tool asks how much insulin was on board before it says whether
    announcing would have helped.
    """
    prandial = iob["manual"] >= 0.75

    if tt is None:
        if prandial:
            return [Finding(
                "no-temp-target", "adjustment",
                "The session was not announced, and a meal bolus was still active",
                observed=f"No temporary target covered this session, and {iob['manual']:.1f} U "
                         f"of manually given insulin was still active when it began.",
                guidance=(
                    "This is the situation where announcing measurably helps. With exercise 90 "
                    "minutes after a meal, time below range fell from 13.0 to 7.0 percent on "
                    "announcement alone, and to 2.0 percent when a 33 percent bolus reduction "
                    "was added. On a closed loop, a raised target is what actually changes the "
                    "algorithm's behaviour; a care portal exercise event records the intention "
                    "and changes nothing."
                ),
                action=(
                    "Set the target before the session rather than at its start. Nothing shorter "
                    "than 60 minutes of lead time has shown a benefit in any randomised "
                    "comparison, and the consensus asks for 60 to 120 minutes."
                ),
                citations=_cite(G.AID_ANNOUNCEMENT_EVIDENCE, G.AID_LEAD_TIME),
            )]
        return [Finding(
            "no-temp-target-low-iob", "observation",
            "The session was not announced, but little insulin was on board",
            observed=f"No temporary target covered this session. Insulin on board at the start "
                     f"was {iob['total']:.1f} U.",
            guidance=(
                "Announcing a session begun at least three hours after the last bolus has twice "
                "failed to show a benefit: in 38 adults time below range was 4.5 percent with an "
                "hour of notice against 6.1 percent with none (p=0.40), and in 26 adults across "
                "16 randomised bouts each the median time below range was zero whether the "
                "target was set 60 minutes ahead, 20 minutes ahead, at the start, or not at all."
            ),
            action=(
                "Announcing a session that was not going to cause a problem has a cost. Before "
                "morning moderate exercise, setting the target an hour ahead gave 15.7 "
                "percentage points less time in range than not setting it at all."
            ),
            citations=_cite(G.AID_ANNOUNCEMENT_EVIDENCE, G.AID_ANNOUNCEMENT_COST),
        )]

    if tt["announced_as_exercise"]:
        lead = tt["lead_time_min"]
        when = (f"{lead:.0f} minutes before the session"
                if lead >= 0 else f"{-lead:.0f} minutes after it started")
        target_text = (f"{fmt(tt['target_mmol'], u)}" if tt.get("target_mmol") else "a raised target")
        f = Finding(
            "temp-target", "observation", "The session was announced as activity",
            observed=f"An activity target of {target_text} was set {when}, lasting "
                     f"{tt['duration_min']:.0f} minutes.",
            guidance=(
                "This is the strongest available signal that the session was announced to the "
                "system, because it is what changed the algorithm's behaviour rather than only "
                "recording an intention. On AndroidAPS a target above 5.6 mmol/L (100 mg/dL) "
                "also stops super micro boluses, overrides the autosens ratio for its duration, "
                "and raises the threshold at which the loop zero-temps by about 1.1 mmol/L."
            ),
            citations=_cite(G.AAPS_TEMP_TARGET_EFFECTS),
        )
        if lead < 60:
            f.severity = "adjustment"
            f.action = (
                f"The target went on {when}. Nothing shorter than 60 minutes of lead time has "
                f"shown a hypoglycaemia benefit in any randomised comparison, and the consensus "
                f"asks for 60 to 120 minutes. "
                + ("A meal bolus was still active here, which is the situation where the lead "
                   "time matters most." if prandial else
                   "Little insulin was on board here, which is the situation where announcing "
                   "has repeatedly failed to show a benefit, so this may not have cost anything.")
            )
            f.citations = _cite(G.AID_LEAD_TIME, G.AID_ANNOUNCEMENT_EVIDENCE,
                                G.AAPS_TEMP_TARGET_EFFECTS)
        return [f]

    return [Finding(
        "temp-target-other", "observation",
        f"A temporary target was active, set for {tt['reason']} rather than activity",
        observed=f"A temporary target with reason {tt['reason']} covered the session.",
        guidance="A target set for another reason still raises the loop's target, and on "
                 "AndroidAPS still suppresses super micro boluses, but it is not a record that "
                 "exercise was announced.",
        citations=_cite(G.AAPS_TEMP_TARGET_EFFECTS),
    )]


def _sensor_caveats(g: SessionGlucose, intensity, u: str) -> list[Finding]:
    out = []
    for note in g.notes:
        out.append(Finding(f"data-{abs(hash(note)) % 10000}", "data",
                           "Sensor coverage", observed=note, guidance=""))

    near_threshold = (g.during.nadir_mmol is not None
                      and HYPO_L1_MMOL <= g.during.nadir_mmol <= HYPO_L1_MMOL + 1.5)
    if near_threshold or (g.steepest_fall_mmol_min or 0) < -0.1:
        out.append(Finding(
            "sensor-lag", "data", "The sensor reading during exercise is not blood glucose",
            observed=f"The session nadir of {fmt(g.during.nadir_mmol, u)} came from a sensor "
                     f"while glucose was moving.",
            guidance=(
                "Pooled mean absolute relative difference during exercise is about 13.6 percent "
                "(95 percent CI 11.4 to 15.8), and lag lengthens from about 5 minutes at rest "
                "to 12 to 24 minutes. During fasted interval work one study measured a negative "
                "bias of 2.0 mmol/L (35.3 mg/dL) and only 65.5 percent of paired values in the "
                "no-risk zone."
            ),
            action=(
                "Taking a fall at the single down arrow boundary over a lag of 12 to 24 minutes "
                "implies true glucose 1.3 to 2.7 mmol/L below the displayed value while falling "
                "fast. That arithmetic is this tool's, not a published rule, and is why the "
                "guidance raises the exercise low alert to 5.6 mmol/L (100 mg/dL) rather than "
                "trusting the number on the screen."
            ),
            citations=_cite(G.CGM_MARD_EXERCISE, G.CGM_LAG_EXERCISE, G.CGM_EXERCISE_ALERT,
                            G.CGM_IMPLIED_OFFSET),
        ))
    if not intensity.is_measured:
        out.append(Finding(
            "no-hr", "data", "No heart rate for this session",
            observed=intensity.notes[0] if intensity.notes else
                     "Intensity was taken from the activity label alone.",
            guidance="A jog and a threshold run share the label. Findings that depend on how "
                     "hard the session was are marked provisional.",
        ))
    return out
