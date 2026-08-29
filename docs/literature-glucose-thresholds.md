# Pre-exercise thresholds and post-exercise hypoglycaemia

Specification for the threshold rules in `python/xeval/guidelines.py`. Every number here
carries its source. Conversions use 18.0182 mg/dL per mmol/L; where a source printed its own
rounded conversion, the source's figure is given.

Almost everything in Part B is graded D or level 4, meaning expert opinion. The exceptions are
the counterregulation clamp studies in A5, with n of 16 to 27, and the two overnight basal
reduction trials with n of 16 young people and 10 adult men. The numeric precision of the
guideline tables considerably exceeds the precision of the evidence behind them, and the tool
says so wherever it quotes one.

## Part A. Post-exercise hypoglycaemia

### A1. Incidence of nocturnal hypoglycaemia after exercise

| Study | Design | Exercise nights | Control nights | p |
|---|---|---|---|---|
| DirecNet, Tsalikian 2005 | Inpatient randomised crossover, n=50, ages 11-17, 75 min treadmill from 16:00, no insulin adjustment. Plasma glucose ≤60 mg/dL (3.3 mmol/L), 22:00-06:00 | 21/50 (42%) | 8/50 (16%) | 0.009 |
| T1DEXI, Bisno 2026 | Real-world cohort, 496 adults, 12,340 nights. CGM 54-69 mg/dL (3.0-3.8 mmol/L) for ≥15 min, 00:00-06:00 | 15.6% | 13.1% | 0.001 |
| T1DEXIP, Sherr 2024 | Real-world, 251 adolescents, 3,319 activities | 14% of nights; 17% when activity ≥60 min/day | 12%; 8% when <60 min/day | 0.01 |
| Campbell 2015 | Crossover, n=10 men on MDI, 45 min running at 70% VO2peak at 18:00 | 9/10 on unchanged basal | 0/10 on 20% reduced basal | not stated |

The two headline figures disagree by a wide margin and the reason is measurement rather than
biology. DirecNet measured venous glucose in an inpatient setting after a standardised bout
with no insulin adjustment, and found roughly one exercise night in two affected. T1DEXI
measured free-living nights in adults who were adjusting insulin and food, and found a
difference of 2.5 percentage points on an already high background rate. The tool treats the
DirecNet figure as the unadjusted worst case and the T1DEXI figure as residual risk in someone
already managing.

By insulin modality in T1DEXI, level 1 / level 2 nocturnal hypoglycaemia: hybrid closed loop
9.7% / 3.2%, standard pump 20.3% / 7.2%, MDI 17.3% / 5.8%, both p<0.001.

### A2. Timing: the biphasic pattern

| Source | Design | Finding |
|---|---|---|
| McMahon 2007, JCEM 92:963 | Euglycaemic clamp, n=9 adolescents, 45 min afternoon exercise at 95% of lactate threshold | Glucose infusion rate rose biphasically: during and immediately after, then a second separate peak 7 to 11 h later. Plasma insulin matched between arms |
| Davey 2013, JCEM 98:2908 | Same method, n=10, 45 min at midday, 17 h of clamp | Infusion rate rose more than threefold during exercise (9.8 ± 1.4 to 30.6 ± 4.7 g/h), fell in the first recovery hour, stayed elevated to 11 h, no second peak. The biphasic pattern is specific to late-afternoon exercise |
| EASD/ISPAD 2020 | Expert opinion, grade D | Hypoglycaemia typically occurs 6 to 15 h after exercise, and risk may remain longer |
| ISPAD 2022 | Consensus | Afternoon exercise at both low and high intensity carries delayed nocturnal risk, frequently 7 to 11 h later |
| Campbell 2015 | Crossover, n=10 | Arms were similar until 6 h post-exercise, then diverged |

Two windows exist after late-afternoon or evening exercise: 0 to about 2 h, and a delayed
window centred on 7 to 11 h, which for a 16:00 to 17:00 session falls between about 23:00 and
04:00. Midday exercise produces a single continuous elevation lasting about 11 h with no
separate late peak, which is why ISPAD does not ask for an overnight adjustment after a
45-minute lunchtime session.

### A3. Duration of raised insulin sensitivity

The 24 to 48 h figure quoted by Riddell 2017 and graded A by ISPAD 2022 is a physiological
statement, not a trial endpoint. No clamp study in type 1 diabetes has measured insulin
sensitivity out to 48 h after a single bout; the 48 h end of the range is extrapolated from
muscle glycogen work in people without diabetes. The trial-derived durations are 24 h of
protection needed (Campbell 2015) and events clustering at 15 to 24 h (Gomez 2015, n=35).

### A4. Overnight basal reduction

| Source | Intervention | Design | Result |
|---|---|---|---|
| Taplin 2010, J Pediatr 157:784 | 20% basal reduction for 6 h from bedtime | Randomised, n=16 young people on pumps, after 60 min exercise | Overnight nadir 172 mg/dL (9.6 mmol/L) vs 127 mg/dL (7.1 mmol/L) control, p=0.042. Fewer readings below 80 and 70 mg/dL, more at or above 250 mg/dL (13.9 mmol/L) |
| Campbell 2015 | 20% of total daily basal on the exercise day, with a 75% reduced pre-exercise bolus, 50% reduced post-exercise bolus and a low-GI bedtime snack | Crossover, n=10 men on MDI | 9/10 hypoglycaemic on 100% basal, 0/10 on 80%, protection maintained 24 h, no hyperglycaemia |
| Sherr 2013, Diabetes Care 36:2909 | Overnight closed loop | Inpatient crossover, n=12 | Delivered about 20% less insulin between 22:00 and 02:00 on post-exercise nights, p=0.008 |

Every guideline converges on 20% for 6 h from bedtime: Riddell 2017, EASD/ISPAD 2020 (grade D),
ISPAD 2022, Diabetes Canada 2018 (grade B level 2, bedtime to 03:00), ADA 2016. ISPAD adds 40%
for 6 h when pre-exercise glucose was below 5.0 mmol/L (90 mg/dL) and no reduction when it was
above 15.0 mmol/L (270 mg/dL). The 40% figure has no trial behind it.

For MDI, Zaharieva and Riddell 2017 give 20 to 30% off the long-acting analogue for an unusually
active day, with a further 10 to 20% off the bedtime dose after prolonged aerobic activity.

The whole evidence base for the 20% figure is 16 young people on pumps and 10 adult men on MDI.

### A5. Bedtime snacks

| Study | Design | Result |
|---|---|---|
| Kalergis 2003, Diabetes Care 26:9 | Randomised placebo-controlled crossover, n=15 adults on lispro plus bedtime NPH, 50 nights, hourly IV sampling. Not an exercise study | 10 of 14 episodes occurred with no snack, p<0.001. Standard and protein snacks produced no nocturnal hypoglycaemia at any bedtime glucose, p<0.001. Above 10 mmol/L (180 mg/dL) no snack was needed but 46% of morning hyperglycaemia was associated with it |
| Raju 2006, JCEM 91:2087 | Randomised crossover, n=21 adults, five conditions. Not an exercise study | Neither a snack, with or without acarbose, nor cornstarch raised the mean nadir or reduced the number of low values. Terbutaline raised the nadir from 75 ± 9 to 127 ± 11 mg/dL, p<0.001, at the cost of morning hyperglycaemia |
| Campbell 2014, Diabetes Care 37:1845 | Crossover, n=10 men, evening exercise, low- vs high-GI meal and snack at 0.4 g carbohydrate per kg body mass | Low GI protected for about 8 h only. Nocturnal hypoglycaemia was identical, 5 of 10 in each arm. High GI produced hyperglycaemia and raised TNF-alpha and IL-6 |
| Paramalingam 2023, Nutrients 15:543 | Clamp pilot, n=6, 50 g protein at 20:00 after 16:00 exercise | Glucose infusion rate 0.27 ± 0.43 vs 1.60 ± 0.66 mg/kg/min during the risk period, p=0.028. The authors state 50 g may be excessive |
| Desjardins 2014, Diabetes Obes Metab 16:577 | Narrative review, 16 studies | Evidence was low. No evidence for people on analogue MDI or pump therapy. A bedtime snack cannot be recommended systematically but may help if individualised, with prior physical activity named as a justifying situation |
| Desjardins 2014, DRCP 106:420 | Observational, n=100 adults, 282 nights | With a rapid-acting bolus, each 5 g of post-dinner carbohydrate raised the odds of nocturnal hypoglycaemia, OR 1.16 (95% CI 1.04-1.29), p=0.008. Without a bolus, each 2 g of protein lowered them, OR 0.88 (0.78-1.00), p=0.048 |

The ISPAD rule of 0.4 g/kg of low- to medium-GI carbohydrate below 10.0 mmol/L (180 mg/dL) plus
15 g protein below 7.0 mmol/L (126 mg/dL) traces to Campbell for the 0.4 g/kg and to Kalergis
for the thresholds. Kalergis predates analogue basal insulin and neither study was in children.
The strongest negative result is Raju: a conventional snack did not prevent nocturnal
hypoglycaemia at all. A snack without an insulin reduction does not eliminate post-exercise
nocturnal hypoglycaemia, and the tool says so rather than recommending one alone.

DirecNet's finding matters more than any threshold: the pre-bed glucose level that is safe on a
sedentary night does not transfer to a post-exercise night, where hypoglycaemia occurred
fairly frequently even above 130 mg/dL (7.2 mmol/L). A rule keyed on bedtime glucose alone
under-predicts risk after afternoon exercise.

### A6. Time of day

| Source | Finding |
|---|---|
| Gomez 2015, JDST 9:619 | Crossover, n=35 adults on sensor-augmented pumps. 5.6 events per person after morning exercise vs 10.7 after afternoon, incidence rate ratio 0.52 (95% CI 0.43-0.63), p<0.0001 |
| Zivkovic 2026, Diabetologia 69:1457 | Observational, 3,248 adults, 428,058 sessions. Sessions after 15:30 did not raise nocturnal risk relative to earlier ones, +0.9 ± 0.34%, p<0.01. Intensity mattered more than timing |
| T1DEXIP, Sherr 2024 | 251 adolescents. Duration drove risk, not time of day |

The observational evidence is split, so the tool treats exercising earlier in the day as a
weakly supported preference rather than a rule, and keys the overnight adjustment on duration
and intensity instead. No guideline advises avoiding evening exercise and none specifies a
minimum gap between a session and bedtime.

### A7. Antecedent hypoglycaemia blunts the response to exercise

| Study | Design | Finding |
|---|---|---|
| Davis 2000, Diabetes 49:73 | n=16 without diabetes. Two 2 h clamps at 2.9 mmol/L (52 mg/dL) on day 1, then 90 min cycling on day 2 | Falls in insulin and rises in adrenaline, noradrenaline, glucagon, growth hormone and cortisol were all blunted, p<0.01. Glucose infusion needed during exercise 8.8 ± 2.2 vs 0.6 ± 0.6 µmol/kg/min, p<0.01. By 90 min the entire exercise-induced increment in endogenous glucose production had been abolished |
| Galassetti 2003, Diabetes 52:1761 | n=16 adults with type 1 diabetes | The glucagon response to exercise was abolished. Other responses reduced by 40 to 80%. Exogenous glucose needed tripled |
| Galassetti 2006, AJP 290:E1109 | n=22, antecedent nadirs of 3.9, 3.3 or 2.8 mmol/L (70, 59, 50 mg/dL) | Blunting was graded by depth of the antecedent low and was detectable from a nadir of only 3.9 mmol/L (70 mg/dL) |
| Sandoval 2004, Diabetes 53:1798 | n=27 with type 1 diabetes, prior exercise at 30% or 50% VO2max, then a hypoglycaemic clamp | Adrenaline 1,959 ± 553 and 1,528 ± 424 vs 3,420 ± 424 pmol/L in controls, p<0.05. Symptoms lower in both exercise groups. Low-intensity exercise at 30% VO2max blunted counterregulation as much as moderate exercise |

T1DEXI corroborates this in the field: time below range at or above 4% in the preceding 24 h
raised level 1 nocturnal hypoglycaemia from 11.7% to 22.9% of nights and level 2 from 3.3% to
10.2%, both p<0.001.

This is the strongest lever available to an engine that has CGM history. Recent time below
range predicts post-exercise nocturnal hypoglycaemia about as strongly as the exercise itself,
and the mechanism is documented at the level of hormone concentrations. The tool computes time
below range over the 24 h before each session and reports it alongside every recommendation.

Guideline translation: severe hypoglycaemia within the previous 24 h is a contraindication to
exercise (Riddell 2017; ISPAD 2022 grade C, which extends it to recurrent antecedent
hypoglycaemia). EXTOD adds that after a self-treated episode one should wait 45 to 60 min after
glucose has stabilised.

## Part B. Pre-exercise thresholds

### B1. Riddell 2017 consensus, Table 1

| Band | mmol/L | mg/dL | Recommendation |
|---|---|---|---|
| Below target | <5.0 | <90 | Ingest 10 to 20 g of glucose before starting. Delay until above 5 mmol/L and monitor closely |
| Near target | 5.0-6.9 | 90-124 | Ingest 10 g of glucose before aerobic exercise. Anaerobic exercise and HIIT can be started |
| Target | 7.0-10.0 | 126-180 | Aerobic exercise can be started. Anaerobic and HIIT can be started but glucose may rise |
| Slightly above | 10.1-15.0 | 182-270 | Aerobic exercise can be started. Anaerobic can be started but glucose may rise |
| Above target | >15.0 | >270 | If unexplained, check blood ketones. Up to 1.4 mmol/L: light intensity only, under 30 min, a small corrective dose may be needed. At or above 1.5 mmol/L: contraindicated. Below 0.6 mmol/L or urine ketones under 2+: mild to moderate aerobic exercise may start |

The consensus threshold for the hyperglycaemia band is 15.0 mmol/L (270 mg/dL), not 13.9 mmol/L
(250 mg/dL). Blood ketones at or above 3.0 mmol/L should be managed immediately by a clinician.

### B2. Where the guidelines disagree

| Question | Riddell 2017 | ISPAD 2022 | EASD/ISPAD 2020 | ADA 2016 | Diabetes Canada | EXTOD |
|---|---|---|---|---|---|---|
| Glucose triggering a ketone check | >15.0 mmol/L (270) | >15.0 (270) | >15.0 (270) | 13.9 (250) | 16.7 (300) and unwell | >15.0 (270) |
| Ketones 0.6-1.4 mmol/L | Light intensity under 30 min permitted | Postpone; half correction or 0.05 U/kg. Its own tables allow a 15 min wait at 0.6-1.0 and 60 min at 1.1-1.4 | Address before exercise | not itemised | not itemised | Below 1.5: proceed with adjustment |
| Correction fraction when hyperglycaemic | "a small corrective dose" | 50% | 50% | not itemised | not itemised | 30% |
| Lower bound to start | 5.0 mmol/L (90) | 5.0 (90) after treating, floor 3.0 (54) | 5.0 (90), do not restart below 3.0 (54) | 90 mg/dL with 15-30 g | not itemised | 3.9 (70) |

Two of these are internal contradictions rather than disagreements between documents. ISPAD's
graded recommendation B says to postpone for any ketone level 0.6 to 1.4 mmol/L, while its own
Tables 4 and 5 give a 15-minute and a 60-minute wait for the two halves of that band. The tool
implements the more conservative reading and shows both.

The tool uses 15.0 mmol/L (270 mg/dL) as the ketone-check threshold, since that is the value in
the three most recent and most exercise-specific documents. I found no current guideline using
16.7 mmol/L (300 mg/dL) as a bar to exercising; in Diabetes Canada it is a trigger to test
ketones when the person also feels unwell.

### B3. EASD/ISPAD risk stratification

Three groups by exercise frequency (sessions of 45 min or more per week) and hypoglycaemia
risk, assessed from an awareness score, then time below 3.9 mmol/L (70 mg/dL) over 3 months,
then whether a severe event occurred in the last 6 months.

| Phase | Low risk | Moderate | High |
|---|---|---|---|
| Adults, carbohydrate threshold before exercise | <7.0 mmol/L (126 mg/dL) | <8.0 (145) | <9.0 (161) |
| Children 6 to under 18, pre-exercise target | 7.0-10.0 mmol/L (126-180) | 8.0-11.0 (145-198) | 9.0-12.0 (162-216) |
| During exercise | 5.0-10.0 mmol/L (90-180), ideally 7.0-10.0 | slightly higher | higher |
| First 90 min after, lower limit | 4.4 mmol/L (80 mg/dL) | 5.0 (90) | 5.6 (100) |
| Overnight alert after evening exercise | 4.4 mmol/L (80 mg/dL) | higher | higher |

Each step up the risk ladder shifts every threshold by about 1.0 to 2.0 mmol/L (18 to 36 mg/dL).

Fixed thresholds independent of risk group: suspend exercise below 3.9 mmol/L (70 mg/dL);
restart near 4.4 mmol/L (80 mg/dL) with a level or rising arrow, 5.0 mmol/L (90 mg/dL) for
children; do not restart below 3.0 mmol/L (54 mg/dL); treat immediately if a predictive alert
forecasts below 3.0 mmol/L.

The low alert at exercise onset is set to 5.6 mmol/L (100 mg/dL), the highest available. The
statement gives the reason explicitly: it is in line with the expected delay between
interstitial and blood glucose when levels are falling during prolonged exercise.

### B4. Trend arrows

Rate-of-change bands, from ISPAD 2022 Table 7.

| Arrow | Change per 15 min | Rate |
|---|---|---|
| Double up | >45 mg/dL (2.5 mmol/L) | >3.0 mg/dL/min (0.167 mmol/L/min) |
| Single up | 30-45 mg/dL (1.7-2.5 mmol/L) | 2.0-3.0 mg/dL/min |
| Angled up | 15-30 mg/dL (0.8-1.7 mmol/L) | 1.0-2.0 mg/dL/min |
| Flat | <15 mg/dL (0.8 mmol/L) | <1.0 mg/dL/min |
| Angled down | 15-30 mg/dL | 1.0-2.0 mg/dL/min |
| Single down | 30-45 mg/dL | 2.0-3.0 mg/dL/min |
| Double down | >45 mg/dL | >3.0 mg/dL/min |

Abbott and Senseonics do not use the double arrows and their single arrow covers everything
above 30 mg/dL per 15 min.

Carbohydrate by arrow, EASD/ISPAD 2020, adults at low risk:

| Phase | Threshold | Flat | Angled down | Down |
|---|---|---|---|---|
| During exercise | 7.0 mmol/L (126 mg/dL) | 10-15 g | 15-25 g immediately | 20-35 g |
| First 90 min after | 4.4 mmol/L (80 mg/dL) or higher by risk | about 10 g | 15 g | individualised |
| Overnight after evening exercise | 4.4 mmol/L (80 mg/dL) or higher by risk | about 10 g | 15 g | individualised |

Repeat every 15 to 20 min at the lower threshold. Expect up to 20 min before the arrow responds
to oral carbohydrate. These recommendations are stated not to apply to hybrid closed-loop
systems.

ISPAD 2022 Table 5, children and adolescents, g/kg body mass per 20 min, capped at 60 kg body
weight, given as regular insulin on board / less insulin on board:

| Sensor glucose | Up | Angled up | Flat | Angled down | Down |
|---|---|---|---|---|---|
| 10.1-15.0 mmol/L (181-270) | 0 / 0 | 0 / 0 | 0 / 0 | 0.1 / 0 | 0.2 / 0 |
| 7.0-10.0 mmol/L (126-180) | 0 / 0 | 0.1 / 0 | 0.2 / 0 | 0.3 / 0.1 | 0.4 / 0.2 |
| 5.0-6.9 mmol/L (90-125) | 0.1 / 0 | 0.2 / 0.1 | 0.3 / 0.2 | 0.4 / 0.3 | 0.5 / 0.4 |
| 4.0-4.9 mmol/L (70-89), delay 20 min | 0.2 / 0.1 | 0.3 / 0.2 | 0.3 / 0.3 | 0.4 / 0.4 | 0.5 / 0.5 |
| 3.0-3.9 mmol/L (54-70) | treat and delay until above 4.9 mmol/L (89 mg/dL) | | | | |
| <3.0 mmol/L (54) | treat, do not start | | | | |

The 60 kg cap exists because peak exogenous carbohydrate oxidation is 1.0 to 1.2 g/min and the
table would otherwise exceed it. Above the 91st BMI centile, ideal body weight is used, taken as
BMI at the 50th centile for age multiplied by height in metres squared, unless the centile
reflects muscle mass.

Note the mismatch the tool has to reconcile: Riddell and EASD/ISPAD give absolute grams, ISPAD
gives grams per kilogram with a cap. For a 30 kg child ISPAD's 0.3 g/kg gives 9 g, close to
Riddell's 10 g. For a 90 kg adult the cap binds at 60 kg and gives 18 g, well below the 20 to
35 g EASD/ISPAD recommends with a falling arrow. The tool shows both and names which is which.

### B5. CGM accuracy during exercise

| Study | Device, n | MARD during exercise | Lag |
|---|---|---|---|
| Zaharieva 2019, DTT 21:313 | Dexcom G4/G5, n=17, 60 min aerobic | 13% (IQR 6-22) | 12 ± 11 min |
| Li 2019, DTT 21:286 | Dexcom G4, n=17 on MDI, 25 min fasted HIIT | 17.8% vs 10.4% pre-exercise, p<0.001 | 35 min to half-maximal rise. Negative bias 35.3 mg/dL (2.0 mmol/L), p<0.001. Only 65.5% of paired values in the no-risk zone |
| Guillot 2020, Biosensors 10:138 | Dexcom G6, n=24 | Aerobic 8.9-13.9%, resistance 7.7-14.5%, HIIT 12.1-16.8% | Median 13 min; 1 min aerobic, 18 min resistance, 19 min HIIT |
| Moser 2019, Diabet Med 36:606 | FreeStyle Libre, n=10, 845 paired values | Median 22% overall; 36.3% in hypoglycaemia | worse on full basal dose |
| Lundemose 2023, Sensors 23:9256 | G6, Guardian 4, Libre 2, n=13 | 12.6%, 10.7%, 17.2%, p=0.31 | Rate error grid zone A+B during exercise 100%, 93.0%, 73.3%, p=0.0003 |

EASD/ISPAD's pooled figure is a MARD of about 13.63% (95% CI 11.41 to 15.84) across exercise
types, with lag lengthening from about 5 min at rest to 12 to 24 min during exercise.

No published rule converts a lag in minutes into a glucose offset. Taking a fall rate at the
single-down boundary of 2 mg/dL/min and a lag of 12 to 24 min implies true glucose is roughly
24 to 48 mg/dL (1.3 to 2.7 mmol/L) below the displayed value while falling fast, which is the
same order as Li's measured 35.3 mg/dL bias and as the raised 5.6 mmol/L alert. That derivation
is not published and the tool labels it as an inference wherever it uses it.

No exercise-specific validation study of Dexcom G7 or FreeStyle Libre 3 was found.

## Citations

Tsalikian E et al. J Pediatr 2005;147:528-534. PMID 16227041.
DirecNet Study Group. Diabetes Care 2006;29:2200-2204. PMID 17003293.
McMahon SK et al. J Clin Endocrinol Metab 2007;92:963-968. PMID 17118993.
Davey RJ et al. J Clin Endocrinol Metab 2013;98:2908-2914. PMID 23780373.
Maran A et al. Diabetes Technol Ther 2010;12:763-768. PMID 20807120.
Taplin CE et al. J Pediatr 2010;157:784-788. PMID 20650471.
Campbell MD et al. BMJ Open Diabetes Res Care 2015;3:e000085. PMID 26019878.
Campbell MD et al. Diabetes Care 2014;37:1845-1853. PMID 24784832.
Kalergis M et al. Diabetes Care 2003;26:9-15. PMID 12502652.
Raju B et al. J Clin Endocrinol Metab 2006;91:2087-2092. PMID 16492699.
Desjardins K et al. Diabetes Obes Metab 2014;16:577-587. PMID 24320159.
Desjardins K et al. Diabetes Res Clin Pract 2014;106:420-427. PMID 25451901.
Paramalingam N et al. Nutrients 2023;15:543. PMID 36771250.
Gomez AM et al. J Diabetes Sci Technol 2015;9:619-624. PMID 25555390.
Sherr JL et al. Diabetes Care 2013;36:2909-2914. PMID 23757427.
Sherr JL et al. Diabetes Care 2024;47:849-857. PMID 38412033.
Bisno DI et al. Diabetes Care 2026;49:1404-1413. PMID 42247270.
Riddell MC et al. Diabetes Care 2023;46:704-713. PMID 36795053.
Zivkovic J et al. Diabetologia 2026;69:1457-1467. PMID 41686193.
Davis SN et al. Diabetes 2000;49:73-81. PMID 10615952.
Galassetti P et al. Diabetes 2003;52:1761-1769. PMID 12829644.
Galassetti P et al. Am J Physiol Endocrinol Metab 2006;290:E1109-E1117. PMID 16403779.
Sandoval DA et al. Diabetes 2004;53:1798-1806. PMID 15220204.
Riddell MC et al. Lancet Diabetes Endocrinol 2017;5:377-390. PMID 28126459.
Moser O et al. Diabetologia 2020;63:2501-2520. PMID 33047481.
Adolfsson P et al. Pediatr Diabetes 2022;23:1341-1372. PMID 36537529.
Colberg SR et al. Diabetes Care 2016;39:2065-2079. PMID 27926890.
Diabetes Canada. Can J Diabetes 2018;42(Suppl 1):S54-S63.
Zaharieva DP, Riddell MC. Can J Diabetes 2017;41:507-516.
Zaharieva DP et al. Diabetes Technol Ther 2019;21:313-321. PMID 31059282.
Li A et al. Diabetes Technol Ther 2019;21:286-294. PMID 31017497.
Guillot FH et al. Biosensors 2020;10:138. PMID 33003524.
Moser O et al. Diabet Med 2019;36:606-611. PMID 30677187.
Maytham K et al. Front Endocrinol 2024;15:1352829. PMID 38686202.
Lundemose SB et al. Sensors 2023;23:9256. PMID 38005642.
