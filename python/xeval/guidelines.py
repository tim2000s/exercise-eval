"""Published numbers, each carrying the source it came from.

Nothing in this module is the tool's own opinion. Where the guidelines disagree, both figures
are held and the disagreement is reported rather than resolved silently. Where a number is
consensus rather than measurement, the grade says so.

Two structural mismatches in the source material had to be represented rather than papered
over. The adult guidelines give carbohydrate in absolute grams while ISPAD gives grams per
kilogram of body mass with a cap at 60 kg, and the two diverge at the extremes: for a 30 kg
child ISPAD's 0.3 g/kg gives 9 g, close to the adult 10 g, whereas for a 90 kg adult the cap
binds and gives 18 g against the 20 to 35 g the adult table recommends with a falling arrow.
Both are computed and both are shown. And ISPAD's own graded recommendation on ketones
contradicts its own tables, so both readings are carried with the contradiction named.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .sources import get as source


@dataclass(frozen=True)
class Guideline:
    """One published figure, with everything needed to quote it honestly."""

    value: Any
    units: str
    source_key: str
    note: str = ""
    #: Grade as the source itself assigned it, where it uses a system. D means expert opinion.
    grade: str | None = None

    @property
    def citation(self) -> str:
        return source(self.source_key).short()

    @property
    def is_evidence(self) -> bool:
        return source(self.source_key).is_evidence

    def describe(self) -> str:
        """A phrase suitable for putting in brackets after the number in the report."""
        s = source(self.source_key)
        bits = [s.short()]
        if s.n:
            bits.append(f"n={s.n}")
        if self.grade:
            bits.append(f"grade {self.grade}")
        elif not s.is_evidence:
            bits.append("consensus")
        return ", ".join(bits)


# ---------------------------------------------------------------------------------------------
# Pre-exercise glucose bands
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class GlucoseBand:
    name: str
    low_mmol: float | None
    high_mmol: float | None
    #: Printed mg/dL bounds as the source gave them. These do not always equal an exact
    #: conversion of the mmol/L figures, because the source rounded with 18 rather than 18.0182.
    printed_mgdl: str
    aerobic: str
    anaerobic: str
    action: str

    def contains(self, mmol: float) -> bool:
        lo = -float("inf") if self.low_mmol is None else self.low_mmol
        hi = float("inf") if self.high_mmol is None else self.high_mmol
        return lo <= mmol <= hi


#: Riddell 2017 Table 1. The consensus threshold for the hyperglycaemia band is 15.0 mmol/L,
#: not the 13.9 mmol/L that the older ADA position statement uses.
PRE_EXERCISE_BANDS: tuple[GlucoseBand, ...] = (
    GlucoseBand(
        "below target", None, 4.99, "<90 mg/dL",
        "Delay until above 5.0 mmol/L", "Delay until above 5.0 mmol/L",
        "Take 10 to 20 g of glucose before starting, and monitor closely for hypoglycaemia",
    ),
    GlucoseBand(
        "near target", 5.0, 6.9, "90-124 mg/dL",
        "Take 10 g of glucose first", "Can be started",
        "Aerobic work needs 10 g of glucose first. Anaerobic work and intervals can start",
    ),
    GlucoseBand(
        "target", 7.0, 10.0, "126-180 mg/dL",
        "Can be started", "Can be started, glucose may rise",
        "No action needed before starting",
    ),
    GlucoseBand(
        "slightly above target", 10.1, 15.0, "182-270 mg/dL",
        "Can be started", "Can be started, glucose may rise further",
        "No carbohydrate. Intense work may push glucose higher still",
    ),
    GlucoseBand(
        "above target", 15.01, None, ">270 mg/dL",
        "Mild to moderate aerobic only, and only if ketones are low",
        "Not advised, it will raise glucose further",
        "If the hyperglycaemia is unexplained, check blood ketones before deciding",
    ),
)

PRE_EXERCISE_BANDS_SOURCE = Guideline(
    "Table 1", "", "riddell2017",
    "Consensus of 21 authors, no formal grading applied",
)

#: The floor below which exercise should not be started or restarted at all.
ABSOLUTE_FLOOR = Guideline(
    3.0, "mmol/L", "moser2020",
    "54 mg/dL. Do not restart exercise below this. Children may be stopped at 5.0 mmol/L "
    "(90 mg/dL) with a confirmatory fingerstick",
    grade="D",
)

SUSPEND_THRESHOLD = Guideline(
    3.9, "mmol/L", "moser2020",
    "70 mg/dL. Suspend exercise and take oral carbohydrate", grade="D",
)

RESTART_THRESHOLD = Guideline(
    4.4, "mmol/L", "moser2020",
    "80 mg/dL, with a level or rising arrow. Children restart at 5.0 mmol/L (90 mg/dL)",
    grade="D",
)


# ---------------------------------------------------------------------------------------------
# Ketones
# ---------------------------------------------------------------------------------------------

#: The glucose above which the guidelines ask for a ketone measurement. The three most recent
#: and most exercise-specific documents agree on 15.0 mmol/L; the others are kept so the
#: disagreement can be shown rather than hidden.
KETONE_CHECK_THRESHOLD = Guideline(
    15.0, "mmol/L", "riddell2017",
    "270 mg/dL. EASD/ISPAD 2020 and ISPAD 2022 agree. The ADA 2016 position statement uses "
    "13.9 mmol/L (250 mg/dL) and Diabetes Canada uses 16.7 mmol/L (300 mg/dL) and only when "
    "the person also feels unwell",
)

KETONE_CHECK_ALTERNATIVES: tuple[Guideline, ...] = (
    Guideline(13.9, "mmol/L", "ada2016", "250 mg/dL, trigger to test for ketones"),
    Guideline(16.7, "mmol/L", "diabetescanada2018",
              "300 mg/dL, and only when the person also feels unwell"),
)

KETONE_BANDS: tuple[tuple[float, float | None, str, str], ...] = (
    (0.0, 0.59, "low",
     "Mild to moderate aerobic exercise may be started (Riddell 2017)"),
    (0.6, 1.4, "modestly raised",
     "The guidelines conflict here. Riddell 2017 permits light intensity for under 30 minutes "
     "with a small corrective dose. ISPAD 2022's graded recommendation B says to postpone "
     "until the cause has been evaluated, while ISPAD's own Tables 4 and 5 allow exercise "
     "after a 15 minute wait at 0.6 to 1.0 mmol/L and a 60 minute wait at 1.1 to 1.4 mmol/L. "
     "That is an internal contradiction within one document. The conservative reading is to "
     "postpone"),
    (1.5, 2.99, "raised", "Exercise is contraindicated (Riddell 2017, EASD/ISPAD 2020, ISPAD 2022)"),
    (3.0, None, "high",
     "Manage immediately with a clinician. This is not an exercise decision"),
)

KETONE_CORRECTION_FRACTION = Guideline(
    0.5, "fraction of the usual correction dose", "moser2020",
    "EASD/ISPAD 2020, ISPAD 2022 and Zaharieva and Riddell 2017 all give 50 percent. EXTOD "
    "gives 30 percent. ISPAD offers 0.05 U/kg as an absolute alternative. A correction close "
    "to bedtime should be avoided, because it adds to post-exercise nocturnal risk",
    grade="D",
)


# ---------------------------------------------------------------------------------------------
# Risk stratification, which shifts every threshold above
# ---------------------------------------------------------------------------------------------

#: EASD/ISPAD 2020 grades hypoglycaemia risk from an awareness score, then time below
#: 3.9 mmol/L over three months, then whether a severe event occurred in the last six months.
#: Each step up the ladder shifts every threshold by roughly 1.0 to 2.0 mmol/L.
RISK_GROUPS: dict[str, dict[str, float]] = {
    "low": {
        "carb_threshold_mmol": 7.0,       # 126 mg/dL
        "child_target_low_mmol": 7.0,
        "child_target_high_mmol": 10.0,   # 126-180 mg/dL
        "post_exercise_floor_mmol": 4.4,  # 80 mg/dL
    },
    "moderate": {
        "carb_threshold_mmol": 8.0,       # 145 mg/dL
        "child_target_low_mmol": 8.0,
        "child_target_high_mmol": 11.0,   # 145-198 mg/dL
        "post_exercise_floor_mmol": 5.0,  # 90 mg/dL
    },
    "high": {
        "carb_threshold_mmol": 9.0,       # 161 mg/dL
        "child_target_low_mmol": 9.0,
        "child_target_high_mmol": 12.0,   # 162-216 mg/dL
        "post_exercise_floor_mmol": 5.6,  # 100 mg/dL
    },
}

RISK_GROUPS_SOURCE = Guideline(
    RISK_GROUPS, "mmol/L", "moser2020",
    "Risk groups are defined by hypoglycaemia awareness, then time below 3.9 mmol/L over three "
    "months, then any severe event in the last six months. Exercise frequency is counted as "
    "sessions of 45 minutes or more per week",
    grade="D",
)

#: The time below range in the preceding 24 h above which post-exercise nocturnal risk roughly
#: doubles. This is the strongest lever the tool has, because it is measurable from CGM alone.
ANTECEDENT_TBR_THRESHOLD = Guideline(
    4.0, "percent of the previous 24 h below 3.9 mmol/L", "t1dexi_noct2026",
    "At or above 4 percent, level 1 nocturnal hypoglycaemia rose from 11.7 to 22.9 percent of "
    "nights and level 2 from 3.3 to 10.2 percent, both p<0.001. The mechanism is documented at "
    "the level of hormone concentrations: antecedent hypoglycaemia blunts the adrenaline, "
    "glucagon and cortisol responses to subsequent exercise, and the blunting is detectable "
    "from a previous nadir of only 3.9 mmol/L",
)

SEVERE_HYPO_CONTRAINDICATION = Guideline(
    24, "hours", "riddell2017",
    "Severe hypoglycaemia within the previous 24 hours is a contraindication to exercise. "
    "ISPAD 2022 grade C extends this to recurrent antecedent hypoglycaemia. EXTOD adds that "
    "after a self-treated episode one should wait 45 to 60 minutes after glucose has settled",
    grade="C",
)


# ---------------------------------------------------------------------------------------------
# Overnight and post-exercise insulin
# ---------------------------------------------------------------------------------------------

OVERNIGHT_BASAL_REDUCTION = Guideline(
    0.20, "fraction of basal", "taplin2010",
    "20 percent for 6 hours from bedtime. Every guideline converges on this figure and the "
    "whole evidence base is two trials: 16 young people on pumps (Taplin 2010, overnight nadir "
    "9.6 against 7.1 mmol/L, p=0.042) and 10 adult men on MDI (Campbell 2015, 9 of 10 "
    "hypoglycaemic on unchanged basal against 0 of 10 on 80 percent). Overnight closed loop "
    "independently delivered about 20 percent less insulin between 22:00 and 02:00 on "
    "post-exercise nights (Sherr 2013, p=0.008)",
)

OVERNIGHT_BASAL_REDUCTION_HOURS = Guideline(
    6, "hours from bedtime", "taplin2010",
    "Diabetes Canada expresses the same window as bedtime to 03:00",
)

OVERNIGHT_BASAL_REDUCTION_LOW_START = Guideline(
    0.40, "fraction of basal", "ispad2022",
    "ISPAD raises the reduction to 40 percent for 6 hours when pre-exercise glucose was below "
    "5.0 mmol/L (90 mg/dL), and asks for no reduction when it was above 15.0 mmol/L "
    "(270 mg/dL). Neither figure has a trial behind it",
    grade="D",
)

MDI_DAILY_BASAL_REDUCTION = Guideline(
    (0.20, 0.30), "fraction of the long-acting analogue", "zaharieva2017",
    "20 to 30 percent for an unusually active day, with a further 10 to 20 percent off the "
    "bedtime dose after prolonged aerobic activity. Expert review rather than trial-derived",
)

#: The delayed risk window after late-afternoon or evening exercise. Two peaks exist, and the
#: second is what catches people out.
LATE_HYPO_WINDOW_HOURS = Guideline(
    (7, 11), "hours after the session", "mcmahon2007",
    "Glucose requirement rose biphasically after 45 minutes of afternoon exercise, with a "
    "second separate peak 7 to 11 hours later. For a session ending at 17:00 that falls "
    "between about midnight and 04:00. Midday exercise produced a single continuous elevation "
    "lasting about 11 hours with no second peak (Davey 2013), which is why ISPAD does not ask "
    "for an overnight adjustment after a lunchtime session",
)

RAISED_SENSITIVITY_HOURS = Guideline(
    (24, 48), "hours", "riddell2017",
    "This is a physiological statement rather than a trial endpoint. No clamp study in type 1 "
    "diabetes has measured insulin sensitivity out to 48 hours after a single bout, and the "
    "upper end is extrapolated from muscle glycogen work in people without diabetes. The "
    "trial-derived figures are 24 hours of protection needed (Campbell 2015) and events "
    "clustering at 15 to 24 hours (Gomez 2015)",
)


INSULIN_ON_BOARD_EFFECT = Guideline(
    None, "", "riddell2017",
    "Circulating insulin is what converts exercise into a fall in glucose. Muscle contraction "
    "raises glucose uptake by an insulin-independent route, but the size of the fall depends on "
    "how much insulin is present at the same time, which is why the consensus adjusts the "
    "pre-exercise bolus as well as basal. The same session started in the tail of a bolus and "
    "started with little insulin on board behave differently",
)


# ---------------------------------------------------------------------------------------------
# Bedtime
# ---------------------------------------------------------------------------------------------

BEDTIME_SNACK_THRESHOLD = Guideline(
    10.0, "mmol/L", "kalergis2003",
    "180 mg/dL. Above this no snack was needed, though 46 percent of morning hyperglycaemia "
    "was associated with taking one anyway. Between 7 and 10 mmol/L any snack sufficed, and "
    "below 7 mmol/L (126 mg/dL) a standard or protein-containing snack was needed. The trial "
    "was in 15 adults on bedtime NPH and was not an exercise study",
)

BEDTIME_PROTEIN_THRESHOLD = Guideline(
    7.0, "mmol/L", "ispad2022",
    "126 mg/dL. Add 15 g of protein below this, on top of the carbohydrate", grade="D",
)

BEDTIME_SNACK_CARB_PER_KG = Guideline(
    0.4, "g per kg body mass", "campbell2014",
    "Low to medium glycaemic index. The figure comes from 10 adult men. A low glycaemic index "
    "snack protected against early hypoglycaemia for about 8 hours but nocturnal hypoglycaemia "
    "occurred in 5 of 10 in both arms, so the snack alone does not prevent the late episode",
)

BEDTIME_SNACK_CAVEAT = Guideline(
    None, "", "raju2006",
    "The strongest negative result in this area. In 21 adults, neither a conventional snack, "
    "with or without acarbose, nor uncooked cornstarch raised the overnight nadir or reduced "
    "the number of low readings. A snack without an insulin reduction should not be relied on",
)

BEDTIME_GLUCOSE_CAVEAT = Guideline(
    7.2, "mmol/L", "tsalikian2005",
    "130 mg/dL. On sedentary nights hypoglycaemia was unusual above this level, but on "
    "exercise nights it occurred fairly frequently even above it. A rule keyed on bedtime "
    "glucose alone under-predicts risk after afternoon exercise",
)


# ---------------------------------------------------------------------------------------------
# Carbohydrate keyed to trend arrow
# ---------------------------------------------------------------------------------------------

#: Rate-of-change bands, ISPAD 2022 Table 7, as mmol/L per minute. Abbott and Senseonics do not
#: use the double arrows and their single arrow covers everything beyond 30 mg/dL per 15 min.
TREND_BANDS: tuple[tuple[str, float, float], ...] = (
    ("falling fast", -float("inf"), -0.1667),   # steeper than 3.0 mg/dL/min
    ("falling", -0.1667, -0.1111),              # 2.0 to 3.0 mg/dL/min
    ("drifting down", -0.1111, -0.0556),        # 1.0 to 2.0 mg/dL/min
    ("steady", -0.0556, 0.0556),                # under 1.0 mg/dL/min
    ("drifting up", 0.0556, 0.1111),
    ("rising", 0.1111, 0.1667),
    ("rising fast", 0.1667, float("inf")),
)

TREND_BANDS_SOURCE = Guideline(
    TREND_BANDS, "mmol/L per minute", "ispad2022",
    "Converted from the per-15-minute figures the guideline prints: under 15, 15 to 30, 30 to "
    "45 and above 45 mg/dL per 15 minutes",
)

#: EASD/ISPAD 2020, adults at low hypoglycaemia risk, absolute grams.
CARB_BY_TREND_DURING: dict[str, tuple[int, int]] = {
    "steady": (10, 15),
    "drifting down": (15, 25),
    "falling": (20, 35),
    "falling fast": (20, 35),
}

CARB_BY_TREND_AFTER: dict[str, tuple[int, int]] = {
    "steady": (10, 10),
    "drifting down": (15, 15),
    "falling": (15, 25),
    "falling fast": (15, 25),
}

CARB_BY_TREND_SOURCE = Guideline(
    CARB_BY_TREND_DURING, "g", "moser2020",
    "Taken at a threshold of 7.0 mmol/L (126 mg/dL) during exercise, and at the post-exercise "
    "floor for the recovery window. Repeat every 15 to 20 minutes at the lower threshold, and "
    "expect up to 20 minutes before the arrow responds. These figures are stated not to apply "
    "to hybrid closed-loop systems",
    grade="D",
)

#: ISPAD 2022 Table 5, g per kg body mass per 20 minutes, keyed on band and trend, given as
#: (regular insulin on board, less insulin on board).
CARB_PER_KG_BY_BAND_AND_TREND: dict[str, dict[str, tuple[float, float]]] = {
    "10.1-15.0": {"rising": (0.0, 0.0), "drifting up": (0.0, 0.0), "steady": (0.0, 0.0),
                  "drifting down": (0.1, 0.0), "falling": (0.2, 0.0)},
    "7.0-10.0":  {"rising": (0.0, 0.0), "drifting up": (0.1, 0.0), "steady": (0.2, 0.0),
                  "drifting down": (0.3, 0.1), "falling": (0.4, 0.2)},
    "5.0-6.9":   {"rising": (0.1, 0.0), "drifting up": (0.2, 0.1), "steady": (0.3, 0.2),
                  "drifting down": (0.4, 0.3), "falling": (0.5, 0.4)},
    "4.0-4.9":   {"rising": (0.2, 0.1), "drifting up": (0.3, 0.2), "steady": (0.3, 0.3),
                  "drifting down": (0.4, 0.4), "falling": (0.5, 0.5)},
}

#: Body mass above which the ISPAD table stops scaling. It exists because peak exogenous
#: carbohydrate oxidation is 1.0 to 1.2 g/min and the table would otherwise exceed it.
ISPAD_WEIGHT_CAP_KG = Guideline(
    60.0, "kg", "ispad2022",
    "Above the 91st BMI centile, ideal body weight is used instead, taken as BMI at the 50th "
    "centile for age multiplied by height in metres squared, unless the centile reflects "
    "muscle mass rather than fat",
    grade="D",
)


# ---------------------------------------------------------------------------------------------
# CGM behaviour during exercise
# ---------------------------------------------------------------------------------------------

CGM_MARD_EXERCISE = Guideline(
    (11.41, 15.84), "percent, 95 percent confidence interval", "moser2020",
    "Pooled mean absolute relative difference of about 13.63 percent across exercise types. "
    "Individual studies: 13 percent for aerobic work with Dexcom G4 and G5 (Zaharieva 2019), "
    "17.8 percent during fasted HIIT against 10.4 percent at rest (Li 2019, p<0.001), and 7.7 "
    "to 16.8 percent across aerobic, resistance and interval work with G6 (Guillot 2020)",
)

CGM_LAG_EXERCISE = Guideline(
    (12, 24), "minutes", "moser2020",
    "Lag lengthens from about 5 minutes at rest. Guillot 2020 measured a median of 1 minute "
    "for aerobic exercise but 18 and 19 minutes for resistance and interval work. Li 2019 "
    "measured 35 minutes to half-maximal rise during HIIT, with a negative bias of 2.0 mmol/L "
    "(35.3 mg/dL) and only 65.5 percent of paired values in the no-risk zone",
)

CGM_EXERCISE_ALERT = Guideline(
    5.6, "mmol/L", "moser2020",
    "100 mg/dL, the highest low-alert threshold available on current systems. The statement "
    "gives the reason explicitly: it is in line with the expected delay between interstitial "
    "and blood glucose when levels are falling during prolonged exercise",
    grade="D",
)

#: The tool's own arithmetic rather than a published rule. It is labelled as such wherever used.
CGM_IMPLIED_OFFSET = Guideline(
    (1.3, 2.7), "mmol/L below the displayed value", "moser2020",
    "Derived here, not published: a fall at the single-down arrow boundary of 2 mg/dL per "
    "minute over a lag of 12 to 24 minutes implies true glucose 24 to 48 mg/dL below what the "
    "sensor shows. That is the same order as the 35.3 mg/dL bias Li 2019 measured during HIIT "
    "and as the raised 5.6 mmol/L alert. No guideline converts lag into an offset this way, so "
    "the figure is an inference and is presented as one",
)
