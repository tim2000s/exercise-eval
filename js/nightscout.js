// Nightscout REST client for a browser with no server of its own.
//
// Three findings from reading cgm-remote-monitor v15.0.7 shape this file, and each is
// documented in docs/nightscout-api.md:
//
//   1. A stock site sends no Access-Control-Allow-Origin, so the site owner has to add cors to
//      the ENABLE variable. Nothing in this client can work around that.
//   2. The api-secret header cannot be used from a browser. It is absent from the fixed
//      Access-Control-Allow-Headers list, so the preflight succeeds and the browser then
//      aborts the real request. Credentials go in the query string instead.
//   3. A query carrying no date filter is silently capped at the last four days, whatever
//      count is asked for. Every request here carries an explicit window.

export const MGDL_PER_MMOL = 18.0182;

/** Days per page when walking backwards through history. */
const PAGE_DAYS = 7;
/** Courtesy delay between pages. Most sites run on a shared free-tier database. */
const PAGE_DELAY_MS = 120;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function normaliseBase(url) {
  let u = String(url || '').trim();
  if (!u) throw new Error('No Nightscout address given.');
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  u = u.replace(/\/+$/, '').replace(/\/api\/v[0-9]+.*$/i, '');
  const parsed = new URL(u);
  if (parsed.protocol !== 'https:' && parsed.hostname !== 'localhost') {
    throw new Error(
      'The address must use https. A page served over https cannot fetch from http, and the ' +
        'browser blocks it before the request is sent.',
    );
  }
  return parsed.origin;
}

/**
 * A fetch that turns the browser's deliberately uninformative CORS failure into something the
 * user can act on.
 *
 * A cross-origin failure and an unreachable host both surface as the same TypeError, with no
 * detail, by design: the page is not allowed to learn anything about a response it was not
 * granted access to. Since the overwhelmingly likely cause here is the missing cors flag, the
 * message says so while acknowledging the other possibilities.
 */
async function get(base, path, params, token) {
  const url = new URL(base + path);
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }
  if (token) url.searchParams.set('token', token);

  let res;
  try {
    res = await fetch(url.toString(), { credentials: 'omit', mode: 'cors' });
  } catch (e) {
    const err = new Error(
      'The browser blocked the request to your Nightscout site before any response could be ' +
        'read. The usual cause is that cross-origin requests are not enabled on the site. Add ' +
        'cors to the ENABLE environment variable, set CORS_ALLOW_ORIGIN to *, and restart the ' +
        'service. The address being wrong, or the site being asleep or offline, produces the ' +
        'same message.',
    );
    err.cause = e;
    err.kind = 'cors-or-network';
    throw err;
  }
  if (res.status === 401 || res.status === 403) {
    const err = new Error(
      'Nightscout refused the request as unauthorised. This site is not readable without a ' +
        'credential, which means AUTH_DEFAULT_ROLES is set to denied. Create a read-only ' +
        'subject token in Admin Tools and paste it in.',
    );
    err.kind = 'auth';
    throw err;
  }
  if (!res.ok) {
    const err = new Error(`Nightscout returned ${res.status} ${res.statusText} for ${path}.`);
    err.kind = 'http';
    throw err;
  }
  return res.json();
}

/**
 * Check the connection and read the site's units.
 *
 * status.json is the cheapest endpoint that exercises the same CORS path as everything else,
 * so a failure here is diagnosed once rather than on every subsequent request.
 */
export async function probe(base, token) {
  const status = await get(base, '/api/v1/status.json', {}, token);
  const units = (status?.settings?.units || '').toLowerCase().startsWith('mmol') ? 'mmol' : 'mgdl';
  return {
    ok: true,
    units,
    version: status?.version || null,
    name: status?.name || null,
    // The presence of these tells the report which of the AAPS quirks to expect.
    enabledPlugins: status?.settings?.enable || [],
  };
}

/**
 * Walk backwards through a collection in fixed windows.
 *
 * Paging rather than one large request keeps every call inside the platform request timeout,
 * which is 30 s on Heroku and reportedly similar on Fly.io, makes a long fetch resumable, and
 * gives the progress bar something real to report. Nightscout applies no rate limiting, so the
 * delay between pages is courtesy to a shared database rather than a requirement.
 */
async function pageBackwards(base, token, path, startMs, endMs, buildParams, onProgress) {
  const out = [];
  const totalMs = endMs - startMs;
  let cursor = endMs;
  let guard = 0;

  while (cursor > startMs) {
    if (++guard > 1000) throw new Error(`Paging ${path} did not terminate. Aborted after 1000 pages.`);
    const windowStart = Math.max(startMs, cursor - PAGE_DAYS * 86400000);
    const batch = await get(base, path, buildParams(windowStart, cursor), token);
    if (Array.isArray(batch)) out.push(...batch);
    if (onProgress) {
      onProgress({
        fraction: Math.min(1, (endMs - windowStart) / totalMs),
        records: out.length,
        oldest: windowStart,
      });
    }
    cursor = windowStart;
    if (cursor > startMs) await sleep(PAGE_DELAY_MS);
  }
  return out;
}

/**
 * CGM entries over a window, returned oldest first.
 *
 * sgv is always mg/dL in storage regardless of the site's display units, so the conversion to
 * mmol/L happens once here and the rest of the tool works in mmol/L.
 */
export async function fetchEntries(base, token, startMs, endMs, onProgress) {
  const raw = await pageBackwards(
    base, token, '/api/v1/entries.json', startMs, endMs,
    (from, to) => ({
      count: 4000, // A seven-day window is 2016 readings at five minutes. Headroom for denser sensors.
      'find[date][$gte]': from,
      'find[date][$lt]': to,
    }),
    onProgress,
  );

  const seen = new Set();
  const out = [];
  for (const e of raw) {
    const t = typeof e.date === 'number' ? e.date : Date.parse(e.dateString);
    const sgv = e.sgv ?? e.mbg ?? null;
    if (!Number.isFinite(t) || sgv === null) continue;
    // Overlapping pages and duplicate uploads from two devices both produce repeats.
    const key = `${t}|${sgv}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      t,
      mgdl: sgv,
      mmol: sgv / MGDL_PER_MMOL,
      direction: e.direction || null,
      device: e.device || null,
      type: e.type || 'sgv',
    });
  }
  out.sort((a, b) => a.t - b.t);
  return out;
}

/**
 * Treatments over a window, normalised past the AAPS naming quirks.
 *
 * created_at is an ISO string on this collection, not the epoch milliseconds that entries use.
 */
export async function fetchTreatments(base, token, startMs, endMs, onProgress) {
  const raw = await pageBackwards(
    base, token, '/api/v1/treatments.json', startMs, endMs,
    (from, to) => ({
      count: 5000,
      'find[created_at][$gte]': new Date(from).toISOString(),
      'find[created_at][$lt]': new Date(to).toISOString(),
    }),
    onProgress,
  );
  return normaliseTreatments(raw);
}

/**
 * Normalise the treatments collection.
 *
 * AAPS does not use the care portal event names the way the names suggest, so an
 * interpretation keyed on eventType alone is wrong in three specific ways:
 *
 *   Every SMB is written as Correction Bolus, and every other bolus, including a correction
 *   dialled by hand, as Meal Bolus (BolusExtension.kt:28).
 *
 *   Carbohydrate below 12 g is Carb Correction and 12 g or more is Meal Bolus with no insulin
 *   field (CarbsExtension.kt:26), so Meal Bolus documents are a mixture of insulin-only,
 *   carbs-only and both.
 *
 *   An Effective Profile Switch arrives as eventType Note with originalProfileName set. There
 *   is no Effective Profile Switch string on the wire, so without this it appears as a blank
 *   comment (EffectiveProfileSwitchExtension.kt:40).
 */
export function normaliseTreatments(raw) {
  const out = [];
  const seen = new Set();

  for (const r of raw) {
    const t = Date.parse(r.created_at || r.timestamp || r.eventTime);
    if (!Number.isFinite(t)) continue;
    const key = r._id || `${t}|${r.eventType}|${r.insulin ?? ''}|${r.carbs ?? ''}`;
    if (seen.has(key)) continue;
    seen.add(key);

    const ev = r.eventType || '';
    const base = {
      t,
      eventType: ev,
      enteredBy: r.enteredBy || null,
      notes: r.notes || null,
      raw: r,
    };

    if (ev === 'Note' && r.originalProfileName) {
      out.push({ ...base, kind: 'effective-profile-switch', profileName: r.originalProfileName,
        percentage: r.originalPercentage ?? 100, timeshift: r.originalTimeshift ?? 0,
        durationMin: r.originalDuration ? r.originalDuration / 60000 : null });
      continue;
    }

    if (ev === 'Temporary Target') {
      // AAPS writes targets in mg/dL whatever the display units.
      const top = r.targetTop ?? null;
      const bottom = r.targetBottom ?? null;
      const durationMin = r.duration ?? (r.durationInMilliseconds ? r.durationInMilliseconds / 60000 : 0);
      out.push({
        ...base,
        kind: durationMin === 0 ? 'temp-target-cancel' : 'temp-target',
        // Nightscout's own care portal writes Manual where AAPS writes Custom. Same meaning.
        reason: r.reason === 'Manual' ? 'Custom' : (r.reason || 'Custom'),
        durationMin,
        // A cancel may legitimately carry no target fields at all.
        targetTopMgdl: top, targetBottomMgdl: bottom,
        targetTopMmol: top === null ? null : top / MGDL_PER_MMOL,
        targetBottomMmol: bottom === null ? null : bottom / MGDL_PER_MMOL,
      });
      continue;
    }

    if (ev === 'Temp Basal' || ev === 'Temp Basal Start') {
      out.push({
        ...base,
        kind: 'temp-basal',
        // rate is always present and always absolute U/h. absolute appears only for
        // absolute-rate temp basals, percent only for percentage ones, where percent is the
        // delta from 100, so a 60 percent temp basal writes -40.
        rateUph: r.rate ?? r.absolute ?? null,
        percentDelta: r.percent ?? null,
        durationMin: r.duration ?? (r.durationInMilliseconds ? r.durationInMilliseconds / 60000 : null),
        basalType: r.type || null,
      });
      continue;
    }

    if (ev === 'Profile Switch') {
      let profile = null;
      if (r.profileJson) {
        // profileJson is the whole profile as a JSON string, not a nested object.
        try { profile = JSON.parse(r.profileJson); } catch { profile = null; }
      }
      out.push({ ...base, kind: 'profile-switch', profileName: r.profile || null,
        percentage: r.percentage ?? 100, timeshift: r.timeshift ?? 0,
        durationMin: r.duration ?? null, profile });
      continue;
    }

    if (ev === 'Exercise') {
      out.push({ ...base, kind: 'exercise-event',
        durationMin: r.duration ?? (r.durationInMilliseconds ? r.durationInMilliseconds / 60000 : null) });
      continue;
    }

    const insulin = Number.isFinite(r.insulin) ? r.insulin : null;
    const carbs = Number.isFinite(r.carbs) ? r.carbs : null;
    if (insulin !== null || carbs !== null) {
      const isSmb = ev === 'Correction Bolus' && (r.isSMB === true || r.type === 'SMB');
      out.push({
        ...base,
        kind: 'dose',
        insulinU: insulin,
        carbsG: carbs,
        isSmb,
        // Manual and automatic insulin are separated because a session's insulin exposure
        // means something different when the loop chose it than when the person did.
        automatic: isSmb,
      });
      continue;
    }

    out.push({ ...base, kind: 'other' });
  }

  out.sort((a, b) => a.t - b.t);
  return out;
}

/**
 * The profile record, flattened to the fields the analysis needs.
 *
 * Nightscout returns an array of profile documents, each holding a store of named profiles.
 * The one in use is named by defaultProfile.
 */
export async function fetchProfile(base, token) {
  const docs = await get(base, '/api/v1/profile.json', {}, token);
  if (!Array.isArray(docs) || !docs.length) return null;
  const doc = docs[0];
  const name = doc.defaultProfile || Object.keys(doc.store || {})[0];
  const p = doc.store?.[name];
  if (!p) return null;

  // Schedule entries carry either seconds from midnight or an HH:MM time, depending on writer.
  const sched = (arr) => (Array.isArray(arr) ? arr : []).map((e) => ({
    secondsFromMidnight: Number.isFinite(e.timeAsSeconds)
      ? e.timeAsSeconds
      : (() => { const [h, m] = String(e.time || '00:00').split(':').map(Number); return h * 3600 + m * 60; })(),
    value: Number(e.value),
  })).sort((a, b) => a.secondsFromMidnight - b.secondsFromMidnight);

  const units = (p.units || '').toLowerCase().startsWith('mmol') ? 'mmol' : 'mgdl';
  return {
    name,
    units,
    dia: Number(p.dia) || 5,
    timezone: p.timezone || null,
    basal: sched(p.basal),           // U/h
    isf: sched(p.sens),              // mg/dL or mmol/L per unit, per units above
    carbRatio: sched(p.carbratio),   // g per unit
    targetLow: sched(p.target_low),
    targetHigh: sched(p.target_high),
    startDate: doc.startDate || null,
  };
}

/** Value of a Nightscout schedule at a given instant, in the profile's own timezone-naive terms. */
export function scheduleValueAt(schedule, date) {
  if (!schedule || !schedule.length) return null;
  const s = date.getHours() * 3600 + date.getMinutes() * 60 + date.getSeconds();
  let value = schedule[schedule.length - 1].value; // wraps from the previous day
  for (const e of schedule) {
    if (e.secondsFromMidnight <= s) value = e.value; else break;
  }
  return value;
}

/**
 * Device status, for the loop's own view of what it was doing.
 *
 * This collection is large and is only fetched when the analysis needs algorithm behaviour
 * rather than insulin accounting. Treatments record what the pump did; enacted records what
 * the algorithm decided each cycle, and the two diverge when a command failed.
 */
export async function fetchDeviceStatus(base, token, startMs, endMs, onProgress) {
  const raw = await pageBackwards(
    base, token, '/api/v1/devicestatus.json', startMs, endMs,
    (from, to) => ({
      count: 3000,
      'find[created_at][$gte]': new Date(from).toISOString(),
      'find[created_at][$lt]': new Date(to).toISOString(),
    }),
    onProgress,
  );
  return raw.map((d) => {
    const t = Date.parse(d.created_at);
    const s = d.openaps?.suggested || {};
    const e = d.openaps?.enacted || {};
    return {
      t,
      iob: d.openaps?.iob?.iob ?? s.IOB ?? null,
      cob: s.COB ?? e.COB ?? null,
      // sensitivityRatio is the autosens ratio only when no temp target is active. Under a
      // temp target with sensitivity adjustment enabled it is derived from the target instead,
      // which is exactly the situation this tool analyses, so the caller must mask it.
      sensitivityRatio: s.sensitivityRatio ?? e.sensitivityRatio ?? null,
      variableSens: s.variable_sens ?? null,
      enactedRate: e.rate ?? null,
      enactedDuration: e.duration ?? null,
      pumpBattery: d.pump?.battery?.percent ?? null,
      device: d.device || null,
    };
  }).filter((d) => Number.isFinite(d.t));
}
