"""The entry point the browser calls, and the summary across sessions.

One function, `analyse`, takes plain dictionaries and returns plain dictionaries, because that
is what crosses the Pyodide boundary cheaply. Nothing here touches the filesystem or the
network.

The per-session findings answer what happened in one session. The summary answers a different
and often more useful question: whether a pattern holds across sessions of the same kind. A
single session that fell 4 mmol/L says little, since any number of things could have caused it.
Eleven aerobic sessions that fell a median of 3.8 mmol/L, against four resistance sessions that
did not fall at all, says something a person can act on. Where there are too few sessions of a
kind to say anything, the summary says that rather than reporting a median of two.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, is_dataclass
from typing import Any

from . import guidelines as G
from . import insulin as I
from . import intensity as X
from .evaluate import HYPO_L1_MMOL, evaluate_session
from .nightscout_profile import basal_rate_at, carb_ratio_at
from .recommend import recommend
from .sources import SOURCES

MS_PER_MIN = 60_000.0

#: Below this many sessions of a kind, a median is not reported. Chosen so that a statement
#: about a pattern rests on more than a coincidence, not because five is a magic number.
MIN_SESSIONS_FOR_PATTERN = 5


def _plain(obj: Any) -> Any:
    """Convert dataclasses and tuples into what the JavaScript side can consume directly."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, float) and obj != obj:  # NaN
        return None
    return obj


def analyse(payload: dict) -> dict:
    """Evaluate every session in the payload.

    payload keys:
        sessions    exercise sessions from whichever importer ran
        entries     CGM readings, sorted, each with t in epoch ms and mmol
        treatments  normalised Nightscout treatments
        profile     the flattened Nightscout profile, or None
        settings    age_years, body_mass_kg, resting_hr, max_hr, risk_group, units, is_child,
                    dia_hours, insulin_peak
    """
    sessions = payload.get("sessions") or []
    entries = payload.get("entries") or []
    treatments = payload.get("treatments") or []
    profile = payload.get("profile")
    st = payload.get("settings") or {}

    units = st.get("units", "mmol")
    dia = float(st.get("dia_hours") or (profile or {}).get("dia") or 5.0)
    peak = float(st.get("insulin_peak") or I.PEAK_MINUTES["rapid"])
    risk_group = st.get("risk_group", "low")
    if risk_group not in G.RISK_GROUPS:
        risk_group = "low"

    results = []
    for s in sessions:
        try:
            results.append(_one(s, entries, treatments, profile, st, units, dia, peak, risk_group))
        except Exception as exc:  # a bad session must not take the whole report down
            results.append({
                "session": {"id": s.get("id"), "start": s.get("start"), "end": s.get("end"),
                            "typeName": s.get("typeName")},
                "error": f"{type(exc).__name__}: {exc}",
                "findings": [],
            })

    return {
        "sessions": results,
        "summary": summarise_across(results, units),
        "bibliography": _bibliography(results),
        "settings_used": {
            "units": units, "dia_hours": dia, "insulin_peak_min": peak,
            "risk_group": risk_group,
            "age_years": st.get("age_years"), "body_mass_kg": st.get("body_mass_kg"),
            "resting_hr": st.get("resting_hr"), "max_hr": st.get("max_hr"),
        },
    }


def _one(s, entries, treatments, profile, st, units, dia, peak, risk_group) -> dict:
    start, end = float(s["start"]), float(s["end"])

    g = evaluate_session(entries, treatments, start, end)

    inten = X.analyse(
        s.get("hr") or [],
        label_modality=s.get("modality", "unknown"),
        resting_hr=st.get("resting_hr") or s.get("restingHr"),
        max_hr=st.get("max_hr"),
        age_years=st.get("age_years"),
        duration_min=(end - start) / MS_PER_MIN,
        summary_avg_hr=s.get("avgHr"),
        summary_max_hr=s.get("maxHr"),
    )

    basal_rate = basal_rate_at(profile, start)
    cr = carb_ratio_at(profile, start)

    basal = I.basal_action(start, end, treatments, basal_rate)
    boluses = I.bolus_actions(start, treatments, cr)
    tt = I.temp_target_action(start, end, treatments)
    iob = I.iob_at(start, treatments, dia_hours=dia, peak_minutes=peak)
    cob = I.cob_at(start, treatments)

    findings = recommend(
        glucose=g, intensity=inten, basal=basal, boluses=boluses, temp_target=tt,
        session={"start": start, "end": end}, iob_at_start=iob, cob_at_start=cob,
        risk_group=risk_group, body_mass_kg=st.get("body_mass_kg"),
        is_child=bool(st.get("is_child")), units=units,
    )

    return {
        "session": {
            "id": s.get("id"), "start": start, "end": end,
            "durationMin": (end - start) / MS_PER_MIN,
            "typeName": s.get("typeName"), "title": s.get("title"),
            "labelModality": s.get("modality"), "sourceApp": s.get("sourceApp"),
            "distanceM": s.get("distanceM"), "activeKcal": s.get("activeKcal"),
        },
        "intensity": _plain(inten) | {"description": X.describe(inten)},
        "glucose": _plain(g),
        "insulin": {
            "basal": _plain(basal),
            "boluses": _plain(boluses),
            "tempTarget": tt,
            "iobAtStart": iob,
            "cobAtStart": cob,
            "profileBasalUph": basal_rate,
            "profileCarbRatio": cr,
        },
        "findings": [_plain(f) for f in findings],
    }


def summarise_across(results: list[dict], units: str) -> dict:
    """Look for patterns that hold across sessions of the same kind."""
    usable = [r for r in results if not r.get("error")
              and r["glucose"]["during"]["change_mmol"] is not None
              and r["glucose"]["during"]["coverage"] >= 0.7]

    by_modality: dict[str, list[dict]] = {}
    for r in usable:
        by_modality.setdefault(r["intensity"]["modality"], []).append(r)

    groups = []
    for modality, rows in sorted(by_modality.items(), key=lambda kv: -len(kv[1])):
        changes = [r["glucose"]["during"]["change_mmol"] for r in rows]
        nadirs = [r["glucose"]["during"]["nadir_mmol"] for r in rows
                  if r["glucose"]["during"]["nadir_mmol"] is not None]
        hypo_during = sum(1 for n in nadirs if n < HYPO_L1_MMOL)
        overnight = [r["glucose"]["overnight"] for r in rows if r["glucose"]["overnight"]]
        hypo_overnight = sum(1 for o in overnight if (o["nadir_mmol"] or 99) < HYPO_L1_MMOL)

        group = {
            "modality": modality,
            "n": len(rows),
            "median_change_mmol": statistics.median(changes),
            "hypo_during_n": hypo_during,
            "hypo_overnight_n": hypo_overnight,
            "overnight_assessed_n": len(overnight),
            "sufficient": len(rows) >= MIN_SESSIONS_FOR_PATTERN,
        }
        if len(rows) >= MIN_SESSIONS_FOR_PATTERN:
            # A quartile range rather than a standard deviation, because these distributions
            # are skewed by the occasional session that rose sharply and n is small.
            group["iqr_change_mmol"] = [
                statistics.quantiles(changes, n=4)[0],
                statistics.quantiles(changes, n=4)[2],
            ]
            group["note"] = (
                f"Across {len(rows)} {modality} sessions the median change during the session "
                f"was {statistics.median(changes):+.1f} mmol/L."
            )
        else:
            group["note"] = (
                f"Only {len(rows)} {modality} session{'s' if len(rows) != 1 else ''} with good "
                f"sensor coverage. That is too few to describe a pattern, so no median is given."
            )
        groups.append(group)

    contrast = None
    aer = next((g for g in groups if g["modality"] == "aerobic" and g["sufficient"]), None)
    res = next((g for g in groups if g["modality"] in {"resistance", "anaerobic"}
                and g["sufficient"]), None)
    if aer and res:
        contrast = (
            f"Aerobic sessions moved glucose by a median of {aer['median_change_mmol']:+.1f} "
            f"mmol/L and {res['modality']} sessions by {res['median_change_mmol']:+.1f} mmol/L. "
            f"That direction matches what the literature describes, where continuous work "
            f"lowers glucose and brief high-intensity work commonly raises it through the "
            f"catecholamine response."
        )

    return {
        "sessions_analysed": len(results),
        "sessions_with_coverage": len(usable),
        "groups": groups,
        "contrast": contrast,
        "caveat": (
            "These are the person's own sessions, not a controlled comparison. Anything that "
            "varies alongside exercise type, the time of day it is usually done, what was eaten "
            "beforehand, how much insulin was on board, will appear inside these medians. They "
            "describe what happened rather than what the exercise caused."
        ),
    }


def _bibliography(results: list[dict]) -> list[dict]:
    """Every source actually cited in this report, so the reader can check any of it."""
    cited = set()
    for r in results:
        for f in r.get("findings", []):
            cited.update(f.get("citations") or [])
    out = []
    for src in SOURCES.values():
        if any(c.startswith(src.short()) for c in cited):
            out.append({
                "citation": src.citation, "design": src.design, "n": src.n,
                "population": src.population, "grade": src.grade,
                "is_evidence": src.is_evidence,
            })
    return sorted(out, key=lambda s: s["citation"])
