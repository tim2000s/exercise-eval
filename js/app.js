// Wiring. Nothing here decides anything about diabetes; it moves data between the importers,
// the Nightscout client and the Python engine, and renders what comes back.

import { normaliseBase, probe, fetchEntries, fetchTreatments, fetchProfile } from './nightscout.js';
import { importFile, mergeDatasets } from './import.js';
import { analyse } from './pyodide-bridge.js';
import * as strava from './strava.js';
import { sessionChart, attachHover, summaryTable } from './charts.js';

const $ = (id) => document.getElementById(id);
const MS_PER_DAY = 86_400_000;

/** Settings persist between visits; the token deliberately does not. */
const SETTINGS_KEY = 'exercise-eval.settings.v1';
const PERSISTED = ['ns-url', 'date-from', 'date-to', 'set-age', 'set-mass', 'set-resting',
  'set-maxhr', 'set-units', 'set-risk', 'set-insulin'];

/**
 * A day either side of the chosen range is fetched.
 *
 * The analysis needs data outside every session: time below range in the 24 hours before is the
 * strongest predictor it has of post-exercise nocturnal hypoglycaemia, and the delayed risk
 * period runs 7 to 11 hours afterwards, which for an evening session falls in the following
 * night. Fetching the range alone would leave both windows empty and the report would quietly
 * report less than it could.
 */
const FETCH_PADDING_MS = MS_PER_DAY;

/**
 * Strava credentials live under their own key, separate from the settings blob.
 *
 * The client secret is a real credential, so it is worth being able to remove it in one action
 * without disturbing anything else, and worth not having it travel inside a general settings
 * object that other code writes to. Activities themselves are never persisted: they are held in
 * memory for the length of the visit and nothing more.
 */
const STRAVA_KEY = 'exercise-eval.strava.v1';

function loadStrava() {
  try { return JSON.parse(localStorage.getItem(STRAVA_KEY) || 'null'); } catch { return null; }
}

function saveStrava(value) {
  try {
    if (value) localStorage.setItem(STRAVA_KEY, JSON.stringify(value));
    else localStorage.removeItem(STRAVA_KEY);
  } catch { /* a private window; the connection then lasts only this visit */ }
}

const state = {
  nightscout: null,   // { entries, treatments, profile, units, base, range }
  datasets: [],       // one per imported file
  files: [],
  selected: null,     // Set of session ids, or null before any file has been imported
  strava: null,       // { clientId, clientSecret, refreshToken, accessToken, expiresAt, athlete }
};

// ---- logging ---------------------------------------------------------------------------------

function log(message, kind = '') {
  $('log-block').hidden = false;
  const li = document.createElement('li');
  if (kind) li.className = kind;
  li.textContent = message;
  $('log').appendChild(li);
  li.scrollIntoView({ block: 'nearest' });
}

function progress(fraction) {
  const el = $('progress');
  if (fraction === null) { el.hidden = true; return; }
  el.hidden = false;
  el.querySelector('.progress-bar').style.width = `${Math.round(fraction * 100)}%`;
}

// ---- settings --------------------------------------------------------------------------------

function loadSettings() {
  // localStorage throws outright in some contexts rather than returning nothing, so every
  // access is guarded and the page renders correctly with no stored value.
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
    for (const id of PERSISTED) {
      if (saved[id] !== undefined && $(id)) $(id).value = saved[id];
    }
  } catch { /* a private window, cleared site data, or storage disabled */ }
}

function saveSettings() {
  try {
    const out = {};
    for (const id of PERSISTED) if ($(id)) out[id] = $(id).value;
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(out));
  } catch { /* nothing here is important enough to interrupt the user over */ }
}

/** Local midnight for a YYYY-MM-DD value from a date input. */
function dayStart(value) {
  const [y, m, d] = String(value || '').split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d).getTime();
}

const isoDay = (ms) => {
  const d = new Date(ms);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/**
 * The chosen period, as a half-open interval.
 *
 * The end is the midnight after the chosen day, so that a range of one day covers that whole
 * day rather than collapsing to an instant.
 */
function readRange() {
  const from = dayStart($('date-from').value);
  const toDay = dayStart($('date-to').value);
  if (from === null || toDay === null) return null;
  const to = toDay + MS_PER_DAY;
  if (to <= from) return null;
  return { from, to, days: Math.round((to - from) / MS_PER_DAY) };
}

function setRange(fromMs, toMs) {
  $('date-from').value = isoDay(fromMs);
  $('date-to').value = isoDay(toMs);
  saveSettings();
  onRangeChanged();
}

function describeRange() {
  const range = readRange();
  const el = $('period-summary');
  if (!range) {
    el.textContent = 'Choose a start date on or before the end date.';
    return null;
  }
  const fmt = (ms) => new Date(ms).toLocaleDateString([], {
    day: 'numeric', month: 'short', year: 'numeric' });
  el.textContent =
    `${range.days} day${range.days === 1 ? '' : 's'}, ${fmt(range.from)} to ` +
    `${fmt(range.to - MS_PER_DAY)}. A day either side of that is fetched as well.`;
  return range;
}

/** Mark whichever preset matches the current range, so the buttons reflect the state. */
function syncPresets() {
  const range = readRange();
  for (const b of document.querySelectorAll('button.preset')) {
    let matches = false;
    if (range) {
      const want = presetRange(b.dataset);
      matches = want && want.from === range.from && want.to === range.to;
    }
    b.setAttribute('aria-pressed', matches ? 'true' : 'false');
  }
}

function presetRange({ days, month }) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (days) {
    return { from: today - (Number(days) - 1) * MS_PER_DAY, to: today + MS_PER_DAY };
  }
  if (month === 'this') {
    return { from: new Date(now.getFullYear(), now.getMonth(), 1).getTime(), to: today + MS_PER_DAY };
  }
  if (month === 'last') {
    return {
      from: new Date(now.getFullYear(), now.getMonth() - 1, 1).getTime(),
      to: new Date(now.getFullYear(), now.getMonth(), 1).getTime(),
    };
  }
  return null;
}

/** Sessions from every imported file whose start falls inside the chosen period. */
function sessionsInRange() {
  const range = readRange();
  const all = mergeDatasets(state.datasets).sessions;
  if (!range) return { inRange: [], outside: all.length, all };
  const inRange = all.filter((s) => s.start >= range.from && s.start < range.to);
  return { inRange, outside: all.length - inRange.length, all };
}

function onRangeChanged() {
  describeRange();
  syncPresets();
  renderSessionPicker();
  updateRunButton();
}

function readSettings() {
  const num = (id) => {
    const v = Number($(id).value);
    return Number.isFinite(v) && v > 0 ? v : null;
  };
  const age = num('set-age');
  return {
    age_years: age,
    body_mass_kg: num('set-mass'),
    resting_hr: num('set-resting'),
    max_hr: num('set-maxhr'),
    units: $('set-units').value,
    risk_group: $('set-risk').value,
    insulin_peak: Number($('set-insulin').value),
    is_child: age !== null && age < 18,
  };
}

// ---- Nightscout ------------------------------------------------------------------------------

async function connectNightscout() {
  const button = $('ns-connect');
  const status = $('ns-status');
  button.disabled = true;
  progress(0);

  try {
    const base = normaliseBase($('ns-url').value);
    const token = $('ns-token').value.trim() || null;
    const range = readRange();
    if (!range) throw new Error('Choose a start date on or before the end date first.');
    const startMs = range.from - FETCH_PADDING_MS;
    // Never ask for data from the future; a range ending today would otherwise request tomorrow.
    const endMs = Math.min(Date.now(), range.to + FETCH_PADDING_MS);
    if (endMs <= startMs) throw new Error('That period is entirely in the future.');
    const days = range.days;

    status.textContent = 'Checking the connection.';
    const info = await probe(base, token);
    log(`Connected to ${info.name || base}${info.version ? `, Nightscout ${info.version}` : ''}. ` +
        `The site reports its units as ${info.units === 'mmol' ? 'mmol/L' : 'mg/dL'}.`);

    status.textContent = 'Fetching glucose readings.';
    const entries = await fetchEntries(base, token, startMs, endMs, (p) => {
      progress(p.fraction * 0.6);
      status.textContent = `Fetching glucose readings: ${p.records.toLocaleString()} so far.`;
    });
    log(`${entries.length.toLocaleString()} sensor readings over ${days} days.`);
    if (!entries.length) {
      log('No sensor readings were returned. Check the date range and that the site holds ' +
          'data for that period.', 'warn');
    }

    status.textContent = 'Fetching treatments.';
    const treatments = await fetchTreatments(base, token, startMs, endMs, (p) => {
      progress(0.6 + p.fraction * 0.35);
      status.textContent = `Fetching treatments: ${p.records.toLocaleString()} so far.`;
    });
    const doses = treatments.filter((t) => t.kind === 'dose').length;
    const tempTargets = treatments.filter((t) => t.kind === 'temp-target').length;
    log(`${treatments.length.toLocaleString()} treatments, of which ${doses.toLocaleString()} ` +
        `carried insulin or carbohydrate and ${tempTargets} were temporary targets.`);

    status.textContent = 'Fetching the profile.';
    progress(0.97);
    const profile = await fetchProfile(base, token);
    if (profile) {
      log(`Profile "${profile.name}": duration of insulin action ${profile.dia} h, ` +
          `${profile.basal.length} basal rate${profile.basal.length === 1 ? '' : 's'}, ` +
          `${profile.carbRatio.length} carbohydrate ratio` +
          `${profile.carbRatio.length === 1 ? '' : 's'}.`);
    } else {
      log('No profile was returned, so basal and bolus comparisons will not be possible.', 'warn');
    }

    state.nightscout = { entries, treatments, profile, units: info.units, base, days, range };
    // Coverage is only knowable once the data is here, so the picker is rebuilt to grey out
    // anything the fetch did not reach.
    state.selected = null;
    renderSessionPicker();
    status.textContent = `${entries.length.toLocaleString()} readings ready.`;
    progress(1);
    setTimeout(() => progress(null), 600);
  } catch (err) {
    status.textContent = 'Could not fetch.';
    log(err.message, 'warn');
    progress(null);
  } finally {
    button.disabled = false;
    updateRunButton();
  }
}

// ---- Strava ----------------------------------------------------------------------------------

function stravaMessage(text, kind = '') {
  const el = $('strava-message');
  el.textContent = text;
  el.className = `hint ${kind}`;
}

function renderStrava() {
  const c = state.strava;
  const connected = Boolean(c?.refreshToken);
  $('strava-disconnected').hidden = connected;
  $('strava-connected').hidden = !connected;
  $('strava-domain').textContent = location.hostname;

  if (connected) {
    const who = c.athlete?.name ? ` as ${c.athlete.name}` : '';
    $('strava-who').innerHTML =
      `<strong>Connected to Strava${esc(who)}.</strong> Activities are fetched for the dates in ` +
      'step 1 and held only for this visit.';
  }
  if (c?.clientId && !connected) $('strava-id').value = c.clientId;
}

/** Ensure a usable access token, refreshing it if the six-hour life has run out. */
async function stravaToken() {
  const c = state.strava;
  if (!c?.refreshToken) throw new Error('Not connected to Strava.');
  // A minute of margin, so a token does not expire between the check and the request.
  if (c.accessToken && c.expiresAt > Date.now() + 60_000) return c.accessToken;

  stravaMessage('Renewing the Strava access token.', 'working');
  const t = await strava.refreshTokens(c.clientId, c.clientSecret, c.refreshToken);
  state.strava = { ...c, ...t };
  saveStrava(state.strava);
  return t.accessToken;
}

function stravaConnect() {
  const clientId = $('strava-id').value.trim();
  const clientSecret = $('strava-secret').value.trim();
  if (!clientId || !clientSecret) {
    stravaMessage('Both the client ID and the client secret are needed.', 'error');
    return;
  }
  // The secret has to survive the redirect, since the exchange happens when Strava sends the
  // browser back to this page.
  state.strava = { ...(state.strava || {}), clientId, clientSecret };
  saveStrava(state.strava);
  location.href = strava.authoriseUrl(clientId);
}

function stravaForget() {
  state.strava = null;
  saveStrava(null);
  $('strava-id').value = '';
  $('strava-secret').value = '';
  // Drop anything already fetched from Strava, since the connection that justified it is gone.
  const before = state.datasets.length;
  state.datasets = state.datasets.filter((d) => d.source !== 'strava');
  if (state.datasets.length !== before) state.selected = null;
  renderStrava();
  renderSessionPicker();
  updateRunButton();
  stravaMessage('The client ID and secret have been removed from this browser. Revoke the ' +
                'application on Strava as well if you want to end its access entirely.');
  log('Strava credentials removed from this browser.');
}

/** Complete the authorisation if this page load is a return from Strava. */
async function stravaCompleteRedirect() {
  const result = strava.readRedirect();
  if (!result) return;

  if (result.error) {
    stravaMessage(result.error, 'error');
    log(result.error, 'warn');
    return;
  }
  const c = state.strava;
  if (!c?.clientId || !c?.clientSecret) {
    stravaMessage('Strava sent an authorisation back, but the client ID and secret are no ' +
                  'longer in this browser. Enter them and connect again.', 'error');
    return;
  }
  try {
    stravaMessage('Completing the connection to Strava.', 'working');
    const tokens = await strava.exchangeCode(c.clientId, c.clientSecret, result.code);
    state.strava = { ...c, ...tokens };
    saveStrava(state.strava);
    renderStrava();
    stravaMessage('Connected. Fetch activities for the dates in step 1 when you are ready.');
    log(`Connected to Strava${tokens.athlete?.name ? ` as ${tokens.athlete.name}` : ''}.`);
  } catch (err) {
    stravaMessage(err.message, 'error');
    log(`Strava: ${err.message}`, 'warn');
  }
}

async function stravaFetch() {
  const range = readRange();
  if (!range) { stravaMessage('Choose a start date on or before the end date first.', 'error'); return; }

  const button = $('strava-fetch');
  button.disabled = true;
  try {
    const token = await stravaToken();
    stravaMessage('Fetching activities from Strava.', 'working');
    const { activities } = await strava.fetchActivities(
      token, range.from, range.to, (m) => stravaMessage(m, 'working'));

    const dataset = strava.toSessions(activities);
    // A second fetch replaces the first rather than doubling every session.
    state.datasets = state.datasets.filter((d) => d.source !== 'strava');
    state.datasets.push(dataset);
    state.selected = null;

    log(`Strava: ${dataset.sessions.length} activit${dataset.sessions.length === 1 ? 'y' : 'ies'} ` +
        `between ${new Date(range.from).toLocaleDateString()} and ` +
        `${new Date(range.to - MS_PER_DAY).toLocaleDateString()}.`);
    for (const w of dataset.warnings) log(`Strava: ${w}`, 'warn');

    stravaMessage(
      `${dataset.sessions.length} activit${dataset.sessions.length === 1 ? 'y' : 'ies'} fetched. ` +
      'Heart rate detail is fetched for the sessions you choose, when you run the analysis.');
    renderSessionPicker();
    updateRunButton();
  } catch (err) {
    stravaMessage(err.message, 'error');
    log(`Strava: ${err.message}`, 'warn');
    if (err.kind === 'auth') {
      state.strava = { ...state.strava, accessToken: null, expiresAt: 0 };
      saveStrava(state.strava);
    }
  } finally {
    button.disabled = false;
  }
}

// ---- files -----------------------------------------------------------------------------------

async function addFiles(fileList) {
  for (const file of fileList) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="name"></span><span class="detail">reading…</span>`;
    li.querySelector('.name').textContent = file.name;
    $('file-list').appendChild(li);

    try {
      const dataset = await importFile(file, (msg) => {
        li.querySelector('.detail').textContent = msg;
      });
      state.datasets.push(dataset);
      state.files.push(file.name);
      // A newly imported file's sessions should arrive selected, so re-derive the selection
      // rather than leaving them unticked behind an unchanged count.
      state.selected = null;

      const n = dataset.sessions.length;
      li.querySelector('.detail').textContent = dataset.source;
      const count = document.createElement('span');
      count.className = 'count';
      count.textContent = `${n} session${n === 1 ? '' : 's'}`;
      li.appendChild(count);

      log(`${file.name}: ${n} session${n === 1 ? '' : 's'} read as ${dataset.source}.`);
      for (const w of dataset.warnings || []) log(`${file.name}: ${w}`, 'warn');
    } catch (err) {
      li.querySelector('.detail').textContent = 'could not be read';
      log(`${file.name}: ${err.message}`, 'warn');
    }
  }
  renderSessionPicker();
  updateRunButton();
}

/**
 * List the sessions in the chosen period, so specific ones can be picked.
 *
 * Everything imported is kept and only the display is filtered, so narrowing the dates does not
 * mean reading the files again. Sessions the glucose record does not cover are shown but not
 * selectable, because evaluating one would produce a page of findings that all say the same
 * thing about missing data.
 */
function renderSessionPicker() {
  const { inRange, outside, all } = sessionsInRange();
  const step = $('step-sessions');

  if (!all.length) {
    step.hidden = true;
    state.selected = null;
    return;
  }
  step.hidden = false;

  const ns = state.nightscout;
  const covered = (s) => {
    if (!ns || !ns.entries.length) return true;   // nothing fetched yet, so nothing to exclude
    return s.end >= ns.entries[0].t && s.start <= ns.entries[ns.entries.length - 1].t;
  };

  // First render, or a range change that revealed new sessions: select everything usable.
  if (state.selected === null) {
    state.selected = new Set(inRange.filter(covered).map((s) => s.id));
  }

  const dayOf = (ms) => new Date(ms).toLocaleDateString([], {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

  const rows = [];
  let lastDay = null;
  for (const s of inRange) {
    const day = dayOf(s.start);
    if (day !== lastDay) {
      rows.push(`<li class="day-heading" role="presentation">${esc(day)}</li>`);
      lastDay = day;
    }
    const usable = covered(s);
    const detail = [
      `${Math.round(s.durationMin)} min`,
      s.distanceM ? `${(s.distanceM / 1000).toFixed(1)} km` : null,
      s.hr && s.hr.length ? `${s.hr.length} heart rate readings` : 'no heart rate',
      s.sourceApp,
    ].filter(Boolean).join(' · ');

    rows.push(`<li class="${usable ? '' : 'no-glucose'}">
      <label>
        <input type="checkbox" value="${esc(s.id)}"
               ${state.selected.has(s.id) ? 'checked' : ''} ${usable ? '' : 'disabled'}>
        <span class="when">${esc(new Date(s.start).toLocaleTimeString([],
          { hour: '2-digit', minute: '2-digit' }))}</span>
        <span class="what">${esc(s.title || titleCase(s.typeName))}</span>
        <span class="detail">${esc(detail)}</span>
        ${usable ? '' : '<span class="flag">outside the glucose data fetched</span>'}
      </label>
    </li>`);
  }

  $('session-picker').innerHTML = rows.join('') ||
    '<li><label><span class="what">No sessions start inside this period.</span></label></li>';

  const selectable = inRange.filter(covered).length;
  const chosen = inRange.filter((s) => state.selected.has(s.id)).length;
  $('session-count').textContent =
    `${chosen} of ${selectable} selected` +
    (selectable < inRange.length
      ? `, and ${inRange.length - selectable} outside the glucose data fetched`
      : '');

  $('session-outside').textContent = outside > 0
    ? `${outside} further session${outside === 1 ? '' : 's'} in your files fall outside this ` +
      'period. Widen the dates above to include them.'
    : '';
}

function onPickerChange(ev) {
  const box = ev.target.closest('input[type="checkbox"]');
  if (!box) return;
  if (box.checked) state.selected.add(box.value);
  else state.selected.delete(box.value);
  renderSessionPicker();
  updateRunButton();
}

function selectAll(select) {
  const { inRange } = sessionsInRange();
  const ns = state.nightscout;
  const covered = (s) => !ns || !ns.entries.length ||
    (s.end >= ns.entries[0].t && s.start <= ns.entries[ns.entries.length - 1].t);
  state.selected = select ? new Set(inRange.filter(covered).map((s) => s.id)) : new Set();
  renderSessionPicker();
  updateRunButton();
}

/** The sessions that will actually be evaluated. */
function chosenSessions() {
  if (!state.selected) return [];
  return sessionsInRange().inRange.filter((s) => state.selected.has(s.id));
}

function updateRunButton() {
  const chosen = chosenSessions().length;
  const anyFiles = state.datasets.length > 0;
  const ready = Boolean(state.nightscout) && chosen > 0;
  $('run').disabled = !ready;

  if (ready) {
    $('run-status').textContent =
      `${chosen} session${chosen === 1 ? '' : 's'} ready to evaluate against ` +
      `${state.nightscout.entries.length.toLocaleString()} sensor readings.`;
  } else if (!state.nightscout && anyFiles) {
    $('run-status').textContent = 'Fetch your Nightscout data to continue.';
  } else if (state.nightscout && !anyFiles) {
    $('run-status').textContent = 'Add an activity file to continue.';
  } else if (anyFiles && !chosen) {
    $('run-status').textContent = 'Choose at least one session in step 4.';
  } else {
    $('run-status').textContent =
      'Fetch your Nightscout data and add an activity file first.';
  }
}

// ---- running ---------------------------------------------------------------------------------

async function run() {
  $('run').disabled = true;
  progress(0.05);

  try {
    const merged = mergeDatasets(state.datasets);
    for (const w of merged.warnings) log(w, 'warn');

    const ns = state.nightscout;
    // Only sessions the CGM record actually covers can be evaluated, so the rest are named
    // rather than silently dropped. The picker already excludes them, but a range changed after
    // the fetch can reintroduce one.
    const oldest = ns.entries.length ? ns.entries[0].t : Infinity;
    const newest = ns.entries.length ? ns.entries[ns.entries.length - 1].t : -Infinity;
    const chosen = chosenSessions();
    const inRange = chosen.filter((s) => s.end >= oldest && s.start <= newest);
    const outside = chosen.length - inRange.length;
    if (outside > 0) {
      log(`${outside} of the chosen session${outside === 1 ? '' : 's'} fell outside the glucose ` +
          'data fetched, and were left out. Widening the dates and fetching again would include ' +
          'them.', 'warn');
    }
    if (!inRange.length) {
      log('None of the chosen sessions overlap the glucose data, so there is nothing to ' +
          'evaluate.', 'warn');
      return;
    }
    log(`Evaluating ${inRange.length} session${inRange.length === 1 ? '' : 's'}.`);

    // Heart rate detail from Strava is one request per activity against a small budget, so it
    // is fetched here, for the chosen sessions only, rather than for everything on import.
    const stravaChosen = inRange.filter((s) => s.stravaId && s.hasHeartRate && !s.hr.length);
    if (stravaChosen.length && state.strava?.refreshToken) {
      try {
        const token = await stravaToken();
        const { fetched, warnings } = await strava.fetchHeartRateFor(
          token, stravaChosen, (m) => { log(m); progress(0.1); });
        if (fetched) {
          log(`Fetched heart rate detail for ${fetched} of ${stravaChosen.length} Strava ` +
              'sessions.');
        }
        for (const w of warnings) log(`Strava: ${w}`, 'warn');
      } catch (err) {
        log(`Strava: ${err.message} The analysis continues with the summary heart rate for ` +
            'those sessions.', 'warn');
      }
    }

    const settings = readSettings();
    // The most recent resting heart rate before each session, where the export carried one.
    if (!settings.resting_hr && merged.restingHr?.length) {
      const recent = merged.restingHr.slice(-14);
      settings.resting_hr = Math.round(recent.reduce((a, r) => a + r.bpm, 0) / recent.length);
      log(`Resting heart rate taken from the export as ${settings.resting_hr} bpm, the mean of ` +
          'the last 14 readings.');
    }

    const report = await analyse(
      { sessions: inRange, entries: ns.entries, treatments: ns.treatments,
        profile: ns.profile, settings },
      (stage, detail) => {
        log(detail);
        progress(stage === 'runtime' ? 0.2 : stage === 'package' ? 0.6 : 0.85);
      },
    );

    progress(1);
    render(report, ns, settings);
    $('results').hidden = false;
    $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    log(`The analysis failed: ${err.message}`, 'warn');
    console.error(err);
  } finally {
    $('run').disabled = false;
    setTimeout(() => progress(null), 800);
  }
}

// ---- rendering -------------------------------------------------------------------------------

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const titleCase = (s) => String(s || '').toLowerCase().split('_')
  .map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
  .replace('High Intensity Interval Training', 'HIIT');

function render(report, ns, settings) {
  renderSummary(report.summary, settings.units);
  renderSessions(report.sessions, ns, settings.units);
  renderBibliography(report.bibliography);
  attachHover($('sessions'));
}

function renderSummary(summary, units) {
  const tiles = summary.groups.map((g) => {
    const change = g.sufficient
      ? `${g.median_change_mmol >= 0 ? '+' : ''}${
          units === 'mgdl' ? Math.round(g.median_change_mmol * 18.0182) : g.median_change_mmol.toFixed(1)}`
      : '—';
    const unitLabel = units === 'mgdl' ? 'mg/dL' : 'mmol/L';
    return `<div class="group-tile">
      <span class="value">${change}${g.sufficient ? ` <span style="font-size:0.7em;font-weight:400">${unitLabel}</span>` : ''}</span>
      <span class="label">median change during ${esc(g.modality)} sessions</span>
      <span class="sub">${esc(g.note)}${
        g.hypo_during_n ? ` ${g.hypo_during_n} of ${g.n} went below range during the session.` : ''}</span>
    </div>`;
  }).join('');

  $('summary').innerHTML = `
    <p>${summary.sessions_analysed} session${summary.sessions_analysed === 1 ? '' : 's'}
       evaluated, ${summary.sessions_with_coverage} with sensor coverage good enough to
       contribute to the figures below.</p>
    <div class="summary-groups">${tiles}</div>
    ${summary.contrast ? `<p>${esc(summary.contrast)}</p>` : ''}
    <p class="hint">${esc(summary.caveat)}</p>`;
}

function renderSessions(sessions, ns, units) {
  const html = sessions.map((r) => {
    if (r.error) {
      return `<div class="session-card"><h3>A session could not be evaluated</h3>
        <p class="hint">${esc(r.error)}</p></div>`;
    }
    const s = r.session;
    const start = new Date(s.start);
    const windowStart = s.start - 2 * 3_600_000;
    const windowEnd = s.end + 6 * 3_600_000;

    const entries = ns.entries.filter((e) => e.t >= windowStart && e.t <= windowEnd);
    const doses = ns.treatments.filter(
      (t) => t.kind === 'dose' && t.t >= windowStart && t.t <= windowEnd);
    const hr = (ns.sessionHr && ns.sessionHr[s.id]) || [];

    const facts = [
      titleCase(s.typeName),
      `${Math.round(s.durationMin)} min`,
      s.distanceM ? `${(s.distanceM / 1000).toFixed(1)} km` : null,
      s.activeKcal ? `${Math.round(s.activeKcal)} kcal` : null,
      s.sourceApp,
    ].filter(Boolean).map((f) => `<span>${esc(f)}</span>`).join('');

    const g = r.glucose;
    const windows = [g.during, g.recovery, g.late, g.overnight, g.antecedent];

    return `<article class="session-card">
      <div class="session-head">
        <h3>${esc(s.title || titleCase(s.typeName))}</h3>
        <span class="session-when">${start.toLocaleDateString([], {
          weekday: 'short', day: 'numeric', month: 'short' })}, ${start.toLocaleTimeString([], {
          hour: '2-digit', minute: '2-digit' })}</span>
      </div>
      <p class="session-facts">${facts}</p>
      <p>${esc(r.intensity.description)}</p>
      ${sessionChart({
        entries, hr, treatments: doses,
        sessionStart: s.start, sessionEnd: s.end, windowStart, windowEnd, units,
      })}
      ${r.findings.map(renderFinding).join('')}
      <details class="help">
        <summary>The numbers behind this session</summary>
        <div class="table-scroll">${summaryTable(windows, units)}</div>
      </details>
    </article>`;
  }).join('');

  $('sessions').innerHTML = html;
}

function renderFinding(f) {
  const parts = [`<h4>${esc(f.headline)}${
    f.provisional ? '<span class="provisional">provisional</span>' : ''}</h4>`];
  if (f.observed) parts.push(`<p class="observed">${esc(f.observed)}</p>`);
  if (f.guidance) {
    parts.push(`<p class="guidance"><span class="label">guidance</span>${esc(f.guidance)}</p>`);
  }
  if (f.action) {
    parts.push(`<p class="action"><span class="label">to change</span>${esc(f.action)}</p>`);
  }
  if (f.citations?.length) {
    parts.push(`<p class="citations">${esc(f.citations.join(' · '))}</p>`);
  }
  return `<div class="finding" data-severity="${esc(f.severity)}">${parts.join('')}</div>`;
}

function renderBibliography(bib) {
  if (!bib.length) { $('bibliography-block').hidden = true; return; }
  $('bibliography-block').hidden = false;
  $('bibliography').innerHTML = bib.map((b) => {
    const bits = [b.design];
    if (b.n) bits.push(`n = ${b.n}`);
    if (b.grade) bits.push(`graded ${b.grade}`);
    if (!b.is_evidence) bits.push('agreed by a panel rather than measured');
    return `<div class="bib-entry">${esc(b.citation)}
      <span class="design">${esc(bits.join(' · '))}${
        b.population ? `. ${esc(b.population)}` : ''}</span></div>`;
  }).join('');
}

// ---- wiring ----------------------------------------------------------------------------------

function init() {
  loadSettings();

  // A first visit gets the last 30 days, which is enough to see a pattern without producing a
  // report nobody reads.
  if (!$('date-from').value || !$('date-to').value) {
    const preset = presetRange({ days: 30 });
    $('date-from').value = isoDay(preset.from);
    $('date-to').value = isoDay(preset.to - MS_PER_DAY);
  }

  for (const id of PERSISTED) $(id)?.addEventListener('change', saveSettings);
  for (const id of ['date-from', 'date-to']) {
    // A changed range can reveal or hide sessions, so the selection is re-derived rather than
    // silently keeping ticks against sessions that are no longer on screen.
    $(id).addEventListener('change', () => { state.selected = null; onRangeChanged(); });
  }
  for (const b of document.querySelectorAll('button.preset')) {
    b.addEventListener('click', () => {
      const r = presetRange(b.dataset);
      if (!r) return;
      state.selected = null;
      setRange(r.from, r.to - MS_PER_DAY);
    });
  }

  $('session-picker').addEventListener('change', onPickerChange);
  $('select-all').addEventListener('click', () => selectAll(true));
  $('select-none').addEventListener('click', () => selectAll(false));

  $('ns-connect').addEventListener('click', connectNightscout);
  $('run').addEventListener('click', run);

  state.strava = loadStrava();
  renderStrava();
  $('strava-connect').addEventListener('click', stravaConnect);
  $('strava-fetch').addEventListener('click', stravaFetch);
  $('strava-forget').addEventListener('click', stravaForget);
  // A return from Strava arrives as a query string on this page, so it is handled at load.
  stravaCompleteRedirect();

  const dz = $('dropzone');
  const input = $('file-input');
  dz.addEventListener('click', () => input.click());
  dz.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
  });
  input.addEventListener('change', () => { addFiles([...input.files]); input.value = ''; });

  for (const type of ['dragenter', 'dragover']) {
    dz.addEventListener(type, (e) => { e.preventDefault(); dz.classList.add('over'); });
  }
  for (const type of ['dragleave', 'drop']) {
    dz.addEventListener(type, (e) => { e.preventDefault(); dz.classList.remove('over'); });
  }
  dz.addEventListener('drop', (e) => {
    if (e.dataTransfer?.files?.length) addFiles([...e.dataTransfer.files]);
  });

  onRangeChanged();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
