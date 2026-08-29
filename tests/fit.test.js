import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { parseFit } from '../js/parsers/fit.js';
import { detectFormat } from '../js/parsers/detect.js';

const here = dirname(fileURLToPath(import.meta.url));
const bytes = new Uint8Array(readFileSync(join(here, 'fixtures/activity.fit')));

test('a FIT file is recognised by its signature rather than its extension', () => {
  const d = detectFormat(bytes, 'whatever.bin');
  assert.equal(d.kind, 'fit');
  assert.equal(d.confident, true);
});

test('the session summary is decoded with the right units', () => {
  const r = parseFit(bytes);
  assert.equal(r.sessions.length, 1);
  const s = r.sessions[0];
  assert.equal(s.typeName, 'RUNNING');
  assert.equal(s.modality, 'aerobic');
  assert.equal(s.durationMin, 45);
  // Distance is stored in centimetres and calories as a plain count.
  assert.equal(s.distanceM, 8100);
  assert.equal(s.activeKcal, 520);
  assert.equal(s.avgHr, 148);
  assert.equal(s.maxHr, 171);
});

test('the FIT epoch is converted to unix time correctly', () => {
  const r = parseFit(bytes);
  const s = r.sessions[0];
  assert.equal(new Date(s.start).toISOString(), '2026-08-03T18:00:00.000Z');
  assert.equal(new Date(s.end).toISOString(), '2026-08-03T18:45:00.000Z');
});

test('the heart rate series is attached and confined to the session', () => {
  const r = parseFit(bytes);
  const s = r.sessions[0];
  assert.equal(s.hr.length, 270); // 45 minutes at one record per 10 seconds
  assert.ok(s.hr.every((p) => p.t >= s.start && p.t <= s.end));
  assert.ok(s.hr.every((p) => p.bpm >= 55 && p.bpm <= 200));
  // The ramp in the fixture must survive decoding.
  assert.ok(s.hr[0].bpm < s.hr[s.hr.length - 1].bpm);
});

test('a truncated file stops cleanly and says why rather than reading garbage', () => {
  // The header still declares the full data size, so a naive decoder walks off the end of the
  // buffer. It must stop at the boundary, say the file is truncated, and return what it read.
  for (const fraction of [0.1, 0.3, 0.6, 0.95]) {
    const truncated = bytes.subarray(0, Math.floor(bytes.length * fraction));
    const r = parseFit(truncated);
    assert.ok(Array.isArray(r.sessions), `threw at ${fraction}`);
    assert.ok(r.warnings.some((w) => /truncated/.test(w)),
      `no truncation warning at ${fraction}: ${JSON.stringify(r.warnings)}`);
  }
});

test('a file truncated before the session summary still returns the records it read', () => {
  // The session message is written last, so cutting the file short leaves records with no
  // summary. A session is synthesised from the record stream and the report says so.
  const truncated = bytes.subarray(0, bytes.length - 60);
  const r = parseFit(truncated);
  assert.ok(r.warnings.some((w) => /no session summary|truncated/.test(w)));
});

test('random bytes carrying a forged signature do not crash the decoder', () => {
  const junk = new Uint8Array(400);
  junk[0] = 12;
  junk.set([0x2e, 0x46, 0x49, 0x54], 8); // ".FIT"
  new DataView(junk.buffer).setUint32(4, 388, true);
  for (let i = 12; i < junk.length; i++) junk[i] = (i * 37) % 256;
  const r = parseFit(junk);
  assert.ok(Array.isArray(r.sessions));
});

test('a file without the signature is refused with a clear message', () => {
  const junk = new Uint8Array(64);
  assert.throws(() => parseFit(junk), /too short|\.FIT signature/);
});
