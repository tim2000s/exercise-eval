# Carbohydrate, glucose response and the measured rates

Specification for the carbohydrate and expected-response rules. Conversions use 18.0182 mg/dL
per mmol/L.

The single most useful finding for this tool is that a rate of fall can be predicted with a
point estimate and an interval, which an earlier reading of the literature suggested was not
possible. The intervals are wide, and the tool reports them rather than the point estimate
alone.

## 1. Rate of glucose change during exercise

García-García F, Kumareswaran K, Hovorka R, Hernando ME. Sports Med 2015;45:587-599.
Meta-analysis of ten studies with digitised population glucose profiles.

| Exercise type | Rate during exercise versus rest | Recovery |
|---|---|---|
| Continuous moderate | -4.43 mmol/L/h (95% CI -6.06 to -2.79), p<0.00001 | +0.70 (-1.14 to +2.54), not significant |
| Intermittent high intensity | -5.25 mmol/L/h (95% CI -7.02 to -3.48), p<0.00001 | +0.72 (-3.10 to +4.54), not significant |
| Resistance | -2.61 mmol/L/h (95% CI -7.55 to +2.34), p=0.30 | -0.02 (-7.58 to +7.53), not significant |

Resistance exercise is not significantly different from rest. Note that intermittent
high-intensity work comes out marginally steeper than continuous moderate here, which is the
opposite of Guelfi 2005 and of T1DEXI; the pooled studies differ in insulin state, and that is
the likely reason.

The laboratory figures do not transfer directly to shorter real-world sessions. A within-subject
matched-pair analysis of 1,546 bouts of 10 to 30 minutes from 482 participants across T1DEXI and
T1DEXIP, matched on starting glucose, rate of change, insulin on board and glucose coefficient of
variation, found a mean change of -2.2 mmol/L over a median 23-minute bout against +0.3 mmol/L in
matched non-activity periods, a difference of -1.9 mmol/L, p<0.0001. Hypoglycaemia during those
bouts occurred in under 2 percent.

That study also ranked the predictors, and the ordering is the one the tool implements: rate of
change first, then starting glucose, then coefficient of variation, then duration, then insulin
on board. It found no significant difference by age, activity type or intensity, which is a
direct challenge to any engine that keys its expectation on the activity label.

Within-person variability is the limit on all of this. The intraclass correlation for the
glucose response to repeated sessions is 0.12. Brož 2021 put ten men through an identical
protocol and measured falls between 4.4 and 10.0 mmol/L/h.

## 2. Carbohydrate required to prevent hypoglycaemia, by time since insulin

Francescato MP et al. Metabolism 2004;53:1126-1130. Twelve people with type 1 diabetes and
twelve matched people without, 1 h constant-workload cycling on four occasions at different
intervals after the morning subcutaneous dose, with oral carbohydrate titrated to prevent
hypoglycaemia.

| Time since insulin | Carbohydrate required |
|---|---|
| 1 h | 0.63 ± 0.30 g/kg |
| 2.5 h | 0.44 ± 0.32 g/kg |
| 4 h | 0.28 ± 0.24 g/kg |
| 5.5 h | 0.14 ± 0.18 g/kg |

Total glucose requirement correlated with plasma insulin, r=0.739, p<0.001, and not with
fitness. A four-fold gradient across four and a half hours at a fixed workload, driven by
insulin alone. This is a cleaner insulin-on-board gradient than anything in the guideline
tables, and it is what the tool uses to say whether the carbohydrate taken matched the insulin
that was still active.

Dubé MC et al. Med Sci Sports Exerc 2005;37:1276-1282. Nine adults, 60 min at 50 percent VO2max
three hours after breakfast, with 0, 15 or 30 g of liquid glucose 15 min before and intravenous
dextrose rescue below 5 mmol/L.

| Pre-exercise glucose | Intravenous dextrose required | Time to first rescue |
|---|---|---|
| 0 g | 10.5 ± 3.2 g | 31.7 ± 7.5 min |
| 15 g | 3.5 ± 1.8 g | 51.3 ± 4.2 min |
| 30 g | 1.6 ± 1.0 g | 55.6 ± 2.6 min |

The fall in glucose did not differ between arms; what differed was how long it took to reach the
floor. Extrapolating the regression, about 40 g would cover 60 min of exercise plus 60 min of
recovery.

## 3. Bolus reduction, and the measured falls behind the consensus table

Rabasa-Lhoret R et al. Diabetes Care 2001;24:625-630. Randomised crossover, eight men on
ultralente plus lispro, HbA1c 6.1 percent, six per exercise arm, 60 metabolic experiments,
cycling from 90 min after a 600 kcal breakfast containing 75 g of carbohydrate.

| Intensity | Duration | Lispro dose | Fall, mmol/L | Derived rate, mmol/L/h |
|---|---|---|---|---|
| 25% VO2max | 60 min | 100% | 2.95 ± 0.66 | 2.95 |
| 25% VO2max | 60 min | 50% | 3.25 ± 0.52, ns | 3.25 |
| 50% VO2max | 30 min | 100% | 3.36 ± 0.76 | 6.72 |
| 50% VO2max | 30 min | 50% | 2.26 ± 0.54, p=0.08 | 4.52 |
| 50% VO2max | 60 min | 100% | arm abandoned, 3 of 4 needed intravenous dextrose | |
| 50% VO2max | 60 min | 50% | 4.18 ± 0.57 | 4.18 |
| 50% VO2max | 60 min | 25% | 3.08 ± 0.53, ns | 3.08 |
| 75% VO2max | 30 min | 100% | 3.0 ± 0.71 | 6.00 |
| 75% VO2max | 30 min | 25% | 2.7 ± 0.38, ns | 5.40 |

The rates are derived here from the published fall and duration, not by the authors, and no
statistical test across intensities was performed. The abandoned arm is the most informative
single row in the table: an hour at half of VO2max on a full breakfast bolus sent three of four
participants to intravenous dextrose, which is why the tool treats a full bolus within three
hours of a session of that shape as the finding rather than a note.

Two further findings. At 25 percent VO2max more than two thirds of the total fall occurred in
the first 30 minutes of a 60-minute bout, so the fall is front-loaded rather than linear. And
dose reduction cut hypoglycaemia by 75 percent, from 64 to 16 episodes per 100 exercise
sessions.

## 4. Treating hypoglycaemia around exercise

The widely repeated convention that 15 g raises glucose by about 2.1 mmol/L (38 mg/dL) at 15 to
20 minutes cannot be traced to a primary measurement. The measured values are roughly half that.

| Dose | Measured rise | Time | Source |
|---|---|---|---|
| 15 g | +1.2 ± 0.4 mmol/L | 15 min | Slama 1990, n=41, insulin-induced |
| 15 g | about +1.3 mmol/L | 10 min | McTavish 2015, n=34, 136 real-life episodes |
| 10 g | about +2.2 mmol/L | 30 min, peak | Wiethop and Cryer 1993 |
| 20 g | about +3.5 mmol/L | 45 min, peak | Wiethop and Cryer 1993 |

The Wiethop and Cryer figures are peaks at 30 and 45 minutes rather than values at 15 to 20, and
conflating the two is where the 2.1 figure appears to have come from.

Brož J et al. Nutrients 2021;13:4165 is the only study of hypoglycaemia treatment around
exercise. Ten men on pump therapy, cycling at 50 percent heart rate reserve from 120 min after a
standardised breakfast taken with an unaltered bolus, given 20 g of glucose at the moment
exercise was stopped for hypoglycaemia.

| Measure | Value | Range |
|---|---|---|
| Glucose at exercise start | 10.57 ± 2.79 mmol/L | 7.2 to 14.2 |
| Rate of fall during exercise | 0.107 ± 0.028 mmol/L/min, 6.4 ± 1.7 mmol/L/h | 4.4 to 10.0 |
| Time to hypoglycaemia | 67.8 ± 25.5 min | 27.8 to 108.8 |
| Rate of rise after 20 g | 0.136 ± 0.042 mmol/L/min, 8.2 ± 2.5 mmol/L/h | 4.4 to 11.2 |
| Rise at 15 min | +1.00 ± 0.29 mmol/L | 0.58 to 1.60 |
| Time to first 1 mmol/L rise | 16.5 ± 5.4 min | 9.2 to 25.8 |
| Time to peak | 40.0 ± 9.9 min | 28.0 to 55.5 |

Twenty grams after exercise raised glucose by 1.0 mmol/L at 15 minutes, against 1.2 mmol/L from
15 g in insulin-induced hypoglycaemia. Per gram the response after exercise looks slightly
blunted, but ten men against a subgroup of 41 with different assays makes that a weak inference.
The treatment was given once exercise had stopped, so this still does not measure what happens
under continued contraction.

Weight-based dosing beats fixed dosing. Against 15 g, 0.3 g/kg gave an adjusted difference of
+0.26 mmol/L (95% CI 0.04 to 0.48, p=0.02) at 10 minutes, while 0.2 g/kg did not differ
(-0.07, 95% CI -0.29 to 0.16, p=0.56). Rebound above 8 mmol/L occurred in three of 409 episodes.

A 2026 systematic review of five databases found only seven studies of oral carbohydrate
treatment of non-severe hypoglycaemia in adults with type 1 diabetes, of which one used exercise
as the trigger. The 15 g rule itself derives from two small studies of intravenous
insulin-induced hypoglycaemia.

## 5. Carbohydrate during exercise, by duration

The sports nutrition bands, confirmed from Burke 2011 and Jeukendrup independently: small
amounts including mouth-rinsing for sustained high-intensity work of about an hour, 30 to 60 g/h
for longer events, and up to 90 g/h beyond two and a half hours using glucose plus fructose to
recruit a second intestinal transporter.

The current sports nutrition figure for the top band has moved to 90 to 120 g/h. That exceeds
every ceiling any diabetes guideline contemplates and is deliberately not propagated into this
tool.

The 60 g/h ceiling for glucose alone is the same physiological constraint that puts the 60 kg
cap on the ISPAD per-kilogram table: peak exogenous carbohydrate oxidation is 1.0 to 1.2 g/min.

## 6. After exercise

Scott SN, Fontana FY, Cocks M, et al. Post-exercise recovery for the endurance athlete with type
1 diabetes: a review and consensus statement. Lancet Diabetes Endocrinol 2021.

- 1.0 to 1.3 g of carbohydrate per kg per hour for the first four hours of recovery, starting as
  soon as possible, feeding every 30 minutes, where peak performance is needed within 24 hours or
  where fewer than eight hours separate two fuel-demanding sessions.
- Protein co-ingestion helps where carbohydrate intake is below the threshold for glycogen
  storage, around 0.5 to 0.8 g/kg/h. Above about 1 g/kg/h it adds nothing to glycogen, though the
  anabolic effect remains.
- Liver glycogen repletion is roughly doubled by glucose plus fructose over glucose alone, most
  clearly above 0.9 g/kg/h.

The primary glycogen trials behind those figures:

| Study | n | Carbohydrate rate | Glycogen synthesis |
|---|---|---|---|
| Blom 1987 | 5 to 7 trained cyclists | 0.175 g/kg/h glucose | 2.1 ± 0.5 mmol/kg/h |
| | | 0.35 g/kg/h | 5.8 ± 1.0 |
| | | 0.70 g/kg/h | 5.7 ± 0.9, a plateau |
| | | 0.35 g/kg/h fructose | 3.2 ± 0.7 |
| van Loon 2000 | 8 trained cyclists | 0.8 g CHO/kg/h | 16.6 ± 7.8 µmol glycosyl/g dry wt/h |
| | | 0.8 g CHO plus 0.4 g protein/kg/h | 35.4 ± 5.1, p<0.05 |
| | | 1.2 g CHO/kg/h | 44.8 ± 6.8, p<0.05 |
| Jentjens 2001 | 8 male cyclists | 1.2 g CHO/kg/h with and without protein | no difference |
| Howarth 2009 | 6 active men | 1.2 CHO, 1.2 CHO plus 0.4 protein, 1.6 CHO | no difference in glycogen |

Timing carries a penalty that cannot be made up later. Ivy 1988a gave 2 g/kg immediately or two
hours after exercise and measured 7.7 against 2.5 µmol/g wet weight per hour over the first two
hours. In the second two hours the delayed group reached only 4.1, still 45 percent below the
immediate group's first-two-hour rate, p<0.05, despite equal glucose and insulin.

The consensus states plainly that no measurement of post-exercise glycogen resynthesis has been
made in people with type 1 diabetes. Every figure in this section is transferred from athletes
without diabetes on the assumption that insulin is dosed correctly, and that assumption is
untested.

## 7. What does not exist

Three absences the tool is designed around rather than papering over.

No measurement of glucose rise per gram of oral glucose under continued muscle contraction.
Brož treated at the moment exercise stopped, and the 2026 systematic review confirms nothing
comes closer.

No measurement of post-exercise glycogen resynthesis in people with type 1 diabetes.

No titration locating the carbohydrate rate above which protein stops contributing to glycogen
synthesis. The 1.0 to 1.2 g/kg/h boundary is interpolated between three trials of six to eight
people each.

## 8. Prediction models, for calibration

Three published models take intensity and duration as inputs. None publishes a readable
intensity-to-rate coefficient, so none is reimplemented here, but the third sets a realistic
accuracy target for anything that tries.

| Model | Approach | Reported performance |
|---|---|---|
| Deichmann 2023, PLoS Comput Biol 19:e1010289 | Ordinary differential equations with insulin-independent uptake, glycogen depletion and prolonged post-exercise sensitivity | Validated on independent datasets, personalised to children in free-living use |
| Neumann 2025, Comput Biol Med 190:110015 | Gradient boosting, random forest and recurrent networks on T1DEXI, 79 participants | Median RMSE 6.99 mg/dL at 10 min, 16.85 mg/dL at 30 min, worse during and after exercise |
| García-Tirado 2019, J Diabetes Sci Technol 13:1054 | Model predictive control with anticipatory exercise action | 8 against 68 exercise-related hypoglycaemic events, in silico |

About 0.9 mmol/L (17 mg/dL) root mean square error at 30 minutes, from a model trained on the
same dataset, is the standard any prediction here would have to meet. This tool does not attempt
prediction; it reports what happened against what the literature says to expect, with the
interval attached.

## Citations

García-García F, Kumareswaran K, Hovorka R, Hernando ME. Sports Med 2015;45:587-599. PMID 25616852.
Brož J, Campbell MD, Urbanová J, et al. Nutrients 2021;13:4165. PMC8619071.
Francescato MP, Geat M, Fusi S, et al. Metabolism 2004;53:1126-1130.
Dubé MC, Weisnagel SJ, Prud'homme D, Lavoie C. Med Sci Sports Exerc 2005;37:1276-1282.
Rabasa-Lhoret R, Bourque J, Ducros F, Chiasson JL. Diabetes Care 2001;24:625-630. PMID 11315820.
McTavish L, Corley B, Weatherall M, et al. Diabet Med 2015;32:1143-1148.
Slama G, Traynard PY, Desplanque N, et al. Arch Intern Med 1990;150:589-593.
Wiethop BV, Cryer PE. Diabetes Care 1993;16:1131-1136.
Scott SN, Fontana FY, Cocks M, et al. Lancet Diabetes Endocrinol 2021.
Blom PC, Høstmark AT, Vaage O, et al. Med Sci Sports Exerc 1987;19:491-496.
van Loon LJ, Saris WH, Kruijshoop M, Wagenmakers AJ. Am J Clin Nutr 2000;72:106-111.
Jentjens RL, van Loon LJ, Mann CH, et al. J Appl Physiol 2001;91:839-846.
Howarth KR, Moreau NA, Phillips SM, Gibala MJ. J Appl Physiol 2009;106:1394-1402.
Ivy JL, Katz AL, Cutler CL, et al. J Appl Physiol 1988;64:1480-1485.
Glucose-lowering effects of physical activity in type 1 diabetes: a causal modelling and
matched-pair analysis. Diabetes Obes Metab 2025. PMC12628732.
Neumann C, et al. Comput Biol Med 2025;190:110015.
Deichmann J, et al. PLoS Comput Biol 2023;19:e1010289. PMC9974135.
