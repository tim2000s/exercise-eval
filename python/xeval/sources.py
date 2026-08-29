"""The bibliography behind every number the tool quotes.

A recommendation that cannot be traced to a measurement or a citation does not belong in the
output, so each entry here records not only the reference but the design, the number of
participants and the population, because those decide how much weight a reader should give it.

The distinction that matters most in this literature is between a figure derived from a trial
and a figure agreed by a consensus panel. The guideline tables are numerically precise well
beyond the precision of the evidence beneath them: the 20 percent overnight basal reduction
that every guideline gives rests on two trials totalling 26 people, and most of the
pre-exercise threshold table is graded D, meaning expert opinion. The tool shows the grade
alongside the number rather than presenting all of them as equivalent.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """One reference, with what a reader needs to judge its weight."""

    key: str
    citation: str
    year: int
    #: trial, observational, clamp, consensus, guideline, or inference for something this tool
    #: derived rather than found published.
    design: str
    #: Participants, or None where the source is a consensus document rather than a study.
    n: int | None
    population: str | None
    #: The grading the source itself assigned, where it uses a grading system.
    grade: str | None = None

    @property
    def is_evidence(self) -> bool:
        """True where a number came from measurement rather than from agreement."""
        return self.design in {"trial", "observational", "clamp"}

    def short(self) -> str:
        author = self.citation.split(",")[0].split(" et al")[0].strip()
        return f"{author} {self.year}"


def _s(*args, **kwargs) -> tuple[str, Source]:
    src = Source(*args, **kwargs)
    return src.key, src


SOURCES: dict[str, Source] = dict(
    [
        # Consensus and guideline documents
        _s(
            "riddell2017",
            "Riddell MC, Gallen IW, Smart CE, et al. Exercise management in type 1 diabetes: "
            "a consensus statement. Lancet Diabetes Endocrinol 2017;5:377-390. PMID 28126459",
            2017, "consensus", None,
            "Consensus of 21 authors. No formal grading system was applied",
        ),
        _s(
            "moser2020",
            "Moser O, Riddell MC, Eckstein ML, et al. Glucose management for exercise using "
            "CGM and isCGM systems in type 1 diabetes: position statement of the EASD and "
            "ISPAD. Diabetologia 2020;63:2501-2520. PMID 33047481",
            2020, "guideline", None,
            "Adults and children from 6 years. Most exercise-threshold recommendations "
            "graded D, meaning expert opinion or extrapolation",
            grade="D",
        ),
        _s(
            "ispad2022",
            "Adolfsson P, Taplin CE, Zaharieva DP, et al. ISPAD Clinical Practice Consensus "
            "Guidelines 2022: Exercise in children and adolescents with diabetes. "
            "Pediatr Diabetes 2022;23:1341-1372. PMID 36537529",
            2022, "guideline", None,
            "Children and adolescents. Numbers are stated per kilogram of body mass with a "
            "60 kg cap",
        ),
        _s(
            "ada2016",
            "Colberg SR, Sigal RJ, Yardley JE, et al. Physical activity/exercise and diabetes: "
            "a position statement of the American Diabetes Association. "
            "Diabetes Care 2016;39:2065-2079. PMID 27926890",
            2016, "guideline", None, "Adults, all diabetes types",
        ),
        _s(
            "diabetescanada2018",
            "Diabetes Canada Clinical Practice Guidelines Expert Committee. Physical activity "
            "and diabetes. Can J Diabetes 2018;42(Suppl 1):S54-S63",
            2018, "guideline", None, "Adults", grade="B",
        ),
        _s(
            "extod",
            "EXTOD. Blood glucose and exercise for adults with type 1 diabetes. "
            "https://extod.org",
            2023, "guideline", None,
            "UK practitioner guidance for adults. No formal grading published",
        ),
        _s(
            "zaharieva2017",
            "Zaharieva DP, Riddell MC. Insulin management strategies for exercise in diabetes. "
            "Can J Diabetes 2017;41:507-516",
            2017, "consensus", None, "Expert review, adults",
        ),
        # Post-exercise nocturnal hypoglycaemia
        _s(
            "tsalikian2005",
            "Tsalikian E, Mauras N, Beck RW, et al. Impact of exercise on overnight glycemic "
            "control in children with type 1 diabetes mellitus. J Pediatr 2005;147:528-534. "
            "PMID 16227041",
            2005, "trial", 50,
            "Ages 11 to 17, 54 percent pump and 46 percent MDI. Inpatient randomised "
            "crossover, 75 min treadmill from 16:00 with no insulin adjustment",
        ),
        _s(
            "taplin2010",
            "Taplin CE, Cobry E, Messer L, et al. Preventing post-exercise nocturnal "
            "hypoglycemia in children with type 1 diabetes. J Pediatr 2010;157:784-788. "
            "PMID 20650471",
            2010, "trial", 16,
            "Young people on pumps, mean age 13.3 years, after 60 min of exercise",
        ),
        _s(
            "campbell2015",
            "Campbell MD, Walker M, Bracken RM, et al. Insulin therapy and dietary adjustments "
            "to normalize glycemia and prevent nocturnal hypoglycemia after evening exercise "
            "in type 1 diabetes. BMJ Open Diabetes Res Care 2015;3:e000085. PMID 26019878",
            2015, "trial", 10,
            "Adult men on MDI, 45 min running at about 70 percent VO2peak at 18:00",
        ),
        _s(
            "campbell2014",
            "Campbell MD, Walker M, Trenell MI, et al. A low-glycemic index meal and bedtime "
            "snack prevents postprandial hyperglycemia. Diabetes Care 2014;37:1845-1853. "
            "PMID 24784832",
            2014, "trial", 10, "Adult men, evening exercise, low against high glycaemic index",
        ),
        _s(
            "kalergis2003",
            "Kalergis M, Schiffrin A, Gougeon R, et al. Impact of bedtime snack composition on "
            "prevention of nocturnal hypoglycemia in adults with type 1 diabetes. "
            "Diabetes Care 2003;26:9-15. PMID 12502652",
            2003, "trial", 15,
            "Adults on lispro at meals with bedtime NPH. Not an exercise study, and it "
            "predates analogue basal insulin",
        ),
        _s(
            "raju2006",
            "Raju B, Arbelaez AM, Breckenridge SM, Cryer PE. Nocturnal hypoglycemia in type 1 "
            "diabetes: an assessment of preventive bedtime treatments. "
            "J Clin Endocrinol Metab 2006;91:2087-2092. PMID 16492699",
            2006, "trial", 21,
            "Adults. Not an exercise study. A conventional snack did not raise the nadir",
        ),
        _s(
            "mcmahon2007",
            "McMahon SK, Ferreira LD, Ratnam N, et al. Glucose requirements to maintain "
            "euglycemia after moderate-intensity afternoon exercise in adolescents with type 1 "
            "diabetes are increased in a biphasic manner. "
            "J Clin Endocrinol Metab 2007;92:963-968. PMID 17118993",
            2007, "clamp", 9,
            "Adolescents, 45 min afternoon exercise at 95 percent of lactate threshold",
        ),
        _s(
            "davey2013",
            "Davey RJ, Howe W, Paramalingam N, et al. The effect of midday moderate-intensity "
            "exercise on postexercise hypoglycemia risk in individuals with type 1 diabetes. "
            "J Clin Endocrinol Metab 2013;98:2908-2914. PMID 23780373",
            2013, "clamp", 10, "Adolescents, 45 min at midday, 17 h of clamp",
        ),
        _s(
            "gomez2015",
            "Gomez AM, Gomez C, Aschner P, et al. Effects of performing morning versus "
            "afternoon exercise on glycemic control and hypoglycemia frequency in type 1 "
            "diabetes patients on sensor-augmented insulin pump therapy. "
            "J Diabetes Sci Technol 2015;9:619-624. PMID 25555390",
            2015, "trial", 35, "Adults on sensor-augmented pumps, mean age 30.3 years",
        ),
        _s(
            "sherr2013",
            "Sherr JL, Cengiz E, Palerm CC, et al. Reduced hypoglycemia and increased time in "
            "target using closed-loop insulin delivery during nights with or without antecedent "
            "afternoon exercise in type 1 diabetes. Diabetes Care 2013;36:2909-2914. "
            "PMID 23757427",
            2013, "trial", 12, "Ages 12 to 26, inpatient crossover",
        ),
        _s(
            "t1dexi2023",
            "Riddell MC, Li Z, Gal RL, et al. Examining the acute glycemic effects of different "
            "types of structured exercise sessions in type 1 diabetes in a real-world setting: "
            "the Type 1 Diabetes and Exercise Initiative. Diabetes Care 2023;46:704-713. "
            "PMID 36795053",
            2023, "observational", 497,
            "Adults, real-world structured sessions of aerobic, interval and resistance "
            "exercise. The largest dataset of its kind",
        ),
        _s(
            "t1dexi_noct2026",
            "Bisno DI, Turner LV, Gallop RJ, et al. Factors associated with nocturnal "
            "hypoglycemia after exercise in the Type 1 Diabetes and Exercise Initiative. "
            "Diabetes Care 2026;49:1404-1413. PMID 42247270",
            2026, "observational", 496,
            "Adults, 12,340 nights, mixed MDI, pump and hybrid closed loop",
        ),
        _s(
            "t1dexip2024",
            "Sherr JL, Bergford S, Gal RL, et al. Exploring factors that influence "
            "postexercise glycemia in youth with type 1 diabetes in the real world: T1DEXIP. "
            "Diabetes Care 2024;47:849-857. PMID 38412033",
            2024, "observational", 251, "Adolescents, mean age 14 years, 3,319 activities",
        ),
        _s(
            "zivkovic2026",
            "Zivkovic J, Mitter M, Theodorou D, et al. Exercise in type 1 diabetes: real-world "
            "data on glucose levels and hypoglycaemia risk from over 420,000 exercise "
            "sessions. Diabetologia 2026;69:1457-1467. PMID 41686193",
            2026, "observational", 3248,
            "Adults, mean age 41.2 years, 428,058 sessions logged in a consumer app",
        ),
        # Counterregulation
        _s(
            "davis2000",
            "Davis SN, Galassetti P, Wasserman DH, Tate D. Effects of antecedent hypoglycemia "
            "on subsequent counterregulatory responses to exercise. Diabetes 2000;49:73-81. "
            "PMID 10615952",
            2000, "clamp", 16, "Adults without diabetes",
        ),
        _s(
            "galassetti2006",
            "Galassetti P, Tate D, Neill RA, et al. Effect of differing antecedent hypoglycemia "
            "on counterregulatory responses to exercise in type 1 diabetes. "
            "Am J Physiol Endocrinol Metab 2006;290:E1109-E1117. PMID 16403779",
            2006, "clamp", 22,
            "Adults with type 1 diabetes. Blunting was graded by the depth of the antecedent "
            "low and was detectable from a nadir of only 3.9 mmol/L",
        ),
        _s(
            "sandoval2004",
            "Sandoval DA, Guy DL, Richardson MA, et al. Effects of low and moderate antecedent "
            "exercise on counterregulatory responses to subsequent hypoglycemia in type 1 "
            "diabetes. Diabetes 2004;53:1798-1806. PMID 15220204",
            2004, "clamp", 27,
            "Adults with type 1 diabetes. Exercise at 30 percent VO2max blunted "
            "counterregulation as much as exercise at 50 percent",
        ),
        # CGM behaviour during exercise
        _s(
            "zaharieva2019",
            "Zaharieva DP, Turksoy K, McGaugh SM, et al. Lag time remains with newer real-time "
            "continuous glucose monitoring technology during aerobic exercise in adults living "
            "with type 1 diabetes. Diabetes Technol Ther 2019;21:313-321. PMID 31059282",
            2019, "trial", 17, "Adults on pumps, Dexcom G4 and G5, 60 min aerobic exercise",
        ),
        _s(
            "li2019",
            "Li A, Riddell MC, Potashner D, et al. Time lag and accuracy of continuous glucose "
            "monitoring during high intensity interval training in adults with type 1 diabetes. "
            "Diabetes Technol Ther 2019;21:286-294. PMID 31017497",
            2019, "trial", 17, "Adults on MDI, Dexcom G4, four fasted 25 min HIIT sessions",
        ),
        _s(
            "guillot2020",
            "Guillot FH, Jacobs PG, Wilson LM, et al. Accuracy of the Dexcom G6 glucose sensor "
            "during aerobic, resistance, and interval exercise in adults with type 1 diabetes. "
            "Biosensors 2020;10:138. PMID 33003524",
            2020, "trial", 24, "Adults on MDI, Dexcom G6, in-clinic sessions of 30 min",
        ),
        # Insulin adjustment
        _s(
            "rabasa2001",
            "Rabasa-Lhoret R, Bourque J, Ducros F, Chiasson JL. Guidelines for premeal insulin "
            "dose reduction for postprandial exercise of different intensities and durations in "
            "type 1 diabetic subjects treated intensively with a basal-bolus insulin regimen. "
            "Diabetes Care 2001;24:625-630. PMID 11315820",
            2001, "trial", 8,
            "Men only, six per exercise arm. Women were excluded because of the effect of "
            "menstrual cyclicity on glucose homeostasis, so the bolus reduction table was "
            "derived entirely in men. Only four of its six cells were tested",
        ),
        _s(
            "mcauley2016",
            "McAuley SA, Horsburgh JC, Ward GM, et al. Insulin pump basal adjustment for "
            "exercise in type 1 diabetes: a randomised crossover study. "
            "Diabetologia 2016;59:1636-1644. PMID 27168135",
            2016, "trial", 14,
            "Adults on pump therapy, fasted, with venous sampling every 15 minutes",
        ),
        _s(
            "mcauley2017",
            "McAuley SA, Ward GM, Horsburgh JC, et al. Insulin pump basal rate adjustments: "
            "time to steady state. Diabet Med 2017;34:1158-1164. PMID 28453877",
            2017, "trial", 12, "Adults on pump therapy, sampling to 300 minutes",
        ),
        _s(
            "royfleming2019",
            "Roy-Fleming A, Taleb N, Messier V, et al. Timing of insulin basal rate reduction "
            "to reduce hypoglycemia during late post-prandial exercise in adults with type 1 "
            "diabetes using insulin pump therapy. Diabetes Metab 2019;45:294-300. PMID 30165156",
            2019, "trial", 22,
            "Adults, 45 min at 60 percent VO2peak three hours after lunch. The primary "
            "outcome was null",
        ),
        _s(
            "zaharieva2019basal",
            "Zaharieva DP, McGaugh S, Pooni R, et al. Improved open-loop glucose control with "
            "basal insulin reduction 90 minutes before aerobic exercise in patients with type 1 "
            "diabetes on continuous subcutaneous insulin infusion. "
            "Diabetes Care 2019;42:824-831. PMID 30796112",
            2019, "trial", 17,
            "Adults on pumps with no insulin on board at exercise onset, 60 min treadmill at "
            "about 50 percent VO2peak",
        ),
        _s(
            "heinemann2009",
            "Heinemann L, Nosek L, Kapitza C, et al. Changes in basal insulin infusion rates "
            "with subcutaneous insulin infusion: time until a change in metabolic effect is "
            "induced. Diabetes Care 2009;32:1437-1439. PMID 19487635",
            2009, "clamp", 10, "Men with type 1 diabetes, euglycaemic clamp",
        ),
        _s(
            "direcnet2006",
            "DirecNet Study Group, Tsalikian E, Kollman C, et al. Prevention of hypoglycemia "
            "during exercise in children with type 1 diabetes by suspending basal insulin. "
            "Diabetes Care 2006;29:2200-2204. PMID 17003293",
            2006, "trial", 49,
            "Children and adolescents aged 8 to 17 on pumps, with the last bolus about four "
            "hours earlier so the rapid-acting depot was small",
        ),
        _s(
            "campbell2013",
            "Campbell MD, Walker M, Trenell MI, et al. Large pre- and postexercise rapid-acting "
            "insulin reductions preserve glycemia and prevent early- but not late-onset "
            "hypoglycemia in patients with type 1 diabetes. "
            "Diabetes Care 2013;36:2217-2224. PMID 23514728",
            2013, "trial", 11, "Men on multiple daily injections, morning exercise",
        ),
        _s(
            "heise2017",
            "Heise T, Zijlstra E, Nosek L, et al. Pharmacological properties of faster-acting "
            "insulin aspart vs insulin aspart in patients with type 1 diabetes receiving "
            "continuous subcutaneous insulin infusion. "
            "Diabetes Obes Metab 2017;19:208-215. PMID 27709762",
            2017, "clamp", 48, "Adults with type 1 diabetes, pump-delivered bolus",
        ),
        # Automated insulin delivery
        _s(
            "tagougui2020",
            "Tagougui S, Taleb N, Legault L, et al. A single-blind, randomised, crossover study "
            "to reduce hypoglycaemia risk during postprandial exercise with closed-loop insulin "
            "delivery in adults with type 1 diabetes. Diabetologia 2020;63:2282-2291. "
            "PMID 32740723",
            2020, "trial", 37,
            "Adults, exercise 90 minutes after breakfast with an active meal bolus",
        ),
        _s(
            "mccarthy2023",
            "McCarthy OM, Christensen MB, Kristensen KB, et al. Glycemic responses to exercise "
            "in adults with type 1 diabetes using an automated insulin delivery system. "
            "Diabetes Technol Ther 2023;25:476-484. PMID 37053529",
            2023, "trial", 10,
            "Adults on the MiniMed 780G, exercise 90 minutes after a carbohydrate drink",
        ),
        _s(
            "turner2025",
            "Turner LV, Sherr JL, Zaharieva DP, et al. Activity feature use before exercise in "
            "adults and youth using an automated insulin delivery system. "
            "Diabetes Care 2025;48:1598-1606. PMID 40680105",
            2025, "trial", 38,
            "Adults and young people on Omnipod 5, exercising at least three hours after the "
            "last bolus. The primary outcome was null",
        ),
        _s(
            "morrison2025",
            "Morrison DJ, Vogrin S, Zaharieva DP, et al. Timing of temporary target activation "
            "before exercise in adults using automated insulin delivery. "
            "Diabetes Obes Metab 2025;27:5160-5170. PMID 40566793",
            2025, "trial", 26,
            "Adults on the MiniMed 780G, 16 randomised bouts each, at least three hours after "
            "a meal. Median time below range was zero in every arm",
        ),
        _s(
            "moser2025",
            "Moser O, Zaharieva DP, Adolfsson P, et al. The use of automated insulin delivery "
            "around physical activity and exercise in type 1 diabetes: position statement of "
            "the EASD and ISPAD. Diabetologia 2025;68:255-280. PMID 39653802",
            2025, "guideline", None,
            "Adults and children on automated insulin delivery. Graded A to D",
            grade="A",
        ),
        # Carbohydrate and the expected response
        _s(
            "garciagarcia2015",
            "Garcia-Garcia F, Kumareswaran K, Hovorka R, Hernando ME. Quantifying the acute "
            "changes in glucose with exercise in type 1 diabetes: a systematic review and "
            "meta-analysis. Sports Med 2015;45:587-599. PMID 25616852",
            2015, "observational", None,
            "Meta-analysis of ten studies with digitised population glucose profiles. Mostly "
            "laboratory conditions with insulin on board",
        ),
        _s(
            "francescato2004",
            "Francescato MP, Geat M, Fusi S, et al. Carbohydrate requirement and insulin "
            "concentration during moderate exercise in type 1 diabetic patients. "
            "Metabolism 2004;53:1126-1130",
            2004, "trial", 12,
            "Adults, 1 h constant-workload cycling at four intervals after the morning dose, "
            "with carbohydrate titrated to prevent hypoglycaemia",
        ),
        _s(
            "broz2021",
            "Broz J, Campbell MD, Urbanova J, et al. Characterization of individualized "
            "glycemic excursions during a standardized bout of hypoglycemia-inducing exercise "
            "and subsequent hypoglycemia treatment. Nutrients 2021;13:4165",
            2021, "trial", 10,
            "Men on pump therapy. The only study of hypoglycaemia treatment around exercise, "
            "and the glucose was given once exercise had already stopped",
        ),
        _s(
            "dube2005",
            "Dube MC, Weisnagel SJ, Prud'homme D, Lavoie C. Exercise and newer insulins: how "
            "much glucose supplement to avoid hypoglycemia? "
            "Med Sci Sports Exerc 2005;37:1276-1282",
            2005, "trial", 9,
            "Adults, 60 min at 50 percent VO2max three hours after breakfast",
        ),
        _s(
            "t1dexi_matched2025",
            "Glucose-lowering effects of physical activity in type 1 diabetes: a causal "
            "modelling and matched-pair analysis. Diabetes Obes Metab 2025. PMC12628732",
            2025, "observational", 482,
            "1,546 real-world bouts of 10 to 30 minutes from T1DEXI and T1DEXIP, matched on "
            "starting glucose, rate of change, insulin on board and glucose variability",
        ),
        _s(
            "scott2021",
            "Scott SN, Fontana FY, Cocks M, et al. Post-exercise recovery for the endurance "
            "athlete with type 1 diabetes: a consensus statement. "
            "Lancet Diabetes Endocrinol 2021;9:304-317. PMID 33864810",
            2021, "consensus", None,
            "Endurance athletes. The statement notes that no measurement of post-exercise "
            "glycogen resynthesis has been made in anyone with type 1 diabetes, so its figures "
            "are transferred from athletes without diabetes",
        ),
    ]
)


def get(key: str) -> Source:
    """Look up a source, failing loudly rather than quietly emitting an uncited number."""
    try:
        return SOURCES[key]
    except KeyError:  # pragma: no cover - a programming error, not a data condition
        raise KeyError(
            f"No source registered under {key!r}. Every quoted number needs one, so add the "
            f"reference to xeval.sources rather than removing the citation."
        ) from None
