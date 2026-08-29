"""Run the test suite against deliberately broken implementations.

A test that cannot fail is worse than no test, and it is the failure mode that generated tests
most often have. Each mutation below is a plausible defect: an inverted comparison, a dropped
unit conversion, a threshold moved by one step. A mutation that no test catches is reported as
survived, and a survivor is either a gap in the suite or a line that does not matter.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (file, description, text to find, replacement)
MUTATIONS = [
    ("python/xeval/insulin.py", "IOB decays with the wrong sign in the exponent",
     "* math.exp(-t / tau) + 1", "* math.exp(t / tau) + 1"),
    ("python/xeval/insulin.py", "carbohydrate on board never decays",
     "total += carbs * (1 - mins / absorption_min)", "total += carbs"),
    ("python/xeval/insulin.py", "a basal reduction is detected at the wrong threshold",
     "t[\"rateUph\"] < profile_basal_uph * 0.95", "t[\"rateUph\"] < profile_basal_uph * 1.5"),
    ("python/xeval/insulin.py", "bolus reduction is computed the wrong way round",
     "reduction = 1 - (insulin / expected)", "reduction = 1 - (expected / insulin)"),
    ("python/xeval/insulin.py", "an expired temp basal counts again",
     "and t[\"t\"] + (t.get(\"durationMin\") or 0) * MS_PER_MIN > session_start_ms", ""),
    ("python/xeval/evaluate.py", "the hypoglycaemia threshold is raised to the hyper one",
     "HYPO_L1_MMOL = 3.9", "HYPO_L1_MMOL = 10.0"),
    ("python/xeval/evaluate.py", "brief excursions are counted as events",
     "MIN_EVENT_MIN = 15.0", "MIN_EVENT_MIN = 0.0"),
    ("python/xeval/evaluate.py", "gaps are smeared across the window instead of reported",
     "w = min(gap, MAX_GAP_MIN)", "w = gap"),
    ("python/xeval/evaluate.py", "the steepest fall returns the shallowest instead",
     "if worst is None or rate < worst:", "if worst is None or rate > worst:"),
    ("python/xeval/evaluate.py", "the antecedent window looks forward instead of back",
     "start_ms - 24 * MS_PER_HOUR, start_ms, \"24 hours before\"",
     "start_ms, start_ms + 24 * MS_PER_HOUR, \"24 hours before\""),
    ("python/xeval/intensity.py", "heart rate reserve uses maximum rather than reserve",
     "fractions = [max(0.0, (b - resting_hr) / reserve) for b in usable]",
     "fractions = [max(0.0, b / max_hr) for b in usable]"),
    ("python/xeval/intensity.py", "interval detection is switched off",
     "intermittent = variation >= INTERVAL_CV_THRESHOLD and fraction_high >= 0.10",
     "intermittent = False"),
    ("python/xeval/intensity.py", "the Tanaka equation reverts to 220 minus age",
     "return 208.0 - 0.7 * age_years", "return 220.0 - age_years"),
    ("python/xeval/intensity.py", "implausible heart rate readings are kept",
     "if s.get(\"bpm\") and 30 <= s[\"bpm\"] <= 230", "if s.get(\"bpm\")"),
    ("python/xeval/units.py", "the mmol conversion factor is wrong",
     "MGDL_PER_MMOL = 18.0182", "MGDL_PER_MMOL = 10.0"),
    ("python/xeval/report.py", "a pattern is claimed from a single session",
     "MIN_SESSIONS_FOR_PATTERN = 5", "MIN_SESSIONS_FOR_PATTERN = 1"),
    ("python/xeval/report.py", "poorly covered sessions enter the summary",
     "and r[\"glucose\"][\"during\"][\"coverage\"] >= 0.7", ""),
    ("python/xeval/nightscout_profile.py", "a schedule does not wrap from the previous day",
     "value = schedule[-1].get(\"value\")", "value = None"),
    # Rules added from the insulin, carbohydrate and automated-delivery literature.
    ("python/xeval/guidelines.py", "a bolus reduction table cell is wrong",
     "(0.50, 60): (0.75, True),", "(0.50, 60): (0.50, True),"),
    ("python/xeval/guidelines.py", "the extrapolated table cell is presented as measured",
     "(0.25, 30): (0.25, False),", "(0.25, 30): (0.25, True),"),
    ("python/xeval/guidelines.py", "a reduction is recommended above 80 percent of VO2max",
     "if vo2_fraction > 0.80:", "if False:"),
    ("python/xeval/guidelines.py", "the untested table cell is filled in by interpolation",
     "cell = BOLUS_REDUCTION_TABLE.get((bucket_v, bucket_d))",
     "cell = BOLUS_REDUCTION_TABLE.get((bucket_v, bucket_d)) or (0.5, True)"),
    ("python/xeval/guidelines.py", "the AndroidAPS sensitivity formula loses its denominator",
     "return c / (c + target_mgdl - AAPS_NORMAL_TARGET_MGDL)", "return c / 160.0"),
    ("python/xeval/guidelines.py", "the insulin on board gradient runs the wrong way",
     "(2.0, float(\"inf\"), -1.44, (-1.55, -1.28)),", "(2.0, float(\"inf\"), 0.5, (-1.55, -1.28)),"),
    ("python/xeval/guidelines.py", "the carbohydrate gradient by time since insulin is flat",
     "(5.5, 0.14, 0.18),", "(5.5, 0.63, 0.18),"),
    ("python/xeval/guidelines.py", "resistance exercise is given a significant expectation",
     "\"resistance\": (-2.61, (-7.55, 2.34), False),", "\"resistance\": (-2.61, (-7.55, 2.34), True),"),
    ("python/xeval/recommend.py", "every session is reported as within the expected range",
     "within = lo <= observed_rate <= hi", "within = True"),
    ("python/xeval/recommend.py", "announcing is recommended regardless of insulin on board",
     "prandial = iob[\"manual\"] >= 0.75", "prandial = True"),
    ("python/xeval/recommend.py", "a late basal reduction is not flagged",
     "if basal.lead_time_min is not None and basal.lead_time_min < 60:",
     "if basal.lead_time_min is not None and basal.lead_time_min < 0:"),
    ("python/xeval/recommend.py", "a suspension is not distinguished from a reduction",
     "and basal.fraction_of_profile <= 0.05:", "and basal.fraction_of_profile <= -1:"),
    ("python/xeval/recommend.py", "a full bolus before a moderate hour is downgraded",
     "severity = \"risk\" if (target and (target[\"reduction\"] or 0) >= 0.5) else \"adjustment\"",
     "severity = \"adjustment\""),
    ("python/xeval/recommend.py", "hypoglycaemia treatment is assessed with no low present",
     "if d.nadir_mmol is None or d.nadir_mmol >= HYPO_L1_MMOL:", "if False:"),
]


def run_tests() -> tuple[bool, str]:
    """Run the suite in a subprocess that writes no bytecode.

    The -B flag is not optional here. CPython decides a cached .pyc is still valid from the
    source file's modification time and size, and several of the mutations below replace text
    with a replacement of exactly the same length. Restoring such a file within the same mtime
    tick leaves a stale .pyc that matches on both keys, so the mutated bytecode keeps running
    after the source has been put back. That produced a corrupted working tree and two tests
    that failed against correct source, which is a far more confusing failure than the one the
    harness was looking for.
    """
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "tests/", "-q", "--no-header", "-x",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return proc.returncode == 0, proc.stdout.strip().splitlines()[-1] if proc.stdout else ""


def main() -> int:
    ok, line = run_tests()
    if not ok:
        print(f"The suite does not pass unmutated, so mutation results would be meaningless.\n{line}")
        return 2
    print(f"Baseline: {line}\n")

    survived = []
    for rel, description, find, replace in MUTATIONS:
        path = ROOT / rel
        original = path.read_text()
        if find not in original:
            print(f"  SKIP   {description}\n         (target text not found in {rel})")
            survived.append((description, "target text not found"))
            continue
        path.write_text(original.replace(find, replace, 1))
        try:
            passed, last = run_tests()
        finally:
            path.write_text(original)
            for cache in ROOT.rglob("__pycache__"):
                if "node_modules" not in str(cache):
                    shutil.rmtree(cache, ignore_errors=True)
        if passed:
            print(f"  SURVIVED  {description}")
            survived.append((description, "no test failed"))
        else:
            print(f"  caught    {description}")

    print()
    if survived:
        print(f"{len(survived)} of {len(MUTATIONS)} mutations survived:")
        for d, why in survived:
            print(f"  - {d} ({why})")
        return 1
    print(f"All {len(MUTATIONS)} mutations were caught.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
