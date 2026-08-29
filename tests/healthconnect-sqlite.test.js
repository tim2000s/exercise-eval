import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import initSqlJs from 'sql.js';
import { unzipSync } from 'fflate';
import { parseHealthConnectDb, isSqlite } from '../js/parsers/healthconnect-sqlite.js';
import { decodeExerciseType, modalityFor } from '../js/parsers/exercise-types.js';

const here = dirname(fileURLToPath(import.meta.url));
const zipBytes = new Uint8Array(readFileSync(join(here, 'fixtures/health_connect_export.zip')));

async function loadFixture() {
  const entries = unzipSync(zipBytes);
  const dbBytes = entries['health_connect_export.db'];
  const SQL = await initSqlJs();
  return parseHealthConnectDb(new SQL.Database(dbBytes));
}

test('the export zip holds one entry and that entry is a SQLite database', () => {
  const entries = unzipSync(zipBytes);
  assert.deepEqual(Object.keys(entries), ['health_connect_export.db']);
  assert.ok(isSqlite(entries['health_connect_export.db']));
});

test('isSqlite rejects a non-database', () => {
  assert.equal(isSqlite(new Uint8Array([0x50, 0x4b, 0x03, 0x04])), false);
  assert.equal(isSqlite(new Uint8Array([])), false);
});

test('schema version is read from the pragma rather than assumed', async () => {
  const d = await loadFixture();
  assert.equal(d.meta.dbVersion, 14);
});

test('sessions decode with the platform enum, not the Jetpack one', async () => {
  const d = await loadFixture();
  assert.equal(d.sessions.length, 4);
  assert.deepEqual(d.sessions.map((s) => s.typeName),
    ['RUNNING', 'STRENGTH_TRAINING', 'BIKING', 'WALKING']);
  // The same integers under the Jetpack scheme would give a different and wrong answer.
  assert.equal(decodeExerciseType(33, 'jetpack').name, 'GUIDED_BREATHING');
});

test('modality prior follows the activity label', async () => {
  const d = await loadFixture();
  assert.deepEqual(d.sessions.map((s) => s.modality),
    ['aerobic', 'resistance', 'aerobic', 'aerobic']);
  assert.equal(modalityFor('HIGH_INTENSITY_INTERVAL_TRAINING'), 'anaerobic');
});

test('energy is converted from stored calories to kilocalories', async () => {
  const d = await loadFixture();
  // The run was seeded at 520 kcal spread over 15-minute buckets straddling both ends.
  const run = d.sessions[0];
  assert.ok(run.activeKcal > 400 && run.activeKcal < 640,
    `expected roughly 520 kcal, got ${run.activeKcal}`);
});

test('overlapping records are apportioned rather than counted whole', async () => {
  const d = await loadFixture();
  const walk = d.sessions[3];
  // 30 minutes seeded at 2400 m. Buckets are 15 minutes and overhang each end, so counting
  // whole records would give a substantially larger figure than the seeded distance.
  assert.ok(walk.distanceM > 1900 && walk.distanceM < 2900,
    `expected roughly 2400 m, got ${walk.distanceM}`);
});

test('heart rate series is attached and downsampled below the cap', async () => {
  const d = await loadFixture();
  for (const s of d.sessions) {
    assert.ok(s.hr.length > 0, `${s.typeName} has no heart rate`);
    assert.ok(s.hr.length <= 3000);
    assert.ok(s.hr.every((p) => p.t >= s.start && p.t <= s.end));
    assert.ok(s.hr.every((p) => p.bpm >= 45 && p.bpm <= 210));
  }
  const ride = d.sessions[2];
  assert.ok(ride.hr.length > 100, 'a 165-minute ride should carry a dense series');
});

test('a missing table degrades to an empty list rather than throwing', async () => {
  const d = await loadFixture();
  // exercise_segments_table and sleep_session_record_table are absent from the fixture.
  assert.deepEqual(d.sessions.map((s) => s.segments.length), [0, 0, 0, 0]);
  assert.deepEqual(d.sleep, []);
});

test('blood glucose is read in mmol/L and converted for the mg/dL path', async () => {
  const d = await loadFixture();
  assert.equal(d.glucose.length, 10);
  for (const g of d.glucose) {
    assert.ok(g.mmol >= 4 && g.mmol <= 10);
    assert.ok(Math.abs(g.mgdl - g.mmol * 18.0182) < 1e-6);
  }
});

test('zone offsets are carried through in seconds', async () => {
  const d = await loadFixture();
  assert.ok(d.sessions.every((s) => s.startOffsetSec === 3600));
});

test('the writing app is resolved from application_info_table', async () => {
  const d = await loadFixture();
  assert.deepEqual(d.sessions.map((s) => s.sourceApp), ['Strava', 'Fitbit', 'Strava', 'Fitbit']);
});

test('carbohydrate entries are read from the nutrition table', async () => {
  const d = await loadFixture();
  assert.equal(d.nutrition.length, 10);
  assert.ok(d.nutrition.every((n) => n.carbsG > 0));
});
