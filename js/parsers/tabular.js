// CSV and JSON importer for third-party Health Connect exporters and similar tools.
//
// No third-party Android exporter publishes a schema for exercise sessions, and the two apps
// most used for this are closed source. A parser written against one vendor's column names
// would break on the next. So the header row is sniffed against a synonym table, the mapping
// it inferred is reported back to the user, and the UI lets them correct it by hand.

import { decodeExerciseType, modalityFor } from './exercise-types.js';

/** Column synonyms, lowercased and stripped of spaces, underscores and punctuation. */
const SYNONYMS = {
  start: ['start', 'starttime', 'startdate', 'startdatetime', 'begin', 'begintime', 'from',
    'datetimestart', 'localstarttime', 'startlocal', 'date', 'timestamp'],
  end: ['end', 'endtime', 'enddate', 'enddatetime', 'finish', 'finishtime', 'to',
    'datetimeend', 'localendtime', 'endlocal'],
  duration: ['duration', 'durationms', 'durations', 'durationmin', 'durationminutes',
    'elapsedtime', 'movingtime', 'totaltime', 'totaltimerdate'],
  type: ['type', 'exercisetype', 'activitytype', 'sporttype', 'sport', 'workouttype',
    'exercise', 'activity', 'activityname'],
  title: ['title', 'name', 'activityname', 'workoutname', 'label'],
  notes: ['notes', 'note', 'description', 'comment', 'comments'],
  distance: ['distance', 'distancem', 'distancemeters', 'distancemetres', 'distancekm',
    'totaldistance'],
  kcal: ['calories', 'kcal', 'energy', 'activecalories', 'caloriesburned', 'energyburned',
    'activeenergy', 'totalcalories'],
  avgHr: ['avghr', 'averageheartrate', 'avgheartrate', 'heartrateaverage', 'meanhr',
    'averagehr', 'hravg'],
  maxHr: ['maxhr', 'maxheartrate', 'heartratemax', 'maximumheartrate'],
  steps: ['steps', 'stepcount', 'totalsteps'],
  elevation: ['elevation', 'elevationgain', 'totalascent', 'ascent', 'elevationgained'],
};

const norm = (s) => String(s).toLowerCase().replace(/[^a-z0-9]/g, '');

/** @returns {Object<string,string>} field name to the source column it was matched to */
export function inferColumns(headers) {
  const normed = headers.map(norm);
  const mapping = {};
  for (const [field, options] of Object.entries(SYNONYMS)) {
    for (const opt of options) {
      const i = normed.indexOf(opt);
      if (i !== -1 && !Object.values(mapping).includes(headers[i])) {
        mapping[field] = headers[i];
        break;
      }
    }
  }
  return mapping;
}

/**
 * Interpret a timestamp in whichever representation the exporter used.
 *
 * Open source Health Connect tools were observed emitting epoch milliseconds, epoch seconds
 * and ISO 8601 for the same field, so the representation is sniffed by magnitude rather than
 * configured. A bare number above about 1e12 is milliseconds and around 1e9 is seconds; the
 * boundary at 1e11 separates them for any date this tool will see.
 *
 * @returns {{ms: number|null, assumedLocal: boolean}} assumedLocal is true when the string
 *   carried no zone designator, in which case the viewer's zone was applied and the report
 *   says so rather than hiding it.
 */
export function parseTimestamp(value) {
  if (value === null || value === undefined || value === '') return { ms: null, assumedLocal: false };
  if (typeof value === 'number' || /^\d+(\.\d+)?$/.test(String(value).trim())) {
    const n = Number(value);
    if (n > 1e11) return { ms: Math.round(n), assumedLocal: false };
    if (n > 1e8) return { ms: Math.round(n * 1000), assumedLocal: false };
    return { ms: null, assumedLocal: false };
  }
  const s = String(value).trim();
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(s);
  const ms = Date.parse(hasZone ? s : s.replace(' ', 'T'));
  return { ms: Number.isNaN(ms) ? null : ms, assumedLocal: !hasZone };
}

/** Minimal RFC 4180 CSV reader: quoted fields, doubled quotes, embedded newlines and commas. */
export function parseCsv(text, delimiter = null) {
  const clean = text.replace(/^﻿/, '');
  if (delimiter === null) {
    const firstLine = clean.slice(0, clean.indexOf('\n') === -1 ? clean.length : clean.indexOf('\n'));
    const counts = [',', ';', '\t', '|'].map((d) => [d, firstLine.split(d).length]);
    counts.sort((a, b) => b[1] - a[1]);
    delimiter = counts[0][1] > 1 ? counts[0][0] : ',';
  }
  const out = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < clean.length; i++) {
    const c = clean[i];
    if (quoted) {
      if (c === '"') {
        if (clean[i + 1] === '"') { field += '"'; i++; } else { quoted = false; }
      } else field += c;
    } else if (c === '"') quoted = true;
    else if (c === delimiter) { row.push(field); field = ''; }
    else if (c === '\n') { row.push(field); out.push(row); row = []; field = ''; }
    else if (c !== '\r') field += c;
  }
  if (field !== '' || row.length) { row.push(field); out.push(row); }
  return { rows: out.filter((r) => r.some((v) => v !== '')), delimiter };
}

function toNumber(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(String(v).replace(/[^0-9.eE+-]/g, ''));
  return Number.isFinite(n) ? n : null;
}

/**
 * Build sessions from rows of objects.
 *
 * @param {Array<Object>} records rows keyed by source column name
 * @param {Object} mapping field to column, from inferColumns or edited by the user
 * @param {'jetpack'|'platform'} scheme integer encoding for a numeric exercise type. Third-party
 *   exporters build on the Jetpack client, so jetpack is the default and the right one here.
 */
export function buildSessions(records, mapping, scheme = 'jetpack') {
  const warnings = [];
  const sessions = [];
  let assumedLocalCount = 0;

  for (const [i, rec] of records.entries()) {
    const startRaw = mapping.start ? rec[mapping.start] : null;
    const s = parseTimestamp(startRaw);
    if (s.ms === null) {
      if (i < 5) warnings.push(`Row ${i + 1}: could not read a start time from "${startRaw}".`);
      continue;
    }
    if (s.assumedLocal) assumedLocalCount++;

    let endMs = null;
    if (mapping.end) {
      const e = parseTimestamp(rec[mapping.end]);
      endMs = e.ms;
    }
    if (endMs === null && mapping.duration) {
      const col = norm(mapping.duration);
      const d = toNumber(rec[mapping.duration]);
      if (d !== null) {
        // The unit is not recoverable from the value alone, so it is taken from the column
        // name where that says, and otherwise inferred: a session is unlikely to be under a
        // minute or over a day, which separates the three candidate units cleanly.
        let ms;
        if (col.includes('ms')) ms = d;
        else if (col.includes('min')) ms = d * 60000;
        else if (col.includes('sec') || col.endsWith('s')) ms = d * 1000;
        else if (d > 86400) ms = d;
        else if (d > 1440) ms = d * 1000;
        else ms = d * 60000;
        endMs = s.ms + ms;
      }
    }
    if (endMs === null || endMs <= s.ms) {
      if (i < 5) warnings.push(`Row ${i + 1}: no usable end time or duration.`);
      continue;
    }

    const typeVal = mapping.type ? rec[mapping.type] : null;
    const type = decodeExerciseType(typeVal, scheme);

    let distanceM = mapping.distance ? toNumber(rec[mapping.distance]) : null;
    if (distanceM !== null && norm(mapping.distance).includes('km')) distanceM *= 1000;

    sessions.push({
      id: `row-${i}`,
      start: s.ms,
      end: endMs,
      durationMin: (endMs - s.ms) / 60000,
      startOffsetSec: null,
      endOffsetSec: null,
      typeName: type.name,
      typeRaw: type.raw,
      typeKnown: type.known,
      modality: modalityFor(type.name),
      title: mapping.title ? rec[mapping.title] || null : null,
      notes: mapping.notes ? rec[mapping.notes] || null : null,
      sourceApp: null,
      distanceM,
      steps: mapping.steps ? toNumber(rec[mapping.steps]) : null,
      elevationM: mapping.elevation ? toNumber(rec[mapping.elevation]) : null,
      activeKcal: mapping.kcal ? toNumber(rec[mapping.kcal]) : null,
      totalKcal: null,
      avgHr: mapping.avgHr ? toNumber(rec[mapping.avgHr]) : null,
      maxHr: mapping.maxHr ? toNumber(rec[mapping.maxHr]) : null,
      hr: [],
      speed: [],
      power: [],
      segments: [],
      laps: [],
    });
  }

  if (assumedLocalCount) {
    warnings.push(
      `${assumedLocalCount} of ${records.length} timestamps carried no time zone. This ` +
        "browser's zone was applied. If the export came from a device in another zone, the " +
        'sessions will be shifted and the Nightscout alignment will be wrong.',
    );
  }
  if (!mapping.type) {
    warnings.push('No activity type column was recognised. Every session is treated as unknown, ' +
      'so recommendations fall back to whatever heart rate data is available.');
  }
  return { sessions, warnings };
}

/** Entry point for a CSV file. */
export function parseCsvSessions(text, overrideMapping = null) {
  const { rows: r, delimiter } = parseCsv(text);
  if (r.length < 2) return { source: 'csv', sessions: [], warnings: ['The file has no data rows.'], mapping: {} };
  const headers = r[0].map((h) => h.trim());
  const mapping = overrideMapping || inferColumns(headers);
  const records = r.slice(1).map((row) => Object.fromEntries(headers.map((h, i) => [h, row[i]])));
  const { sessions, warnings } = buildSessions(records, mapping);
  return { source: 'csv', meta: { headers, delimiter, mapping }, sessions, warnings, mapping,
    restingHr: [], vo2max: [], glucose: [], nutrition: [], sleep: [] };
}

/** Entry point for a JSON file: an array of objects, or an object wrapping one. */
export function parseJsonSessions(text, overrideMapping = null) {
  let data = JSON.parse(text);
  if (!Array.isArray(data)) {
    const arr = Object.values(data).find((v) => Array.isArray(v) && v.length && typeof v[0] === 'object');
    if (!arr) throw new Error('No array of records found in this JSON file.');
    data = arr;
  }
  const headers = [...new Set(data.flatMap((o) => Object.keys(o)))];
  const mapping = overrideMapping || inferColumns(headers);
  const { sessions, warnings } = buildSessions(data, mapping);
  return { source: 'json', meta: { headers, mapping }, sessions, warnings, mapping,
    restingHr: [], vo2max: [], glucose: [], nutrition: [], sleep: [] };
}
