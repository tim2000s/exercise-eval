// Wiring. Nothing here decides anything about diabetes; it moves data between the importers,
// the Nightscout client and the Python engine, and renders what comes back.

import { normaliseBase, probe, fetchEntries, fetchTreatments, fetchProfile } from './nightscout.js';
import { importFile, mergeDatasets } from './import.js';
import { analyse } from './pyodide-bridge.js';
import { sessionChart, attachHover, summaryTable } from './charts.js';

const $ = (id) => document.getElementById(id);
const MS_PER_DAY = 86_400_000;

/** Settings persist between visits; the token deliberately does not. */
const SETTINGS_KEY = 'exercise-eval.settings.v1';
const PERSISTED = ['ns-url', 'ns-days', 'set-age', 'set-mass', 'set-resting', 'set-maxhr',
  'set-units', 'set-risk', 'set-insulin'];

const state = {
  nightscout: null,   // { entries, treatments, profile, units, base }
  datasets: [],       // one per imported file
  files: [],
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
    const days = Number($('ns-days').value);
    const endMs = Date.now();
    const startMs = endMs - days * MS_PER_DAY;

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

    state.nightscout = { entries, treatments, profile, units: info.units, base, days };
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
  updateRunButton();
}

function updateRunButton() {
  const sessions = mergeDatasets(state.datasets).sessions.length;
  const ready = Boolean(state.nightscout) && sessions > 0;
  $('run').disabled = !ready;
  if (ready) {
    $('run-status').textContent =
      `${sessions} session${sessions === 1 ? '' : 's'} ready to evaluate against ` +
      `${state.nightscout.entries.length.toLocaleString()} sensor readings.`;
  } else if (!state.nightscout && sessions) {
    $('run-status').textContent = 'Fetch your Nightscout data to continue.';
  } else if (state.nightscout && !sessions) {
    $('run-status').textContent = 'Add an activity file to continue.';
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
    // rather than silently dropped.
    const oldest = ns.entries.length ? ns.entries[0].t : Infinity;
    const newest = ns.entries.length ? ns.entries[ns.entries.length - 1].t : -Infinity;
    const inRange = merged.sessions.filter((s) => s.end >= oldest && s.start <= newest);
    const outside = merged.sessions.length - inRange.length;
    if (outside > 0) {
      log(`${outside} session${outside === 1 ? '' : 's'} fell outside the ${ns.days} days of ` +
          'Nightscout data fetched, and were left out. Widening the date range would include them.',
          'warn');
    }
    if (!inRange.length) {
      log('No sessions overlap the glucose data, so there is nothing to evaluate.', 'warn');
      return;
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
  for (const id of PERSISTED) $(id)?.addEventListener('change', saveSettings);

  $('ns-connect').addEventListener('click', connectNightscout);
  $('run').addEventListener('click', run);

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

  updateRunButton();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
