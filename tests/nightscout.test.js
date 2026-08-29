import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normaliseBase, normaliseTreatments, scheduleValueAt, MGDL_PER_MMOL } from '../js/nightscout.js';

test('base address is normalised and an api path is stripped', () => {
  assert.equal(normaliseBase('mysite.herokuapp.com'), 'https://mysite.herokuapp.com');
  assert.equal(normaliseBase('https://mysite.fly.dev/'), 'https://mysite.fly.dev');
  assert.equal(normaliseBase('https://mysite.fly.dev/api/v1/entries.json'), 'https://mysite.fly.dev');
  assert.equal(normaliseBase('  https://a.b.c///  '), 'https://a.b.c');
});

test('a plain http address is refused, because the page cannot fetch it', () => {
  assert.throws(() => normaliseBase('http://mysite.example'), /must use https/);
  assert.doesNotThrow(() => normaliseBase('http://localhost:1337'));
});

test('every AAPS SMB is written as a Correction Bolus and is flagged as automatic', () => {
  const [a, b] = normaliseTreatments([
    { created_at: '2026-08-01T10:00:00Z', eventType: 'Correction Bolus', insulin: 0.15, type: 'SMB', isSMB: true },
    { created_at: '2026-08-01T10:05:00Z', eventType: 'Correction Bolus', insulin: 2.0, type: 'NORMAL' },
  ]);
  assert.equal(a.kind, 'dose');
  assert.equal(a.isSmb, true);
  assert.equal(a.automatic, true);
  // A correction the person dialled by hand is not an SMB even under the same event type.
  assert.equal(b.isSmb, false);
  assert.equal(b.automatic, false);
});

test('an older document carrying only one of the two SMB markers is still recognised', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T10:00:00Z', eventType: 'Correction Bolus', insulin: 0.2, isSMB: true },
  ]);
  assert.equal(a.isSmb, true);
});

test('a Meal Bolus with carbs and no insulin field is not assumed to carry insulin', () => {
  // AAPS writes carbs of 12 g or more as Meal Bolus with no insulin.
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T12:00:00Z', eventType: 'Meal Bolus', carbs: 40 },
  ]);
  assert.equal(a.kind, 'dose');
  assert.equal(a.carbsG, 40);
  assert.equal(a.insulinU, null);
});

test('carbs under 12 g arrive as Carb Correction and are still a dose', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T12:00:00Z', eventType: 'Carb Correction', carbs: 8 },
  ]);
  assert.equal(a.kind, 'dose');
  assert.equal(a.carbsG, 8);
});

test('an Effective Profile Switch arrives as a Note and is not treated as a comment', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T09:00:00Z', eventType: 'Note', originalProfileName: 'Weekday',
      originalPercentage: 80, originalDuration: 3600000 },
  ]);
  assert.equal(a.kind, 'effective-profile-switch');
  assert.equal(a.profileName, 'Weekday');
  assert.equal(a.percentage, 80);
  assert.equal(a.durationMin, 60);
});

test('a genuine note is still a note', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T09:00:00Z', eventType: 'Note', notes: 'felt rough' },
  ]);
  assert.equal(a.kind, 'other');
  assert.equal(a.notes, 'felt rough');
});

test('temp target bounds are read as mg/dL and converted, whatever the site displays', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T17:00:00Z', eventType: 'Temporary Target', reason: 'Activity',
      duration: 90, targetTop: 140, targetBottom: 140, units: 'mg/dl' },
  ]);
  assert.equal(a.kind, 'temp-target');
  assert.equal(a.reason, 'Activity');
  assert.equal(a.targetTopMgdl, 140);
  assert.ok(Math.abs(a.targetTopMmol - 140 / MGDL_PER_MMOL) < 1e-9);
});

test('a zero-duration temp target is a cancel and may carry no target fields', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T18:30:00Z', eventType: 'Temporary Target', duration: 0 },
  ]);
  assert.equal(a.kind, 'temp-target-cancel');
  assert.equal(a.targetTopMgdl, null);
});

test('Nightscout Manual and AAPS Custom are folded together', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T17:00:00Z', eventType: 'Temporary Target', reason: 'Manual',
      duration: 60, targetTop: 120, targetBottom: 100 },
  ]);
  assert.equal(a.reason, 'Custom');
});

test('temp basal rate is read as absolute U/h and percent is understood as a delta', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T17:05:00Z', eventType: 'Temp Basal', rate: 0.4, percent: -60,
      duration: 30, type: 'NORMAL' },
  ]);
  assert.equal(a.kind, 'temp-basal');
  assert.equal(a.rateUph, 0.4);
  assert.equal(a.percentDelta, -60); // a 40 percent temp basal
});

test('a profile switch has its embedded profile string parsed', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T08:00:00Z', eventType: 'Profile Switch', profile: 'Sport',
      percentage: 70, duration: 180,
      profileJson: JSON.stringify({ dia: 6, units: 'mmol', basal: [{ time: '00:00', value: 0.8 }] }) },
  ]);
  assert.equal(a.kind, 'profile-switch');
  assert.equal(a.percentage, 70);
  assert.equal(a.profile.dia, 6);
});

test('a malformed profileJson does not throw', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T08:00:00Z', eventType: 'Profile Switch', profile: 'Sport',
      profileJson: '{not json' },
  ]);
  assert.equal(a.profile, null);
});

test('a care portal exercise event is recognised', () => {
  const [a] = normaliseTreatments([
    { created_at: '2026-08-01T18:00:00Z', eventType: 'Exercise', duration: 45, notes: 'club run' },
  ]);
  assert.equal(a.kind, 'exercise-event');
  assert.equal(a.durationMin, 45);
});

test('duplicates from overlapping pages are dropped and output is time ordered', () => {
  const t = normaliseTreatments([
    { _id: 'x', created_at: '2026-08-01T10:05:00Z', eventType: 'Meal Bolus', insulin: 2 },
    { _id: 'x', created_at: '2026-08-01T10:05:00Z', eventType: 'Meal Bolus', insulin: 2 },
    { _id: 'y', created_at: '2026-08-01T09:00:00Z', eventType: 'Meal Bolus', insulin: 1 },
  ]);
  assert.equal(t.length, 2);
  assert.ok(t[0].t < t[1].t);
});

test('a record with an unreadable timestamp is dropped rather than crashing the parse', () => {
  const t = normaliseTreatments([
    { created_at: 'not a date', eventType: 'Meal Bolus', insulin: 2 },
    { created_at: '2026-08-01T09:00:00Z', eventType: 'Meal Bolus', insulin: 1 },
  ]);
  assert.equal(t.length, 1);
});

test('a schedule reads the entry in force, and wraps from the previous day before the first', () => {
  const basal = [
    { secondsFromMidnight: 0, value: 0.7 },
    { secondsFromMidnight: 6 * 3600, value: 1.1 },
    { secondsFromMidnight: 22 * 3600, value: 0.6 },
  ];
  const at = (h, m = 0) => { const d = new Date(2026, 7, 1); d.setHours(h, m, 0, 0); return d; };
  assert.equal(scheduleValueAt(basal, at(0, 30)), 0.7);
  assert.equal(scheduleValueAt(basal, at(6)), 1.1);
  assert.equal(scheduleValueAt(basal, at(21, 59)), 1.1);
  assert.equal(scheduleValueAt(basal, at(23)), 0.6);

  // A schedule that does not start at midnight wraps from its last entry.
  const partial = [{ secondsFromMidnight: 8 * 3600, value: 2.0 }];
  assert.equal(scheduleValueAt(partial, at(3)), 2.0);
  assert.equal(scheduleValueAt([], at(3)), null);
});
