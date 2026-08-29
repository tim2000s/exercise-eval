# Insulin adjustment for exercise

Specification for the insulin rules. Conversions use 18.0182 mg/dL per mmol/L except where a
source printed both units, in which case the source's own pair is quoted.

Two findings here changed the design of the tool rather than merely adding numbers to it. A
bolus reduction does not slow the fall in glucose during exercise; it raises the level the fall
starts from. And a basal reduction has almost no effect on circulating insulin within the first
hour, so lead time is not a refinement but the whole mechanism.

## 1. Pre-exercise bolus reduction

Rabasa-Lhoret R, Bourque J, Ducros F, Chiasson JL. Diabetes Care 2001;24:625-630.

Eight men on ultralente plus lispro, six per exercise arm, five completing every protocol, 60
metabolic experiments. Age 33.0 ± 3.1 years, BMI 23.4 ± 0.6, HbA1c 6.1 percent, VO2max 37.8 ±
3.5 mL/kg/min. Women were excluded because of the effect of menstrual cyclicity on glucose
homeostasis, so the table below was derived entirely in men. Lispro was injected immediately
before a 600 kcal breakfast containing 75 g of carbohydrate, and cycling began 90 minutes after
the meal started.

The published guidance, Table 1 of that paper:

| Intensity | 30 min of exercise | 60 min of exercise |
|---|---|---|
| 25 percent VO2max | −25 percent (extrapolated, not tested) | −50 percent |
| 50 percent VO2max | −50 percent | −75 percent |
| 75 percent VO2max | −75 percent | not assessed |

Only four of the six cells were tested. The paper marks the 25 percent, 30 minute cell with an
asterisk as extrapolated. Downstream reproductions, including Riddell 2017 Table 5, carry that
cell without the asterisk, and Riddell adds a row for intensities above 80 percent VO2max where
no reduction is recommended. The tool keeps the distinction and says which cells were measured.

The measured outcomes, as change from the pre-meal baseline at the end of exercise:

| Intensity | Duration | Bolus | Fall during exercise, mmol/L | Glucose at end vs baseline, mmol/L |
|---|---|---|---|---|
| 25 percent | 60 min | 100 percent | 2.95 ± 0.66 | −2.90 ± 1.13 |
| 25 percent | 60 min | 50 percent | 3.25 ± 0.52, not different | −0.62 ± 0.93 |
| 50 percent | 30 min | 100 percent | 3.36 ± 0.76 | −2.05 ± 0.67 |
| 50 percent | 30 min | 50 percent | 2.26 ± 0.54, p=0.08 | −0.39 ± 1.26 |
| 50 percent | 60 min | 100 percent | arm abandoned | 3 of 4 needed intravenous dextrose |
| 50 percent | 60 min | 50 percent | 4.18 ± 0.57 | −2.68 ± 0.59 |
| 50 percent | 60 min | 25 percent | 3.08 ± 0.53, not different | +0.49 ± 0.5, p<0.05 vs 50 percent |
| 75 percent | 30 min | 100 percent | 3.0 ± 0.71 | −2.94 ± 0.59 |
| 75 percent | 30 min | 25 percent | 2.7 ± 0.38, not different | +0.71 ± 1.09, p<0.05 |

The mechanism is the column that is usually left out. In every comparison the fall during
exercise was statistically indistinguishable between the full and the reduced dose. What the
reduction changed was the starting point: glucose was higher when exercise began, so the same
fall landed somewhere safer. A recommendation engine should therefore model a bolus reduction as
a shift in the pre-exercise level, not as an attenuation of the exercise-induced slope.

More than two thirds of the total fall at 25 percent VO2max occurred in the first 30 minutes of
a 60 minute bout, so the fall is front-loaded rather than linear.

The abandoned arm is the single most informative row. An hour at half of VO2max on a full
breakfast bolus sent three of four participants to intravenous dextrose, and the fourth finished
at 3.5 mmol/L. That is why the tool treats a full bolus within three hours of a session of that
shape as a finding rather than a note.

Dose reduction cut hypoglycaemia from 64 to 16 episodes per 100 exercising sessions, a 75
percent reduction, which the authors note is an underestimate because the worst arm was stopped
early. Only four of the 24 minor episodes occurred during exercise itself, all in the 50 percent
VO2max, 60 minute arm at full bolus. Hypoglycaemia after exercise still occurred despite an
appropriate reduction.

The cost of reducing is postprandial hyperglycaemia: mean excursion 1.1 ± 0.56 mmol/L at full
dose, 2.1 ± 0.7 at half, 3.6 ± 0.6 at a quarter.

## 2. Insulin on board, and the dose-response

Riddell MC et al. T1DEXI. Diabetes Care 2023;46:704-713. Real-world structured sessions in 497
adults, age 37 ± 14 years, HbA1c 6.6 ± 0.8 percent, 45 percent using closed loop.

| Insulin on board at start | Participants / sessions | Baseline glucose | Change during exercise | Adjusted change (95% CI) |
|---|---|---|---|---|
| 0 U | 294 / 568 | 136 mg/dL (7.6 mmol/L) | +2 ± 29 mg/dL | −2 (−5 to 1) mg/dL |
| above 0 to under 1.0 U | 318 / 631 | 138 mg/dL (7.7) | −6 ± 29 | −10 (−13 to −7) |
| 1.0 to under 2.0 U | 304 / 523 | 149 mg/dL (8.3) | −15 ± 35 | −16 (−19 to −13) |
| 2.0 U or more | 351 / 891 | 167 mg/dL (9.3) | −29 ± 39 | −26 (−28 to −23) |

Overall p<0.001. This is the cleanest published gradient linking insulin on board to the size of
the fall, and it is measured in the free-living setting the tool works in rather than in a
laboratory. A session started with no insulin on board did not fall at all.

Francescato 2004 gives the same relationship from the other direction, as the carbohydrate
needed to prevent hypoglycaemia at a fixed workload: 0.63 ± 0.30 g/kg at 1 h after the dose,
0.44 ± 0.32 at 2.5 h, 0.28 ± 0.24 at 4 h and 0.14 ± 0.18 at 5.5 h. Requirement correlated with
plasma insulin (r=0.739, p<0.001) and not with fitness.

ISPAD states the same distinction as a rule: 0.5 to 1.0 g/kg/h of carbohydrate with bolus
insulin on board, against 0.3 to 0.5 g/kg/h more than two hours after a bolus.

## 3. Lead time for a basal reduction

This is where the guidelines and the trials diverge most sharply, and the trials are the ones
that measured insulin.

| Study | Design | Finding |
|---|---|---|
| McAuley 2016, Diabetologia 59:1636 | n=14 adults on pumps, fasted, basal halved 60 min before 30 min of cycling, venous sampling every 15 min | Free insulin fell 4.9 ± 2.9 percent at 1 h, 16.2 ± 2.6 percent at 2 h, 18.6 ± 3.2 percent at 3 h. The fall reached significance only after 75 minutes. Their conclusion: halving the basal rate one hour before exercise did not significantly reduce circulating free insulin by the time exercise began |
| Roy-Fleming 2019, Diabetes Metab 45:294 | n=22 adults, 80 percent basal reduction at 40, 20 or 0 min before 45 min at 60 percent VO2peak, 3 h after lunch | Time below 4.0 mmol/L 16 ± 25, 26 ± 27, 24 ± 29 percent. No significant difference. Needing carbohydrate during exercise: 6 (27 percent), 12 (55 percent), 11 (50 percent). Forty minutes of lead time is insufficient |
| Zaharieva 2019, Diabetes Care 42:824 | n=17 adults on pumps, no insulin on board at onset, 60 min treadmill at about 50 percent VO2peak | 80 percent reduction at −90 min: fall −31 ± 58 mg/dL, 1 of 17 hypoglycaemic. 50 percent at −90 min: −47 ± 50 mg/dL, 1 of 17. Pump suspension at onset: −67 ± 41 mg/dL, 7 of 17 (41 percent), p<0.05 |
| Heinemann 2009, Diabetes Care 32:1437 | Euglycaemic clamp, n=10 men | Insulinaemia began to change 15 to 30 min after a basal rate change; glucose consumption 30 to 60 min after. Two and a half to four hours were needed for a new steady-state metabolic effect |
| McAuley 2017, Diabet Med 34:1158 | n=12 adults, 0.2 U/h change, sampling to 300 min | An increase reached 80 percent of steady state in 170 min. A reduction did not reach 80 percent within 300 min. First significant difference at 180 min for an increase and 300 min for a reduction |

The asymmetry in the last row is the part that matters most for a closed loop. An algorithm can
raise circulating insulin substantially faster than it can lower it.

A second complication runs the other way. Exercise itself transiently raises plasma insulin,
because absorption from the subcutaneous depot accelerates. McAuley measured +6 ± 2 pmol/L at 15
minutes and +5 ± 2 pmol/L at 30 minutes relative to rest, p<0.001, and Franc 2015 measured
+7.8 ± 2.6 µU/mL between 0 and 30 minutes against rest, p=0.004, in every arm including the one
where the pump was stopped. A suspension at exercise onset therefore produces a smaller and
later fall in insulin than its nominal 100 percent reduction implies.

Taken together: nothing shorter than 60 minutes of lead time has shown a hypoglycaemia benefit
in any randomised comparison, 90 minutes works, and no trial has directly compared 60 against
90. The guidelines give 60 to 90 minutes (Riddell 2017), 30 to 60 (ADA 2016) and 90 to 120
(ISPAD 2022, EASD/ISPAD 2025). The tool uses 90 minutes as the figure with trial support and
names the disagreement.

## 4. Pump suspension at exercise onset

DirecNet, Tsalikian 2006, Diabetes Care 29:2200. Forty-nine children and adolescents aged 8 to
17 on pumps, two 75 minute afternoon sessions, pump off at exercise start and restarted 45
minutes afterwards, about 2 hours in total. The last bolus was roughly 4 hours earlier, so the
rapid-acting depot was small and the effect is attributable to stopping basal.

| Outcome | Basal continued | Basal stopped | p |
|---|---|---|---|
| Glucose fall | 63 ± 33 mg/dL (3.5 mmol/L) | 44 ± 38 mg/dL (2.4 mmol/L) | <0.001 |
| Relative fall | 41 ± 19 percent | 28 ± 23 percent | <0.001 |
| Hypoglycaemia at or below 70 mg/dL during exercise | 21 (43 percent) | 8 (16 percent) | 0.003 |
| Hypoglycaemia during or after | 25 (51 percent) | 8 (16 percent) | <0.001 |
| Hyperglycaemia during or after | 3 (6 percent) | 13 (27 percent) | 0.008 |

Suspension halves the hypoglycaemia and quadruples the hyperglycaemia. Blood ketones stayed at
or below 0.4 mmol/L in every session, so the ketone concern with a two-hour suspension was not
realised here.

Admon 2005 is the counterweight: in ten young people cycling two hours after a bolus, pump off
against pump at 50 percent made no measurable difference, and late hypoglycaemia over 24 hours
was more common than hypoglycaemia during exercise.

Riddell 2017 recommends reducing rather than suspending where practical, and caps a suspension
at under two hours on pharmacokinetic grounds. ISPAD caps it at 90 minutes for children, with
about 50 percent of the usual hourly delivery given if disconnection runs longer.

## 5. Overnight and post-exercise

Campbell 2013, Diabetes Care 36:2217. Eleven men, a 75 percent reduced breakfast bolus then 45
minutes of running at 72.5 percent VO2peak, with the post-exercise lunch bolus randomised to
full, 75 percent or 50 percent.

| Outcome | Full | 75 percent | 50 percent |
|---|---|---|---|
| Peak serum insulin after the meal, pmol/L | 229 ± 44 | 196 ± 42 | 83 ± 29 |
| Participants with hypoglycaemia after the meal | 5 | 2 | 0 |
| Total episodes after the meal | 9 | 6 | 0 |

The 50 percent arm prevented hypoglycaemia for a further four hours, pushing the first episode
to eight hours post-exercise. Beyond nine hours the three arms were comparable. Across all
trials, 82 percent of hypoglycaemic episodes were nocturnal.

Campbell 2015 stacked four adjustments together and randomised only the basal: 80 percent basal
across the day, a 75 percent reduced pre-exercise bolus, a 50 percent reduced post-exercise
bolus and a low glycaemic index bedtime snack. Nine of ten had nocturnal hypoglycaemia on full
basal and none of ten on 80 percent. Because only the basal was randomised, the contributions of
the other three cannot be separated from that trial.

Taplin 2010 is the source of the 20 percent overnight figure. The authors report the trial was
underpowered for the hypoglycaemia rate: the control rate was 12.5 percent against the 48
percent assumed from DirecNet, because the pump was disconnected during exercise and run at 50
percent for 45 minutes afterwards in every arm. The 20 percent figure therefore rests on a
significant difference in nadir and on hypoglycaemia counts that were not powered.

## 6. Automated insulin delivery

### 6.1 What each system does

| System | Exercise target | Lead time as the manufacturer states it | Duration | Auto-correction during the mode |
|---|---|---|---|---|
| MiniMed 780G | 150 mg/dL / 8.3 mmol/L | 1 to 2 hours | 30 min to 24 h | Suspended |
| MiniMed 670G and 770G | 150 mg/dL / 8.3 mmol/L | not stated | up to 12 h | The feature does not exist on these pumps |
| Tandem Control-IQ | 140 to 160 mg/dL / 7.8 to 8.9 mmol/L | not stated in any Tandem guide | 30 min to 8 h, or untimed | Still delivered, on the unchanged 180 mg/dL trigger |
| Omnipod 5 Activity | 150 mg/dL / 8.3 mmol/L | 30 to 60 min in the UK guide, none in the US guide | 1 to 24 h | No separate auto-correction exists |
| CamAPS FX Ease-off | not published | 60 to 90 minutes | 0 to 24 h | not stated |
| Diabeloop DBLG1 | target raised by 70 mg/dL / 3.9 mmol/L | at least 30 min, 1 to 2 h preferred | user-entered | modulated by an intensity and duration matrix |
| AndroidAPS Activity | 140 mg/dL / 7.8 mmol/L (app default) | 1 to 2 hours in the documentation | 90 min default | SMB delivery suppressed by default |

Three different lead times circulate for the Omnipod 5 Activity feature alone: none in the US
user guide, 30 to 60 minutes in the UK quick tips, and 1 to 2 hours in the EASD/ISPAD statement.
Tandem publishes no lead time at all. The 1 to 2 hour figure that appears everywhere is
consensus rather than a manufacturer instruction.

Two figures in circulation could not be verified in any manufacturer document and should not be
quoted as such: the roughly 50 percent reduction in delivery attributed to the Omnipod 5 Activity
feature, which is a review characterisation, and the numeric size of the CamAPS Ease-off target
elevation, which is not published.

### 6.2 Does announcing exercise help?

| Study | n | Timing relative to a meal | Time below range, announced vs not | p |
|---|---|---|---|---|
| Tagougui 2020, Diabetologia 63:2282 | 37 | 90 min after breakfast, active bolus | announced with 33 percent bolus reduction 2.0 ± 6.2 percent; announced with full bolus 7.0 ± 12.6; unannounced full bolus 13.0 ± 19.0 | <0.0001 and 0.005 |
| McCarthy 2023, DTT 25:476 | 10 | 90 min after a carbohydrate drink | target at −90 min 1.1 ± 1.9 percent; at −45 min 7.8 ± 10.3; at onset with full bolus 22.9 ± 22.2 | 0.029 |
| Turner 2025, Diabetes Care 48:1598 | 38 | at least 3 h postabsorptive | Activity at −60 min 4.5 ± 0.9 percent; at −30 min 4.3 ± 1.2; automated mode 6.1 ± 2.0 | 0.40 and 0.39 |
| Morrison 2025, Diabetes Obes Metab 27:5160 | 26 | at least 3 h post-meal | median 0 percent in all four arms, at −60, −20, 0 and no target | above 0.99 |

The pattern that separates them is prandial insulin on board, not announcement. Both trials with
a large effect placed exercise 90 minutes after a meal with an active bolus. Both null trials
placed it at least three hours after the last bolus, where the median time below range was
already zero. Raising the target changes only future automated delivery, which is a small lever
against a bolus already in the subcutaneous tissue.

Announcement reliably reduces insulin and raises the floor without reliably preventing events.
Turner is the clearest case: 0.29 U against 1.27 U delivered in the hour before, a nadir 9.5
mg/dL higher and a fall a quarter shallower, yet 29 percent against 42 percent still went below
70 mg/dL, which did not reach significance.

In Morrison, setting the target early before morning moderate exercise cost 15.7 percentage
points of time in range against not setting it at all, p=0.008, in a cohort whose median time
below range was zero. Announcing a session that was not going to cause a problem buys
hyperglycaemia.

### 6.3 How a closed loop can make things worse

The mechanism is stated as consensus in four separate documents and quantified by Turner. A
carbohydrate-heavy meal with a reduced bolus, or pre-exercise carbohydrate taken twenty minutes
or more before the start, raises glucose before exercise. The algorithm responds with extra
automated basal or a correction bolus. That insulin then peaks after the session has started.

Heise 2017 measured the timing for a pump-delivered bolus in 48 adults: peak plasma insulin at
82.3 minutes for aspart and 56.6 for faster aspart, and peak glucose-lowering effect at 130.6
and 111.9 minutes. A correction given at the start of a 45 minute run reaches its peak effect
after the run has finished.

ISPAD draws the practical conclusion and limits pre-exercise carbohydrate on a closed loop to
within 5 to 10 minutes of the start, rather than the 30 to 60 minutes recommended for someone
not on a closed loop.

No published trial was found in which a closed loop performed worse than open loop or a
sensor-augmented pump around exercise, and that should be stated plainly because the mechanism
is well described while the head-to-head outcome data do not support net harm. T1DEXI found
identical glucose changes across modalities (closed loop −14 ± 37, pump −13 ± 35, injections
−13 ± 34 mg/dL, p=0.80), and closed loop roughly halved nocturnal hypoglycaemia after exercise.
The failures are within-AID: the unannounced session with an active meal bolus.

### 6.4 AndroidAPS specifics

The app source is the authoritative set of defaults, and it disagrees with two of the
documentation pages.

| Temp target | App source | Preferences page | TempTargets page |
|---|---|---|---|
| Activity | 140 mg/dL / 7.8 mmol/L, 90 min | 140 mg/dL, 90 min | 8 mmol/L (144 mg/dL), 40 min |
| Eating soon | 90 mg/dL / 5.0 mmol/L, 45 min | 72 mg/dL / 4.0 mmol/L, 45 min | 5 mmol/L, 30 min |
| Hypo | 160 mg/dL / 8.9 mmol/L, 60 min | 125 mg/dL / 6.9 mmol/L, 45 min | 7 mmol/L, 30 min |

Where a high temp target changes the algorithm, the formula is, with a normal target of 100
mg/dL and a default half-basal exercise target of 160:

```
c = halfBasalTarget - 100
sensitivityRatio = c / (c + target - 100)
```

| Temp target | Sensitivity ratio | Basal as a percentage of profile | ISF multiplier |
|---|---|---|---|
| 120 mg/dL (6.7 mmol/L) | 0.75 | 75 | 1.33 |
| 140 mg/dL (7.8 mmol/L), the Activity default | 0.60 | 60 | 1.67 |
| 160 mg/dL (8.9 mmol/L) | 0.50 | 50 | 2.00 |
| 180 mg/dL (10.0 mmol/L) | 0.43 | 43 | 2.33 |

That only applies when the user has enabled `high_temptarget_raises_sensitivity`, which is off
by default. A stale comment in the source lists different values from a superseded formula.

Three behaviours fire without the user enabling anything, because of how AndroidAPS overrides
the oref defaults:

A temp target above 100 mg/dL disables super micro boluses, since `enableSMB_always` defaults to
true and `allowSMB_with_high_temptarget` to false. Setting the Activity target therefore switches
SMB delivery off and the loop falls back to temporary basal rates. Unannounced meal detection
continues to compute its predictions; only the microbolus delivery stops.

A temp target overrides autosens entirely for the sensitivity ratio, and suppresses the autosens
target adjustment. This is why the tool ignores `sensitivityRatio` for any interval covered by
an active temp target: under an exercise target it reflects the target, not the person.

The low-glucose-suspend threshold is derived from the target as `min_bg - 0.5 * (min_bg - 40)`.
At a normal target of 100 mg/dL that is 70 mg/dL; at the Activity target of 140 it is 90 mg/dL.
Setting the Activity target therefore makes the algorithm zero-temp about 20 mg/dL
(1.1 mmol/L) earlier, independently of any sensitivity change. That consequence is not
documented anywhere and follows directly from the code.

A profile switch resets autosens; a temp target does not. The documentation recommends temp
targets over profile switches for that reason, and declines to give any numeric profile
percentage for exercise, saying the value is individual and to start on the safe side.

## 7. Where the guidelines disagree

| Question | Value A | Value B | Value C |
|---|---|---|---|
| Basal reduction lead time | ADA 2016: 30 to 60 min | Riddell 2017: 60 to 90 min | ISPAD 2022 and EASD/ISPAD 2025: 90 to 120 min |
| Pre-exercise glucose target | ADA 2016: 90 to 250 mg/dL | Riddell 2017: 7 to 10 mmol/L | EASD/ISPAD 2020: 5.0 to 10.0, ideally 7.0 to 10.0 |
| Post-exercise sensitivity duration | McMahon 2007: second peak at 7 to 11 h | Mikines 1988: still present at 48 h, gone by 5 days | Reviews: 24 to 48 h |
| Pump suspension limit | Riddell 2017: under 2 h | ISPAD 2022: under 90 min for children | |
| Correction fraction when hyperglycaemic | Riddell, EASD/ISPAD, ISPAD: 50 percent | EXTOD: 30 percent | ISPAD alternative: 0.05 U/kg |

## 8. Figures that do not exist

Stated rather than estimated, because the tool is designed around their absence.

No published table gives the percentage of a rapid-acting bolus's glucose-lowering effect
remaining at 30, 60, 90 and 120 minutes. Bolus-calculator decay curves are proprietary and
appear in the literature only as figures. The nearest published anchors are a time to 50 percent
of total glucose infused of 183 to 186 minutes after a 0.15 U/kg analogue bolus (Morrow 2013)
and a late 50 percent time for the glucose-lowering effect of 274.5 ± 27.7 minutes (Walsh 2014).
This is why the tool uses the published exponential curve from oref rather than a vendor one.

No study has measured plasma free insulin following complete pump suspension during exercise.

No study has measured, in units, the extra automated insulin a closed loop delivers specifically
in response to a pre-exercise glucose rise, as distinct from total delivery in a fixed window.
Turner's 1.27 U against 0.29 U in the hour before exercise is the closest published quantity.

## Citations

Rabasa-Lhoret R, Bourque J, Ducros F, Chiasson JL. Diabetes Care 2001;24:625-630. PMID 11315820.
McAuley SA, Horsburgh JC, Ward GM, et al. Diabetologia 2016;59:1636-1644. PMID 27168135.
McAuley SA, Ward GM, Horsburgh JC, et al. Diabet Med 2017;34:1158-1164. PMID 28453877.
Roy-Fleming A, Taleb N, Messier V, et al. Diabetes Metab 2019;45:294-300. PMID 30165156.
Zaharieva DP, McGaugh S, Pooni R, et al. Diabetes Care 2019;42:824-831. PMID 30796112.
Heinemann L, Nosek L, Kapitza C, et al. Diabetes Care 2009;32:1437-1439. PMID 19487635.
Franc S, Daoudi A, Pochat A, et al. Diabetes Obes Metab 2015;17:1150-1157. PMID 26264812.
DirecNet Study Group, Tsalikian E, Kollman C, et al. Diabetes Care 2006;29:2200-2204. PMID 17003293.
Admon G, Weinstein Y, Falk B, et al. Pediatrics 2005;116:e348-e355. PMID 16140677.
Campbell MD, Walker M, Trenell MI, et al. Diabetes Care 2013;36:2217-2224. PMID 23514728.
Campbell MD, Walker M, Bracken RM, et al. BMJ Open Diabetes Res Care 2015;3:e000085. PMID 26019878.
Taplin CE, Cobry E, Messer L, et al. J Pediatr 2010;157:784-788. PMID 20650471.
Riddell MC, Li Z, Gal RL, et al. Diabetes Care 2023;46:704-713. PMID 36795053.
Francescato MP, Geat M, Fusi S, et al. Metabolism 2004;53:1126-1130.
Tagougui S, Taleb N, Legault L, et al. Diabetologia 2020;63:2282-2291. PMID 32740723.
McCarthy OM, Christensen MB, Kristensen KB, et al. Diabetes Technol Ther 2023;25:476-484. PMID 37053529.
Turner LV, Sherr JL, Zaharieva DP, et al. Diabetes Care 2025;48:1598-1606. PMID 40680105.
Morrison DJ, Vogrin S, Zaharieva DP, et al. Diabetes Obes Metab 2025;27:5160-5170. PMID 40566793.
Heise T, Zijlstra E, Nosek L, et al. Diabetes Obes Metab 2017;19:208-215. PMID 27709762.
Moser O, Zaharieva DP, Adolfsson P, et al. Diabetologia 2025;68:255-280. PMID 39653802.
Walsh J, Roberts R, Heinemann L. J Diabetes Sci Technol 2014;8:170-178. PMID 24876553.
Morrow L, Muchmore DB, Hompesch M, et al. Diabetes Care 2013;36:273-275. PMID 23043164.
DeFronzo RA, Ferrannini E, Sato Y, et al. J Clin Invest 1981;68:1468-1474. PMID 7033285.
