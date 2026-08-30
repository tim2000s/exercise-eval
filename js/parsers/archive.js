// Reader for an activity archive: a Strava bulk export, a Garmin account export, or any zip
// holding a set of activity files.
//
// Three properties of a real Strava export shape this module. Individual activity files are
// gzipped, so an entry is named 9001.fit.gz rather than 9001.fit and matching on the bare
// extension misses almost everything. The archive carries a good deal that is not activity data,
// which has to be skipped without filling the log with complaints about a profile CSV. And the
// summary activities.csv describes the same activities as the per-activity files, so counting
// both would double every session.

import { gunzipSync } from '../../vendor/fflate.js';
import { parseFit } from './fit.js';
import { parseGpx, parseTcx } from './xml-activities.js';
import { parseCsvSessions } from './tabular.js';

/** Entries that are part of the archive's furniture rather than activity data. */
const IGNORED = [
  /^profile\.csv$/i,
  /^comments?\.csv$/i,
  /^followers?\.csv$/i,
  /^following\.csv$/i,
  /^clubs?\./i,
  /^media\//i,
  /^photos?\//i,
  /^routes?\//i,
  /^segments?\//i,
  /^goals\.csv$/i,
  /^connected_apps\.csv$/i,
  /^logins\.csv$/i,
  /^contacts\.csv$/i,
  /^applications\.csv$/i,
  /^bikes\.csv$/i,
  /^shoes\.csv$/i,
  /^components\.csv$/i,
  /^global\.csv$/i,
  /^favorites\.csv$/i,
  /\.(jpe?g|png|heic|mp4|mov|json|txt|pdf|html)$/i,
  /^__MACOSX\//,
  /\/$/,                       // directory entries
  /(^|\/)\.DS_Store$/,
];

const decode = (bytes) => new TextDecoder('utf-8', { fatal: false }).decode(bytes);

const isGzip = (bytes) => bytes.length > 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;

/**
 * Return the bytes of an entry, decompressing it if the archive gzipped it.
 *
 * Both the name and the magic number are checked. Strava names its compressed entries with a
 * .gz suffix, but an entry that is gzipped without one still has to be read, and one named .gz
 * that is not actually gzipped should not throw.
 */
function contentOf(name, bytes) {
  if (!isGzip(bytes)) return { name, bytes };
  const inner = gunzipSync(bytes);
  return { name: name.replace(/\.gz$/i, ''), bytes: inner };
}

/**
 * Parse the entries of an already-unzipped archive.
 *
 * @param {Object<string, Uint8Array>} entries name to bytes, as fflate returns them
 * @param {(msg: string) => void} onProgress
 */
export function parseArchive(entries, onProgress = () => {}) {
  const warnings = [];
  const sessions = [];
  let summaryCsv = null;
  let failed = 0;
  let ignored = 0;

  const names = Object.keys(entries);
  const activityNames = names.filter((n) => !IGNORED.some((re) => re.test(n)));
  ignored = names.length - activityNames.length;

  for (const rawName of activityNames) {
    let name = rawName;
    let bytes = entries[rawName];
    try {
      ({ name, bytes } = contentOf(rawName, bytes));
    } catch (e) {
      failed++;
      if (failed <= 3) warnings.push(`${rawName} could not be decompressed: ${e.message}`);
      continue;
    }

    const lower = name.toLowerCase();
    try {
      if (lower.endsWith('.fit')) {
        sessions.push(...parseFit(bytes).sessions);
      } else if (lower.endsWith('.gpx')) {
        sessions.push(...parseGpx(decode(bytes)).sessions);
      } else if (lower.endsWith('.tcx')) {
        sessions.push(...parseTcx(decode(bytes)).sessions);
      } else if (/(^|\/)activities\.csv$/i.test(lower)) {
        summaryCsv = parseCsvSessions(decode(bytes));
      } else {
        ignored++;
      }
    } catch (e) {
      failed++;
      if (failed <= 3) warnings.push(`${rawName} could not be read: ${e.message}`);
    }
  }

  // The summary describes the same activities as the per-activity files, so it is a fallback
  // rather than an addition. It carries less: no heart rate series, and a coarser type.
  if (!sessions.length && summaryCsv?.sessions.length) {
    onProgress('No per-activity files were readable, so the summary CSV was used instead.');
    summaryCsv.warnings.push(
      'The per-activity files could not be read, so this came from activities.csv. That has no ' +
        'heart rate series, so intensity for these sessions rests on the activity label alone.',
    );
    return { ...summaryCsv, source: 'archive-summary' };
  }

  if (failed > 3) warnings.push(`${failed} files in the archive could not be read.`);
  if (!sessions.length) {
    warnings.push(
      'No activity files were found in this archive. Supported entries are .fit, .gpx and .tcx, ' +
        'compressed or not, or a Health Connect database.',
    );
  } else if (summaryCsv?.sessions.length) {
    const diff = summaryCsv.sessions.length - sessions.length;
    if (diff > 0) {
      warnings.push(
        `activities.csv lists ${summaryCsv.sessions.length} activities but only ` +
          `${sessions.length} had a readable file. The other ${diff} are missing from the ` +
          'archive, which Strava does for activities with no recorded track.',
      );
    }
  }

  // Archives are not ordered, and later stages assume sessions run forwards in time.
  sessions.sort((a, b) => a.start - b.start);

  return {
    source: 'archive',
    sessions,
    warnings,
    restingHr: [], vo2max: [], glucose: [], nutrition: [], sleep: [],
    meta: { entries: names.length, ignored, failed,
            summaryListed: summaryCsv?.sessions.length ?? null },
  };
}
