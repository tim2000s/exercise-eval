// Turning a dropped file into sessions, whatever kind of file it is.
//
// The user is not asked what format their file is. Extensions lie, the Health Connect export is
// commonly renamed at setup, and someone who has just found the file in their cloud storage
// often does not know what is inside it. The bytes are examined instead and the importer says
// what it found, which is also the most useful thing to show when the answer is that the file is
// not what they expected.

import { unzipSync, unzip } from '../vendor/fflate.js';
import { detectFormat } from './parsers/detect.js';
import { parseHealthConnectDb, isSqlite } from './parsers/healthconnect-sqlite.js';
import { parseCsvSessions, parseJsonSessions } from './parsers/tabular.js';
import { parseFit } from './parsers/fit.js';
import { parseGpx, parseTcx } from './parsers/xml-activities.js';

/** Above this, the file is read in chunks rather than materialised whole. */
const STREAM_THRESHOLD_BYTES = 100 * 1024 * 1024;
/** Above this, sql.js holds too much in the WASM heap to be comfortable. */
const SQLITE_WARN_BYTES = 100 * 1024 * 1024;

let sqlPromise = null;

function loadSql() {
  if (sqlPromise) return sqlPromise;
  sqlPromise = (async () => {
    // sql.js ships a UMD build, so it is loaded by script tag and read off the global rather
    // than imported. The wasm sits beside it in vendor/.
    if (!window.initSqlJs) {
      await new Promise((resolve, reject) => {
        const el = document.createElement('script');
        el.src = new URL('../vendor/sql-wasm.js', import.meta.url);
        el.onload = resolve;
        el.onerror = () => reject(new Error('Could not load the SQLite reader from vendor/.'));
        document.head.appendChild(el);
      });
    }
    return window.initSqlJs({
      locateFile: (f) => new URL(`../vendor/${f}`, import.meta.url).toString(),
    });
  })();
  return sqlPromise;
}

const EMPTY = {
  sessions: [], warnings: [], restingHr: [], vo2max: [], glucose: [], nutrition: [], sleep: [],
  meta: {},
};

const decode = (bytes) => new TextDecoder('utf-8', { fatal: false }).decode(bytes);

/**
 * Read one file.
 *
 * @param {File} file
 * @param {(msg: string) => void} onProgress
 * @returns {Promise<object>} the parsed dataset, in the shape the analysis expects
 */
export async function importFile(file, onProgress = () => {}) {
  onProgress(`Reading ${file.name} (${(file.size / 1e6).toFixed(1)} MB).`);

  if (file.size > STREAM_THRESHOLD_BYTES) {
    onProgress(
      `${file.name} is ${(file.size / 1e6).toFixed(0)} MB. Reading a file this size holds ` +
        'roughly twice its size in memory while the browser still has the original, so this ' +
        'may be slow or may fail on a device with little memory to spare.',
    );
  }

  const head = new Uint8Array(await file.slice(0, 8192).arrayBuffer());
  const format = detectFormat(head, file.name);
  onProgress(format.detail);

  const bytes = new Uint8Array(await file.arrayBuffer());

  switch (format.kind) {
    case 'health-connect-zip':
    case 'archive-zip':
      return importZip(bytes, file.name, onProgress);
    case 'sqlite':
      return importSqlite(bytes, onProgress);
    case 'fit':
      return parseFit(bytes);
    case 'gpx':
      return parseGpx(decode(bytes));
    case 'tcx':
      return parseTcx(decode(bytes));
    case 'csv':
      return parseCsvSessions(decode(bytes));
    case 'json':
      return parseJsonSessions(decode(bytes));
    case 'apple-health-xml':
      return {
        ...EMPTY,
        source: 'apple-health',
        warnings: [
          'This is an Apple Health export. These are a single flat XML document commonly 200 ' +
            'to 500 MB unzipped, which a browser cannot parse as a document, and support for ' +
            'reading them in chunks is not implemented. Exporting the individual workouts as ' +
            'GPX, TCX or FIT files gives this tool something it can read.',
        ],
      };
    default:
      return { ...EMPTY, source: 'unknown', warnings: [format.detail] };
  }
}

async function importZip(bytes, filename, onProgress) {
  let entries;
  try {
    entries = await new Promise((resolve, reject) => {
      unzip(bytes, (err, data) => (err ? reject(err) : resolve(data)));
    });
  } catch (e) {
    return { ...EMPTY, source: 'zip',
      warnings: [`${filename} could not be unzipped: ${e.message}`] };
  }

  const names = Object.keys(entries);
  onProgress(`The archive holds ${names.length} file${names.length === 1 ? '' : 's'}.`);

  const dbName = names.find((n) => n.endsWith('.db') || isSqlite(entries[n]));
  if (dbName) {
    onProgress(`Reading the Health Connect database from ${dbName}.`);
    return importSqlite(entries[dbName], onProgress);
  }

  // A Strava or Garmin archive: one file per activity, plus a summary CSV. Each activity is
  // parsed and the results are merged, since the tool works in sessions rather than files.
  const merged = { ...EMPTY, source: 'archive', sessions: [], warnings: [] };
  let failed = 0;

  for (const name of names) {
    const lower = name.toLowerCase();
    try {
      if (lower.endsWith('.fit')) merged.sessions.push(...parseFit(entries[name]).sessions);
      else if (lower.endsWith('.gpx')) merged.sessions.push(...parseGpx(decode(entries[name])).sessions);
      else if (lower.endsWith('.tcx')) merged.sessions.push(...parseTcx(decode(entries[name])).sessions);
      else if (lower.endsWith('activities.csv')) {
        const r = parseCsvSessions(decode(entries[name]));
        // The summary CSV duplicates the per-activity files, so it is only used when no
        // per-activity file was readable. Counting both would double every session.
        merged.meta.summaryCsv = r;
      }
    } catch (e) {
      failed++;
      if (failed <= 3) merged.warnings.push(`${name} could not be read: ${e.message}`);
    }
  }

  if (!merged.sessions.length && merged.meta.summaryCsv?.sessions.length) {
    onProgress('No per-activity files were readable, so the summary CSV was used instead.');
    return merged.meta.summaryCsv;
  }
  if (failed > 3) {
    merged.warnings.push(`${failed} files in the archive could not be read.`);
  }
  if (!merged.sessions.length) {
    merged.warnings.push(
      'No activity files were found in this archive. Supported entries are .fit, .gpx and ' +
        '.tcx, or a Health Connect database.',
    );
  }
  // Archives are not ordered, and later stages assume sessions run forwards in time.
  merged.sessions.sort((a, b) => a.start - b.start);
  return merged;
}

async function importSqlite(bytes, onProgress) {
  if (!isSqlite(bytes)) {
    return { ...EMPTY, source: 'sqlite',
      warnings: ['This file does not begin with the SQLite header, so it is not a database.'] };
  }
  if (bytes.length > SQLITE_WARN_BYTES) {
    onProgress(
      `The database is ${(bytes.length / 1e6).toFixed(0)} MB. It is held entirely in memory ` +
        'while it is read, so this may be slow.',
    );
  }
  const SQL = await loadSql();
  const db = new SQL.Database(bytes);
  try {
    onProgress('Indexing the database so the per-session queries do not scan it repeatedly.');
    return parseHealthConnectDb(db);
  } finally {
    db.close();
  }
}

/** Merge the output of several files into one dataset, dropping sessions that overlap. */
export function mergeDatasets(datasets) {
  const merged = { ...EMPTY, source: 'merged', sessions: [], warnings: [] };
  for (const d of datasets) {
    merged.sessions.push(...(d.sessions || []));
    merged.warnings.push(...(d.warnings || []));
    for (const key of ['restingHr', 'vo2max', 'glucose', 'nutrition', 'sleep']) {
      merged[key].push(...(d[key] || []));
    }
  }
  merged.sessions.sort((a, b) => a.start - b.start);

  // The same run exported from a watch and from a phone appears twice with slightly different
  // boundaries. Two sessions that overlap by most of their length are the same session, and
  // the one carrying heart rate is kept because it is the one the analysis can use.
  const kept = [];
  for (const s of merged.sessions) {
    const clash = kept.find((k) => {
      const overlap = Math.min(k.end, s.end) - Math.max(k.start, s.start);
      return overlap > 0.7 * Math.min(k.end - k.start, s.end - s.start);
    });
    if (!clash) { kept.push(s); continue; }
    if ((s.hr?.length || 0) > (clash.hr?.length || 0)) {
      kept[kept.indexOf(clash)] = s;
    }
  }
  const dropped = merged.sessions.length - kept.length;
  if (dropped > 0) {
    merged.warnings.push(
      `${dropped} session${dropped === 1 ? '' : 's'} appeared in more than one file and ` +
        'the duplicates were dropped, keeping whichever copy carried heart rate.',
    );
  }
  merged.sessions = kept;
  return merged;
}
