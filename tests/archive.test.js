import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import './dom-shim.js';
import { unzipSync } from 'fflate';
import { detectFormat } from '../js/parsers/detect.js';
import { parseArchive } from '../js/parsers/archive.js';

// These cover the bulk export archive. tests/strava.test.js covers the API client.

const here = dirname(fileURLToPath(import.meta.url));
const bytes = new Uint8Array(readFileSync(join(here, 'fixtures/strava_export.zip')));

test('a Strava export is recognised as an activity archive', () => {
  const d = detectFormat(bytes, 'export_12345.zip');
  assert.equal(d.kind, 'archive-zip');
  assert.match(d.detail, /Strava/);
});

test('every activity is read, including the gzipped ones', () => {
  // Strava gzips individual activity files, so entries are named .fit.gz, .gpx.gz and .tcx.gz.
  // Matching on the bare extension misses three of the four in this archive.
  const r = parseArchive(unzipSync(bytes));
  assert.equal(r.sessions.length, 4, `read ${r.sessions.length}: ${r.warnings.join(' | ')}`);
});

test('sessions come back in time order with the right types', () => {
  const r = parseArchive(unzipSync(bytes));
  assert.deepEqual(r.sessions.map((s) => s.typeName),
    ['BIKING', 'RUNNING', 'SWIMMING_POOL', 'WALKING']);
  for (let i = 1; i < r.sessions.length; i++) {
    assert.ok(r.sessions[i].start >= r.sessions[i - 1].start, 'sessions are not in time order');
  }
});

test('the heart rate series survives decompression', () => {
  const r = parseArchive(unzipSync(bytes));
  for (const s of r.sessions) {
    assert.ok(s.hr.length > 10, `${s.typeName} carries only ${s.hr.length} heart rate readings`);
    assert.ok(s.hr.every((p) => p.t >= s.start && p.t <= s.end),
      `${s.typeName} has heart rate outside its own window`);
  }
});

test('the non-activity contents of the archive are skipped without complaint', () => {
  const r = parseArchive(unzipSync(bytes));
  // profile.csv, comments.csv, followers.csv, clubs.json and a photo are all present.
  const noise = r.warnings.filter((w) => /profile|comments|followers|clubs|photo|jpg/i.test(w));
  assert.deepEqual(noise, [], `complained about archive furniture: ${noise.join(' | ')}`);
});

test('the summary CSV is not counted on top of the per-activity files', () => {
  // activities.csv describes the same four activities. Counting both would double every session.
  const r = parseArchive(unzipSync(bytes));
  assert.equal(r.sessions.length, 4);
});

test('the summary CSV is used when no per-activity file can be read', () => {
  const entries = unzipSync(bytes);
  const only = { 'activities.csv': entries['activities.csv'] };
  const r = parseArchive(only);
  assert.equal(r.sessions.length, 4, `summary fallback read ${r.sessions.length}`);
  // Strava writes dates as "Aug 3, 2026, 5:00:00 PM", which is not ISO 8601.
  assert.ok(r.sessions.every((s) => Number.isFinite(s.start) && s.start > 0),
    'the Strava date format was not understood');
  const run = r.sessions.find((s) => s.typeName === 'RUNNING');
  assert.ok(run, 'the summary CSV did not yield a run');
});

test('an archive with nothing recognisable says so', () => {
  const r = parseArchive({ 'readme.txt': new Uint8Array([104, 105]) });
  assert.equal(r.sessions.length, 0);
  assert.ok(r.warnings.some((w) => /No activity files/.test(w)));
});
