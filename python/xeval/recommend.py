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
    f += _basal(basal, intensity, session)
    f += _bolus(boluses, intensity)
    f += _iob(iob_at_start, cob_at_start, glucose, intensity)
    f += _carbohydrate(glucose, intensity, body_mass_kg, is_child, u)
    f += _overnight(glucose, session, intensity, basal, u)
    f += _temp_target(temp_target, session)
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
            "basal-late", "adjustment", "The basal reduction started late",
            observed=f"The reduction began {when}.",
            guidance=(
                "A basal reduction acts on the insulin already in the subcutaneous depot, so it "
                "takes time to change circulating insulin. Reductions started at the beginning "
                "of a session have little effect during it."
            ),
            action="Starting the same reduction earlier would deliver most of its effect during "
                   "the session rather than after it.",
            citations=_cite(G.OVERNIGHT_BASAL_REDUCTION),
        ))
    return findings


def _bolus(boluses: list, intensity) -> list[Finding]:
    if not boluses:
        return []
    out = []
    for b in boluses:
        if b.reduction_fraction is None:
            continue
        pct = b.reduction_fraction * 100
        if pct >= 15:
            out.append(Finding(
                f"bolus-reduced-{int(b.at_ms)}", "observation",
                f"The meal {b.minutes_before:.0f} minutes before was bolused "
                f"{pct:.0f} percent under the profile ratio",
                observed=f"{b.carbs_g:.0f} g of carbohydrate was covered with "
                         f"{b.insulin_given_u:.1f} U where the profile ratio implies "
                         f"{b.insulin_expected_u:.1f} U.",
                guidance="Reducing the bolus for a meal eaten shortly before exercise is the "
                         "standard adjustment for a session within the action of that dose.",
                action="",
                citations=_cite(G.OVERNIGHT_BASAL_REDUCTION),
                provisional=True,
            ))
            out[-1].guidance += " " + b.caveat
        elif pct <= 5 and b.minutes_before <= 150:
            out.append(Finding(
                f"bolus-full-{int(b.at_ms)}", "adjustment",
                f"A full meal bolus was given {b.minutes_before:.0f} minutes before the session",
                observed=f"{b.carbs_g:.0f} g of carbohydrate was covered with "
                         f"{b.insulin_given_u:.1f} U, which is what the profile ratio implies.",
                guidance="A meal bolus given within the two to three hours before exercise is "
                         "still substantially active during it, and circulating insulin is what "
                         "converts exercise into a fall in glucose. " + b.caveat,
                action="Reducing this bolus is usually more effective than adding carbohydrate "
                       "during the session, because it acts on the cause rather than the effect.",
                citations=(),
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


def _carbohydrate(g: SessionGlucose, intensity, body_mass_kg, is_child, u: str) -> list[Finding]:
    d = g.during
    duration_min = (d.end_ms - d.start_ms) / MS_PER_MIN
    taken = g.carbs_during_g

    if intensity.modality == "low" or duration_min < 20:
        return []

    # The two guideline families give carbohydrate in different currencies and diverge at the
    # extremes, so both are computed and both are shown.
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
                "20 minutes." + per_kg_note
            ),
            action="Carbohydrate taken during the session, or a larger insulin reduction before "
                   "it, would both have flattened this. Which is preferable depends on whether "
                   "the session was planned.",
            citations=_cite(G.CARB_BY_TREND_SOURCE, G.ISPAD_WEIGHT_CAP_KG),
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
                     + per_kg_note,
            citations=_cite(G.CARB_BY_TREND_SOURCE),
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


def _temp_target(tt: dict | None, session) -> list[Finding]:
    if tt is None:
        return [Finding(
            "no-temp-target", "adjustment", "The session was not announced with a temporary target",
            observed="No temporary target covered this session.",
            guidance="On a closed loop, a raised target is what actually changes the algorithm's "
                     "behaviour. A care portal exercise event records the intention but changes "
                     "nothing.",
            action="Setting an activity target before the session, rather than at its start, "
                   "gives the system time to act on it.",
        )]
    if tt["announced_as_exercise"]:
        lead = tt["lead_time_min"]
        when = (f"{lead:.0f} minutes before the session"
                if lead >= 0 else f"{-lead:.0f} minutes after it started")
        f = Finding(
            "temp-target", "observation", "The session was announced as activity",
            observed=f"An activity temporary target of "
                     f"{tt['target_mmol']:.1f} mmol/L was set {when}, lasting "
                     f"{tt['duration_min']:.0f} minutes.",
            guidance="This is the strongest available signal that the session was announced to "
                     "the system, because it is what changed the algorithm's behaviour rather "
                     "than only recording an intention.",
        )
        if lead < 30:
            f.action = ("The target was set close to the session start. A longer lead time gives "
                        "the system time to reduce delivery before the work begins.")
            f.severity = "adjustment"
        return [f]
    return [Finding(
        "temp-target-other", "observation",
        f"A temporary target was active, set for {tt['reason']} rather than activity",
        observed=f"A temporary target with reason {tt['reason']} covered the session.",
        guidance="A target set for another reason still raises the loop's target, but it is not "
                 "a record that exercise was announced.",
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
